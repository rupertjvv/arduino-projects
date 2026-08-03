// --- Pin Definitions ---
// The 8 Row Pins (Anodes) - Connected via 1k resistors
int rowPins[8] = {2, 3, 4, 5, 6, 7, 8, 9}; 

// The 8 Column Pins (Cathodes) - Connected directly
int colPins[8] = {10, 11, 12, 13, A1, A2, A3, A4}; 

void setup() {
  // Set all pins as outputs
  for (int i = 0; i < 8; i++) {
    pinMode(rowPins[i], OUTPUT);
    pinMode(colPins[i], OUTPUT);
    
    // Turn everything OFF to start
    digitalWrite(rowPins[i], LOW);   // Rows OFF (LOW)
    digitalWrite(colPins[i], HIGH);  // Columns OFF (HIGH)
  }
}

void loop() {
  // Sweep through each column (left to right)
  for (int c = 0; c < 8; c++) {
    digitalWrite(colPins[c], LOW); // Turn the current column ON
    
    // Sweep through each row in that column (top to bottom)
    for (int r = 0; r < 8; r++) {
      digitalWrite(rowPins[r], HIGH); // Turn the single LED ON
      
      delay(100);                     // Wait 100 milliseconds so you can easily track it
      
      digitalWrite(rowPins[r], LOW);  // Turn the single LED OFF
    }
    
    digitalWrite(colPins[c], HIGH); // Turn the current column OFF before moving on
  }
}