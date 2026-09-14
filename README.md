# Arduino Projects

Small Arduino UNO R3 sketches I wrote while learning embedded programming, built and tested on a
home bench. The theme running through them is driving and reading hardware directly: multiplexing
a display faster than the eye can follow, sampling an analogue signal properly rather than taking
a single reading, and calibrating against what a sensor actually does rather than its nominal
range.

## The sketches

**audio-visualiser-8x8** is the main one. An electret microphone on `A0` drives a scrolling level
meter on an 8x8 LED matrix. A single `analogRead` of audio catches the waveform at an arbitrary
point in its cycle, so the sketch tracks the running minimum and maximum over a 50 ms window and
uses the peak-to-peak spread instead. All 64 LEDs share 8 row and 8 column pins, so the display
loop lights one column at a time for 1 ms and leans on persistence of vision. Column heights sit
in an 8-element buffer that shifts left each frame, which is what makes it scroll.

**led-matrix-sweep-test** lights one LED at a time across the matrix, 100 ms each. I wrote it
first to prove out the wiring before anything harder depended on it.

**mic-level-serial** reads the microphone and streams raw values over serial at 9600 baud. This is
how I worked out the amplitude range the mic actually produces.

**pot-led-dimmer** fades an LED with PWM on pin 9. The ADC is read ten times and averaged, because
a single reading jitters enough to make the LED visibly flicker.

**melody-player** plays a melody on a piezo buzzer with `tone()`, note durations written as
musical fractions. Each note is followed by a short gap so repeated notes stay audibly separate.

## Wiring

Rows are anodes driven high and columns are cathodes driven low, so a pixel lights when its row is
HIGH and its column is LOW.

| Function | Arduino pins | Notes |
|---|---|---|
| Matrix rows (anodes) | `2, 3, 4, 5, 6, 7, 8, 9` | each through a 1k resistor |
| Matrix columns (cathodes) | `10, 11, 12, 13, A1, A2, A3, A4` | driven low to enable |
| Microphone | `A0` | visualiser and mic-level sketches |
| Potentiometer | `A0` | dimmer sketch |
| LED (PWM) | `9` | dimmer sketch |
| Piezo buzzer | `8` | melody sketch |

Matrix pin order varies between modules, so run `led-matrix-sweep-test` first. A wrong pin shows
up straight away instead of surfacing later as a scrambled display.

## Two values to change for your hardware

- `map(peakToPeak, 0, 300, 0, 8)` in the visualiser assumes the mic swings about 300 counts
  peak-to-peak at normal volume.
- `map(potValue, 200, 800, 0, 255)` in the dimmer matches the travel my potentiometer really has,
  not the nominal 0 to 1023.

## tools/mic_calibrate.py

That 300 depends on the microphone module, its gain trimmer, the supply rail and how far away you
are. The Serial Plotter only shows raw readings, while the sketch acts on the peak-to-peak spread
over 50 ms, so this reads the `mic-level-serial` stream, reproduces that windowing on the host and
prints a `map()` line to paste back.

```
python3 tools/mic_calibrate.py --port /dev/cu.usbmodem1101
```

Two things came out of it that the plotter does not show. The noise floor is not zero, so mapping
from 0 leaves the bottom row permanently lit. And the stream is slower than the 10 ms delay
suggests, nearer 15 ms once 9600 baud is accounted for, which is why the visualiser samples on the
board rather than streaming readings to a host.

Live capture needs `pyserial`. Replay and the tests need neither it nor a board:

```
python3 -m unittest discover -s tools
```

## Running

Open a sketch folder in the Arduino IDE and upload. The folder name matches the `.ino` name, as the
IDE requires. `mic-level-serial` is best viewed with the Serial Plotter at 9600 baud.

Rupert van Vuuren. BEng Electrical and Electronic Engineering, Stellenbosch University.
