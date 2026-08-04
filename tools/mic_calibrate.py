#!/usr/bin/env python3
"""
mic_calibrate.py - work out the map() bounds for the 8x8 audio visualiser.

The visualiser turns microphone amplitude into a column height with

    int newVolumeLevel = map(peakToPeak, 0, 300, 0, 8);

and that 300 is marked "TWEAK THIS" in the sketch because the right value
depends on the microphone module, its gain trimmer, the supply rail and how
far away you are. Guessing it means the display either sits at full scale or
barely lifts off the floor.

This reads the stream from the mic-level-serial sketch, reproduces on the host
exactly what the visualiser does on the board (peak to peak over a 50 ms
window), and reports the bounds that actually suit your bench.

    ./mic_calibrate.py --port /dev/cu.usbmodem1101          live, with meter
    ./mic_calibrate.py --port /dev/cu.usbmodem1101 --record quiet.csv
    ./mic_calibrate.py --replay quiet.csv                   analyse a capture

Live capture needs pyserial. Replay does not, and neither does anything in
here that a test touches.

Note on sample rate: mic-level-serial delays 10 ms per reading, but each line
is about five characters and 9600 baud only carries a character every ~1 ms,
so the real period lands nearer 15 ms. That is measured rather than assumed
whenever timestamps are available, and it is the reason the visualiser samples
on the board instead of streaming readings to a host.
"""

import argparse
import collections
import sys
import time

# Matches the sampling window in audio-visualiser-8x8.ino.
WINDOW_MS = 50.0

# Rows on the matrix, so the top of the range maps to a full column.
MATRIX_ROWS = 8

# The Uno ADC is 10 bit, so peak to peak cannot exceed this.
ADC_MAX = 1023


Sample = collections.namedtuple("Sample", "t_ms value")


def parse_line(line, index, sample_period_ms):
    """
    Turn one line of a capture into a Sample, or None if it is not a reading.

    Accepts both "t_ms,value" as written by --record and the bare "value" that
    the Arduino serial monitor produces, in which case the timestamp is
    synthesised from the assumed sample period.
    """
    line = line.strip()
    if not line:
        return None

    if "," in line:
        t_text, _, v_text = line.partition(",")
        try:
            return Sample(float(t_text), int(v_text))
        except ValueError:
            return None

    try:
        return Sample(index * sample_period_ms, int(line))
    except ValueError:
        return None


def parse_capture(lines, sample_period_ms=15.0):
    """Parse an iterable of lines, skipping anything unreadable."""
    samples = []
    for line in lines:
        sample = parse_line(line, len(samples), sample_period_ms)
        if sample is not None:
            samples.append(sample)
    return samples


def measure_sample_period(samples):
    """Median gap between readings, in ms. None if there is nothing to measure."""
    if len(samples) < 2:
        return None
    gaps = sorted(b.t_ms - a.t_ms for a, b in zip(samples, samples[1:]))
    return median(gaps)


def peak_to_peak_windows(samples, window_ms=WINDOW_MS):
    """
    Collapse samples into one peak-to-peak figure per window.

    This is the host side copy of the sketch's inner loop: track the running
    minimum and maximum for the length of the window and keep the difference.
    A single reading of an audio signal is close to meaningless because it
    catches the waveform at an arbitrary point in its cycle; the peak to peak
    spread over a window is stable enough to drive a display.
    """
    if not samples:
        return []

    windows = []
    window_start = samples[0].t_ms
    lo = hi = samples[0].value

    for sample in samples[1:]:
        if sample.t_ms - window_start >= window_ms:
            windows.append(hi - lo)
            window_start = sample.t_ms
            lo = hi = sample.value
        else:
            lo = min(lo, sample.value)
            hi = max(hi, sample.value)

    windows.append(hi - lo)
    return windows


def median(values):
    if not values:
        raise ValueError("median of no values")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def percentile(values, pct):
    """Linearly interpolated percentile. pct is 0 to 100."""
    if not values:
        raise ValueError("percentile of no values")
    if not 0 <= pct <= 100:
        raise ValueError("percentile out of range: %r" % pct)

    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    pos = (len(ordered) - 1) * (pct / 100.0)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    weight = pos - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def recommend(windows):
    """
    Suggest map() bounds from a capture.

    The floor is the 5th percentile: the quiet baseline of the room and the
    module's own noise. Mapping from 0 rather than from this is why a display
    can refuse to go fully dark in a quiet room.

    The ceiling is the 95th percentile rather than the maximum, so that a
    single door slam does not set the scale for everything else. A handful of
    peaks above it get clipped by constrain(), which is the intended behaviour.
    """
    if not windows:
        raise ValueError("no windows to analyse")

    floor = percentile(windows, 5)
    ceiling = percentile(windows, 95)

    # Keep the range usable even if the capture is nearly silent throughout.
    if ceiling - floor < 1.0:
        ceiling = floor + 1.0

    return {
        "count": len(windows),
        "min": min(windows),
        "max": max(windows),
        "median": median(windows),
        "floor": int(round(floor)),
        "ceiling": int(round(ceiling)),
        "clipped_pct": 100.0 * sum(1 for w in windows if w > ceiling) / len(windows),
        "dark_pct": 100.0 * sum(1 for w in windows if w <= floor) / len(windows),
    }


def level_for(pp, floor, ceiling, rows=MATRIX_ROWS):
    """The column height the sketch would show, given these bounds."""
    if ceiling <= floor:
        raise ValueError("ceiling must be above floor")
    scaled = (pp - floor) * rows // (ceiling - floor)
    return int(max(0, min(rows, scaled)))


