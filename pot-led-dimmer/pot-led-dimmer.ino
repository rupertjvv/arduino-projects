#define POT_PIN  A0
#define LED_PIN  9

int readSmoothed() {
  long total = 0;
  for (int i = 0; i < 10; i++) {
    total += analogRead(POT_PIN);
    delay(2);
  }
  return total / 10; // average of 10 readings
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int potValue = readSmoothed();
  
  // map from YOUR actual range instead of 0-1023
  int brightness = map(potValue, 200, 800, 0, 255);
  brightness = constrain(brightness, 0, 255); // clamp to safe range
  
  analogWrite(LED_PIN, brightness);

  Serial.print("Pot: ");
  Serial.print(potValue);
  Serial.print("  Brightness: ");
  Serial.println(brightness);

  delay(10);
}