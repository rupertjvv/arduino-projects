// --- Pin Definitions ---
// The 8 Row Pins (Anodes) connected via 1k resistors
// Matrix Pins: 9, 14, 8, 12, 1, 7, 2, 5
int rowPins[8] = {2, 3, 4, 5, 6, 7, 8, 9}; 

// The 8 Column Pins (Cathodes) connected directly with jumper wires
// Matrix Pins: 13, 3, 4, 10, 6, 11, 15, 16
int colPins[8] = {10, 11, 12, 13, A1, A2, A3, A4}; 

// Array to store the height of each of the 8 columns for the scrolling effect
int colHeights[8] = {0, 0, 0, 0, 0, 0, 0, 0};

void setup() {
  // Initialize all row and column pins as outputs
  for (int i = 0; i < 8; i++) {
    pinMode(rowPins[i], OUTPUT);
    pinMode(colPins[i], OUTPUT);
    
    // Turn all rows OFF (LOW)
    digitalWrite(rowPins[i], LOW);
    
    // Turn all columns OFF (HIGH for common cathode logic)
    digitalWrite(colPins[i], HIGH); 
  }
}

void loop() {
 // Replace your sampling block with this:
int maxVal = 0;
int minVal = 1024;
unsigned long startTime = millis();

// Sample for 50ms instead of just 20 rapid reads
while (millis() - startTime < 50) {
  int val = analogRead(A0);
  if (val > maxVal) maxVal = val;
  if (val < minVal) minVal = val;
}
  
  // Calculate amplitude (the volume)
  int peakToPeak = maxVal - minVal;
  
  // Map the volume to a value between 0 and 8 (the 8 rows)
  // TWEAK THIS: Change '300' if the matrix is too sensitive or not sensitive enough!
  int newVolumeLevel = map(peakToPeak, 0, 300, 0, 8); 

  // Constrain the value just in case a loud noise spikes it above 8
  newVolumeLevel = constrain(newVolumeLevel, 0, 8);

  // 2. Shift the old column heights to the left to create the scrolling effect
  for (int i = 0; i < 7; i++) {
    colHeights[i] = colHeights[i + 1];
  }
  
  // 3. Put the new volume level in the right-most column
  colHeights[7] = newVolumeLevel;

  // 4. Multiplex the display (draw the frame)
  // We run this inner drawing loop a few times to slow down the scrolling speed.
  // Increase the '5' if it scrolls too fast, decrease it if it is too slow.
  for (int frames = 0; frames < 5; frames++) { 
    for (int c = 0; c < 8; c++) {
      
      // Turn the current column ON (LOW means current can sink into this pin)
      digitalWrite(colPins[c], LOW); 

      // Turn the necessary rows ON based on the height stored for this column
      for (int r = 0; r < 8; r++) {
        if (r < colHeights[c]) {
          digitalWrite(rowPins[r], HIGH); // Turn row ON
        } else {
          digitalWrite(rowPins[r], LOW);  // Turn row OFF
        }
      }

      // Leave the LEDs on for 1 millisecond so the human eye registers them
      delay(1); 
      
      // Turn the current column OFF before moving to the next one
      digitalWrite(colPins[c], HIGH); 
    }
  }
}