def bar(pp, ceiling, width=40):
    """A one line meter for the live display."""
    if ceiling <= 0:
        return ""
    filled = int(min(1.0, pp / float(ceiling)) * width)
    return "#" * filled + "-" * (width - filled)


def read_serial(port, baud, seconds, record=None, quiet=False):
    """Stream from the board, printing a meter, until the time is up."""
    try:
        import serial  # pyserial, only needed for live capture
    except ImportError:
        sys.exit("Live capture needs pyserial:\n\n    pip install pyserial\n\n"
                 "Or analyse a saved capture with --replay.")

    samples = []
    sink = open(record, "w") if record else None

    try:
        with serial.Serial(port, baud, timeout=1) as link:
            # The Uno resets when the port opens; skip the boot noise.
            time.sleep(2.0)
            link.reset_input_buffer()

            start = time.monotonic()
            window_start = start
            lo = hi = None

            while time.monotonic() - start < seconds:
                raw = link.readline().decode("ascii", "replace").strip()
                if not raw:
                    continue
                try:
                    value = int(raw)
                except ValueError:
                    continue

                t_ms = (time.monotonic() - start) * 1000.0
                samples.append(Sample(t_ms, value))
                if sink:
                    sink.write("%.1f,%d\n" % (t_ms, value))

                lo = value if lo is None else min(lo, value)
                hi = value if hi is None else max(hi, value)

                if not quiet and (time.monotonic() - window_start) * 1000.0 >= WINDOW_MS:
                    pp = hi - lo
                    sys.stdout.write("\r%4d  %s" % (pp, bar(pp, 300)))
                    sys.stdout.flush()
                    window_start = time.monotonic()
                    lo = hi = None

            if not quiet:
                sys.stdout.write("\n")
    finally:
        if sink:
            sink.close()

    return samples


def report(samples, window_ms=WINDOW_MS):
    period = measure_sample_period(samples)
    windows = peak_to_peak_windows(samples, window_ms)
    stats = recommend(windows)

    print("samples          %d" % len(samples))
    if period is not None:
        print("sample period    %.1f ms  (%.0f Hz)"
              % (period, 1000.0 / period if period else 0))
    print("windows          %d of %.0f ms" % (stats["count"], window_ms))
    print()
    print("peak to peak     min %d, median %.0f, max %d"
          % (stats["min"], stats["median"], stats["max"]))
    print("noise floor      %d      (5th percentile)" % stats["floor"])
    print("loud level       %d      (95th percentile)" % stats["ceiling"])
    print()
    print("Suggested line for audio-visualiser-8x8.ino:")
    print()
    print("    int newVolumeLevel = map(peakToPeak, %d, %d, 0, %d);"
          % (stats["floor"], stats["ceiling"], MATRIX_ROWS))
    print()

    if stats["floor"] > 0:
        print("Mapping from %d rather than 0 is what stops the display glowing"
              % stats["floor"])
        print("in a quiet room: that much spread is present with no signal at all.")
        print()

    print("With these bounds this capture would have spent %.0f%% of its windows"
          % stats["dark_pct"])
    print("dark and clipped %.0f%% at full height." % stats["clipped_pct"])

    histogram(windows, stats)


def histogram(windows, stats):
    """Show how the capture spreads across the eight matrix rows."""
    floor, ceiling = stats["floor"], stats["ceiling"]
    counts = [0] * (MATRIX_ROWS + 1)
    for pp in windows:
        counts[level_for(pp, floor, ceiling)] += 1

    biggest = max(counts) or 1
    print()
    print("Column height distribution:")
    for level in range(MATRIX_ROWS, -1, -1):
        width = int(counts[level] / float(biggest) * 40)
        print("  %d  %-40s %5d" % (level, "#" * width, counts[level]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Work out map() bounds for the 8x8 audio visualiser.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--port", help="serial port of the board, e.g. /dev/cu.usbmodem1101")
    source.add_argument("--replay", metavar="FILE",
                        help="analyse a capture instead of reading the board")
    parser.add_argument("--baud", type=int, default=9600,
                        help="must match Serial.begin in the sketch (default: 9600)")
    parser.add_argument("--seconds", type=float, default=15.0,
                        help="how long to capture for (default: 15)")
    parser.add_argument("--record", metavar="FILE",
                        help="save the live capture for later replay")
    parser.add_argument("--window", type=float, default=WINDOW_MS,
                        help="sampling window in ms, matching the sketch (default: 50)")
    parser.add_argument("--sample-period", type=float, default=15.0,
                        help="assumed ms between readings, for captures without "
                             "timestamps (default: 15)")
    parser.add_argument("--quiet", action="store_true",
                        help="skip the live meter")
    args = parser.parse_args(argv)

    if args.replay:
        with open(args.replay) as handle:
            samples = parse_capture(handle, args.sample_period)
        if not samples:
            sys.exit("No readings found in %s" % args.replay)
    else:
        print("Capturing for %.0fs. Play something at the volume you want to "
              "fill the matrix." % args.seconds)
        samples = read_serial(args.port, args.baud, args.seconds,
                              args.record, args.quiet)
        if not samples:
            sys.exit("No readings arrived. Check the port, the baud rate, and "
                     "that the serial monitor is closed.")
        if args.record:
            print("Capture saved to %s" % args.record)
        print()

    report(samples, args.window)
    return 0


if __name__ == "__main__":
    sys.exit(main())
