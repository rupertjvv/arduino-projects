"""
Tests for mic_calibrate.

Everything here works on synthetic readings, so the suite runs with no board
plugged in and no pyserial installed:

    python -m unittest discover -s tools
"""

import math
import unittest

import mic_calibrate as mc


def sine_capture(amplitude, seconds=2.0, period_ms=15.0, freq_hz=440.0,
                 offset=512):
    """
    Readings that look like a mic module on a 2.5 V bias sampled slowly.

    The sample period is far below the Nyquist rate for an audio tone, which
    is exactly the situation the sketch is in. That is fine here: the point of
    peak to peak sampling is that it recovers amplitude without resolving the
    waveform.
    """
    samples = []
    t_ms = 0.0
    while t_ms < seconds * 1000.0:
        angle = 2.0 * math.pi * freq_hz * (t_ms / 1000.0)
        samples.append(mc.Sample(t_ms, int(offset + amplitude * math.sin(angle))))
        t_ms += period_ms
    return samples


class TestParsing(unittest.TestCase):

    def test_timestamped_line(self):
        self.assertEqual(mc.parse_line("120.5,517", 0, 15.0),
                         mc.Sample(120.5, 517))

    def test_bare_value_gets_a_synthesised_timestamp(self):
        self.assertEqual(mc.parse_line("517", 4, 15.0), mc.Sample(60.0, 517))

    def test_whitespace_is_tolerated(self):
        self.assertEqual(mc.parse_line("  517  \r\n", 0, 15.0).value, 517)

    def test_blank_and_junk_lines_are_skipped(self):
        for line in ("", "   ", "\n", "hello", "1023 1023", "12.5"):
            self.assertIsNone(mc.parse_line(line, 0, 15.0), msg=repr(line))

    def test_partial_line_from_a_reset_is_skipped(self):
        # Opening the port resets the Uno, so the first line is often a fragment.
        self.assertIsNone(mc.parse_line("\x00\xff5", 0, 15.0))

    def test_capture_skips_junk_without_disturbing_the_clock(self):
        lines = ["500", "garbage", "520", "", "480"]
        samples = mc.parse_capture(lines, sample_period_ms=10.0)
        self.assertEqual([s.value for s in samples], [500, 520, 480])
        self.assertEqual([s.t_ms for s in samples], [0.0, 10.0, 20.0])

    def test_timestamped_capture_keeps_real_timings(self):
        lines = ["0.0,500", "14.9,520", "31.2,480"]
        samples = mc.parse_capture(lines)
        self.assertEqual([s.t_ms for s in samples], [0.0, 14.9, 31.2])


class TestSamplePeriod(unittest.TestCase):

    def test_measures_the_median_gap(self):
        samples = [mc.Sample(t, 500) for t in (0.0, 15.0, 30.0, 45.0)]
        self.assertAlmostEqual(mc.measure_sample_period(samples), 15.0)

    def test_a_single_stall_does_not_move_the_estimate(self):
        samples = [mc.Sample(t, 500) for t in (0.0, 15.0, 30.0, 400.0, 415.0)]
        self.assertAlmostEqual(mc.measure_sample_period(samples), 15.0)

    def test_too_few_samples_to_measure(self):
        self.assertIsNone(mc.measure_sample_period([]))
        self.assertIsNone(mc.measure_sample_period([mc.Sample(0.0, 500)]))


class TestWindowing(unittest.TestCase):

    def test_silence_has_no_spread(self):
        samples = [mc.Sample(i * 15.0, 512) for i in range(40)]
        self.assertTrue(all(w == 0 for w in mc.peak_to_peak_windows(samples)))

    def test_spread_tracks_amplitude(self):
        quiet = mc.peak_to_peak_windows(sine_capture(20))
        loud = mc.peak_to_peak_windows(sine_capture(200))
        self.assertGreater(mc.median(loud), mc.median(quiet) * 5)

    def test_recovers_the_amplitude_of_a_tone(self):
        # Peak to peak should approach twice the amplitude.
        windows = mc.peak_to_peak_windows(sine_capture(150, seconds=4.0))
        self.assertAlmostEqual(mc.percentile(windows, 90), 300, delta=40)

    def test_windows_split_on_the_configured_length(self):
        samples = [mc.Sample(i * 10.0, 512) for i in range(20)]  # 200 ms
        self.assertEqual(len(mc.peak_to_peak_windows(samples, window_ms=50.0)), 4)
        self.assertEqual(len(mc.peak_to_peak_windows(samples, window_ms=100.0)), 2)

    def test_a_short_tail_still_becomes_a_window(self):
        samples = [mc.Sample(i * 10.0, 512) for i in range(7)]  # 60 ms
        self.assertEqual(len(mc.peak_to_peak_windows(samples, window_ms=50.0)), 2)

    def test_one_sample_is_one_empty_window(self):
        self.assertEqual(mc.peak_to_peak_windows([mc.Sample(0.0, 512)]), [0])

    def test_no_samples_means_no_windows(self):
        self.assertEqual(mc.peak_to_peak_windows([]), [])

    def test_gaps_in_the_stream_do_not_merge_windows(self):
        # A stalled USB link must not produce one enormous window.
        samples = [mc.Sample(0.0, 400), mc.Sample(1000.0, 600)]
        self.assertEqual(mc.peak_to_peak_windows(samples, window_ms=50.0), [0, 0])


