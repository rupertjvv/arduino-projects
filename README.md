# Arduino Projects

A set of small Arduino UNO R3 sketches I wrote while learning embedded programming,
built and tested on a home bench with an oscilloscope, function generator and bench PSU.

The theme running through them is driving and reading hardware directly: multiplexing a
display faster than the eye can follow, sampling an analogue signal properly rather than
taking a single reading, and calibrating against what a sensor actually does instead of
what the datasheet range says.

---

## audio-visualiser-8x8

The main one. An electret microphone on `A0` drives a scrolling level meter on an 8x8 LED matrix.

Three things in here were more interesting than they first looked:

**Sampling.** A single `analogRead` of an audio signal is close to meaningless, because you catch
the waveform at an arbitrary point in its cycle. Instead the sketch tracks the running minimum and
maximum over a 50 ms window and uses the peak-to-peak difference as the amplitude. That is stable
enough to drive a display.

**Multiplexing.** All 64 LEDs share 8 row and 8 column pins, so only one column can be lit at a
time. The display loop walks the columns, holding each for 1 ms, which is fast enough that
persistence of vision makes the whole frame look continuously lit.

**Scrolling.** Column heights live in an 8-element buffer. Each frame shifts the buffer left and
writes the newest level into the last column, so the display scrolls right to left like a
spectrogram. The inner draw loop repeats a few times per sample to slow the scroll to a readable
speed without slowing the multiplexing itself.

Rows go through 1k resistors; columns are common cathode and driven low to enable.

## led-matrix-sweep-test

Lights one LED at a time across the whole matrix, 100 ms each. I wrote this first to prove out the
row and column wiring before anything more complicated depended on it. Useful for finding a
mis-wired pin in seconds rather than debugging it inside the visualiser.

## mic-level-serial

Minimal sketch that reads the microphone and streams raw values over serial at 9600 baud, so the
signal can be plotted on the computer. This is how I worked out what amplitude range the
microphone actually produced, which set the `map()` bounds used in the visualiser.

## pot-led-dimmer

A potentiometer fades an LED through PWM on pin 9.

Two details worth noting. The ADC is read ten times and averaged, because a single reading jitters
by several counts and the LED visibly flickers as a result. And the input is mapped from the
200 to 800 range the potentiometer actually swings through on my board, not the theoretical
0 to 1023, then clamped. Mapping from the measured range rather than the nominal one gives full
brightness travel across the physical rotation.

## melody-player

Plays a melody on a piezo buzzer using `tone()`, with note frequencies defined as constants and
durations expressed as musical fractions (4 for a quarter note, 2 for a half). Each note is
followed by a short gap so consecutive identical notes are audibly separate rather than running
together.

---

## Hardware

- Arduino UNO R3
- 8x8 LED matrix, common cathode, rows through 1k resistors
- Electret microphone module on `A0`
- 10k potentiometer
- Piezo buzzer

## Running

Open any sketch folder in the Arduino IDE and upload. The sketch folder name matches the `.ino`
name, as the IDE requires. `mic-level-serial` is best viewed with the Serial Plotter at 9600 baud.

---

Rupert van Vuuren. BEng Electrical and Electronic Engineering, Stellenbosch University.
