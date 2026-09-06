// Define note frequencies (Hz)
#define NOTE_C4  262
#define NOTE_D4  294
#define NOTE_E4  330
#define NOTE_F4  349
#define NOTE_G4  392
#define NOTE_A4  440
#define NOTE_B4  494
#define NOTE_C5  523

int buzzerPin = 8;

// Melody: notes and durations (4 = quarter, 8 = eighth)
int melody[] = {
  NOTE_C4, NOTE_C4, NOTE_G4, NOTE_G4,
  NOTE_A4, NOTE_A4, NOTE_G4,
  NOTE_F4, NOTE_F4, NOTE_E4, NOTE_E4,
  NOTE_D4, NOTE_D4, NOTE_C4
};

int durations[] = {
  4, 4, 4, 4,
  4, 4, 2,
  4, 4, 4, 4,
  4, 4, 2
};

void setup() {
  // Play melody once on startup
  for (int i = 0; i < 14; i++) {
    int duration = 1000 / durations[i];
    tone(buzzerPin, melody[i], duration);

    // Small gap between notes so they sound separate
    delay(duration * 1.3);
    noTone(buzzerPin);
  }
}

void loop() {
  // Nothing here, plays once on startup
  // Change to put the for loop here if you want it to repeat
}