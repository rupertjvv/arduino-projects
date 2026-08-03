void setup() {
  // Start the serial communication at 9600 baud rate
  Serial.begin(9600);
}

void loop() {
  // Read the raw analog value from the microphone
  int micValue = analogRead(A0);
  
  // Send the value to the computer
  Serial.println(micValue);
  
  // A tiny delay to keep the graph readable
  delay(10); 
}