class TestStatistics(unittest.TestCase):

    def test_median_of_odd_and_even_counts(self):
        self.assertEqual(mc.median([3, 1, 2]), 2.0)
        self.assertEqual(mc.median([4, 1, 3, 2]), 2.5)

    def test_median_needs_values(self):
        with self.assertRaises(ValueError):
            mc.median([])

    def test_percentile_endpoints(self):
        values = list(range(101))
        self.assertEqual(mc.percentile(values, 0), 0)
        self.assertEqual(mc.percentile(values, 100), 100)
        self.assertAlmostEqual(mc.percentile(values, 50), 50)

    def test_percentile_interpolates(self):
        self.assertAlmostEqual(mc.percentile([0, 10], 25), 2.5)

    def test_percentile_rejects_out_of_range(self):
        for pct in (-1, 101):
            with self.assertRaises(ValueError):
                mc.percentile([1, 2, 3], pct)

    def test_percentile_of_one_value(self):
        self.assertEqual(mc.percentile([7], 90), 7.0)


class TestRecommendation(unittest.TestCase):

    def test_ceiling_sits_above_the_floor(self):
        stats = mc.recommend(mc.peak_to_peak_windows(sine_capture(150)))
        self.assertGreater(stats["ceiling"], stats["floor"])

    def test_louder_captures_recommend_a_higher_ceiling(self):
        quiet = mc.recommend(mc.peak_to_peak_windows(sine_capture(50)))
        loud = mc.recommend(mc.peak_to_peak_windows(sine_capture(300)))
        self.assertGreater(loud["ceiling"], quiet["ceiling"])

    def test_a_rare_spike_does_not_set_the_scale(self):
        # One door slam among quiet windows must not swamp the ceiling, which
        # is the whole reason for using a percentile rather than the maximum.
        windows = [20] * 200 + [900]
        stats = mc.recommend(windows)
        self.assertEqual(stats["max"], 900)
        self.assertLess(stats["ceiling"], 100)

    def test_silence_still_yields_a_usable_range(self):
        stats = mc.recommend([0] * 50)
        self.assertGreater(stats["ceiling"], stats["floor"])

    def test_needs_something_to_analyse(self):
        with self.assertRaises(ValueError):
            mc.recommend([])

    def test_reported_bounds_are_whole_numbers(self):
        # They are pasted straight into a map() call in C.
        stats = mc.recommend(mc.peak_to_peak_windows(sine_capture(123)))
        self.assertIsInstance(stats["floor"], int)
        self.assertIsInstance(stats["ceiling"], int)


class TestLevelMapping(unittest.TestCase):

    def test_floor_is_dark_and_ceiling_is_full(self):
        self.assertEqual(mc.level_for(30, 30, 300), 0)
        self.assertEqual(mc.level_for(300, 30, 300), 8)

    def test_clamped_at_both_ends(self):
        self.assertEqual(mc.level_for(-100, 30, 300), 0)
        self.assertEqual(mc.level_for(5000, 30, 300), 8)

    def test_midpoint_lands_halfway_up(self):
        self.assertEqual(mc.level_for(165, 30, 300), 4)

    def test_monotonic_across_the_range(self):
        levels = [mc.level_for(pp, 30, 300) for pp in range(0, 400, 5)]
        self.assertEqual(levels, sorted(levels))

    def test_every_row_is_reachable(self):
        levels = {mc.level_for(pp, 30, 300) for pp in range(0, 400)}
        self.assertEqual(levels, set(range(9)))

    def test_an_inverted_range_is_rejected(self):
        with self.assertRaises(ValueError):
            mc.level_for(100, 300, 30)


class TestMeter(unittest.TestCase):

    def test_bar_is_a_fixed_width(self):
        for pp in (0, 50, 300, 900):
            self.assertEqual(len(mc.bar(pp, 300, width=40)), 40)

    def test_bar_fills_as_it_gets_louder(self):
        quiet = mc.bar(30, 300).count("#")
        loud = mc.bar(280, 300).count("#")
        self.assertLess(quiet, loud)

    def test_bar_saturates_rather_than_overflowing(self):
        self.assertEqual(mc.bar(9000, 300, width=40), "#" * 40)


if __name__ == "__main__":
    unittest.main()
