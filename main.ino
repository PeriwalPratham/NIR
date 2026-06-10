

/*
   ============================================================
   ESP32 + AS7263 + Edge Impulse Material Segregation System
   ============================================================

   FINAL LOGIC
   ------------------------------------------------------------

   1. System waits for object
   2. IR detects objec
   3. Wait 10 sec
   4. AS7263 scans material
   5. Edge Impulse predicts material
   6. FINAL RESULT printed
   7. DC motor starts
   8. Servo performs sorting action
   9. Servo returns to initial position
   10. DC motor CONTINUES RUNNING
   11. ONLY when IR continuously shows NO OBJECT
       for 2 seconds:
          -> Motor stops
          -> System resets
   12. Wait for next object

   ============================================================

   MATERIAL ACTIONS
   ------------------------------------------------------------

   Plastic
      Servo1 : 90 -> 180 -> 90

   Miscellaneous
      Servo1 : 90 -> 0 -> 90

   Bio
      Servo2 : 0 -> 60 -> 0

   ============================================================
*/

#include <Arduino.h>
#include <Wire.h>
#include "AS726X.h"
#include <ESP32Servo.h>

// ============================================================
// EDGE IMPULSE LIBRARY
// ============================================================



// ============================================================
// PIN DEFINITIONS
// ============================================================

#define IR_PIN         19

// Servo Pins
#define SERVO1_PIN     18
#define SERVO2_PIN     17

// Motor Pins
#define ENA            25
#define IN1            26
#define IN2            27

// I2C Pins
#define SDA_PIN        21
#define SCL_PIN        22

// ============================================================
// OBJECTS
// ============================================================

AS726X sensor;

Servo servo1;
Servo servo2;

// ============================================================
// VARIABLES
// ============================================================

float features[6];

int motorSpeed = 180;

bool waitingForScan = false;
bool processCompleted = false;

// Object removal confirmation
bool objectRemovedTimerStarted = false;

unsigned long detectTime = 0;
unsigned long objectRemovedTime = 0;

#define WAIT_TIME     10000
#define REMOVE_DELAY    50

// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  delay(2000);

  // ==========================================================
  // PIN MODES
  // ==========================================================

  pinMode(IR_PIN, INPUT);

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);

  // ==========================================================
  // ATTACH SERVOS
  // ==========================================================

  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);

  // Initial Positions
  servo1.write(90);
  servo2.write(0);

  // ==========================================================
  // STOP MOTOR
  // ==========================================================

  stopMotor();

  // ==========================================================
  // I2C START
  // ==========================================================

  Wire.begin(SDA_PIN, SCL_PIN);

  // ==========================================================
  // SENSOR INITIALIZATION
  // ==========================================================

  if (!sensor.begin(Wire, 3, 3)) {

    Serial.println("AS7263 NOT DETECTED!");

    while (1);
  }

  sensor.setIntegrationTime(60);

  sensor.setBulbCurrent(1);

  sensor.enableBulb();

  Serial.println("=================================");
  Serial.println("SYSTEM READY");
  Serial.println("WAITING FOR OBJECT...");
  Serial.println("=================================");
}

// ============================================================
// LOOP
// ============================================================

void loop() {

  bool objectDetected = (digitalRead(IR_PIN) == LOW);

  // ==========================================================
  // OBJECT DETECTED
  // ==========================================================

  if (objectDetected) {

    // Reset removal timer
    objectRemovedTimerStarted = false;

    // Start process only once
    if (!waitingForScan && !processCompleted) {

      Serial.println("Object Detected");

      Serial.println("Waiting 10 sec before scanning...");

      detectTime = millis();

      waitingForScan = true;
    }

    // ========================================================
    // AFTER 10 SEC
    // ========================================================

    if (waitingForScan &&
        millis() - detectTime >= WAIT_TIME) {

      waitingForScan = false;

      Serial.println("=================================");
      Serial.println("SCANNING MATERIAL");
      Serial.println("=================================");

      // ======================================================
      // TAKE SENSOR READINGS
      // ======================================================

      sensor.takeMeasurements();

      features[0] = sensor.getCalibratedR();
      features[1] = sensor.getCalibratedS();
      features[2] = sensor.getCalibratedT();
      features[3] = sensor.getCalibratedU();
      features[4] = sensor.getCalibratedV();
      features[5] = sensor.getCalibratedW();

      // ======================================================
      // PRINT SENSOR VALUES
      // ======================================================

      Serial.print("R: ");
      Serial.println(features[0]);

      Serial.print("S: ");
      Serial.println(features[1]);

      Serial.print("T: ");
      Serial.println(features[2]);

      Serial.print("U: ");
      Serial.println(features[3]);

      Serial.print("V: ");
      Serial.println(features[4]);

      Serial.print("W: ");
      Serial.println(features[5]);

      // ======================================================
      // CREATE SIGNAL
      // ======================================================

      signal_t signal;

      int err = numpy::signal_from_buffer(features, 6, &signal);

      if (err != 0) {

        Serial.println("Signal Error");

        return;
      }

      // ======================================================
      // RUN CLASSIFIER
      // ======================================================

      ei_impulse_result_t result = {0};

      EI_IMPULSE_ERROR res =
        run_classifier(&signal, &result, false);

      if (res != EI_IMPULSE_OK) {

        Serial.println("Classification Failed");

        return;
      }

      // ======================================================
      // PRINT PREDICTIONS
      // ======================================================

      Serial.println("Predictions:");

      for (size_t ix = 0;
           ix < EI_CLASSIFIER_LABEL_COUNT;
           ix++) {

        Serial.print(result.classification[ix].label);

        Serial.print(": ");

        Serial.println(
          result.classification[ix].value,
          5
        );
      }

      // ======================================================
      // FIND BEST LABEL
      // ======================================================

      String predictedLabel = "";

      float highestValue = 0;

      for (size_t ix = 0;
           ix < EI_CLASSIFIER_LABEL_COUNT;
           ix++) {

        if (result.classification[ix].value >
            highestValue) {

          highestValue =
            result.classification[ix].value;

          predictedLabel =
            String(result.classification[ix].label);
        }
      }

      // Convert label to lowercase
      predictedLabel.toLowerCase();

      // ======================================================
      // PRINT FINAL RESULT
      // ======================================================

      Serial.println("---------------------------------");

      Serial.print("FINAL RESULT: ");

      Serial.println(predictedLabel);

      Serial.println("---------------------------------");

      // ======================================================
      // START MOTOR
      // ======================================================

      Serial.println("Starting Conveyor Motor");

      setMotorCW();

      // ======================================================
      // PLASTIC
      // ======================================================

      if (predictedLabel == "plastic") {

        Serial.println("Plastic Detected");

        Serial.println("Servo1 : 90 -> 180 -> 90");

        moveServo1(90, 180);

        delay(2000);

        moveServo1(180, 90);
        delay(2000)
      }

      // ======================================================
      // MISCELLANEOUS
      // ======================================================

      else if (predictedLabel == "miscellaneous" ||
               predictedLabel == "miscellanious" ||
               predictedLabel == "miscallaneous" ||
               predictedLabel == "miscallanous"  ||
               predictedLabel == "misc") {

        Serial.println("Miscellaneous Detected");

        Serial.println("Servo1 : 90 -> 0 -> 90");

        moveServo1(90, 0);
        delay(2000);
        moveServo1(0, 90);
        delay(2000);
      }

      // ======================================================
      // BIO
      // ======================================================

      else if (predictedLabel == "metal") {

        Serial.println("Bio Detected");

        Serial.println("Servo2 : 0 -> 60 -> 0");

        moveServo2(0, 60);
        delay(2000);
        moveServo2(60, 0);
        delay(2000);
      }

      // ======================================================
      // UNKNOWN
      // ======================================================

      else {

        Serial.println("Unknown Material");
      }

      // ======================================================
      // PROCESS COMPLETE
      // ======================================================

      processCompleted = true;

      Serial.println("Sorting Completed");

      Serial.println("Motor Running...");

      Serial.println("Waiting for object removal...");
    }
  }

  // ==========================================================
  // OBJECT NOT DETECTED
  // ==========================================================

  else {

    // Only after full process
    if (processCompleted) {

      // Start removal timer once
      if (!objectRemovedTimerStarted) {

        objectRemovedTimerStarted = true;

        objectRemovedTime = millis();

        Serial.println("IR Lost Detection...");
      }

      // Confirm removal for stable duration
      if (millis() - objectRemovedTime >= REMOVE_DELAY) {

        Serial.println("Object Removed");

        // ====================================================
        // STOP MOTOR
        // ====================================================

        stopMotor();

        // ====================================================
        // RESET SERVOS
        // ====================================================

        servo1.write(90);
        servo2.write(0);

        // ====================================================
        // RESET FLAGS
        // ====================================================

        waitingForScan = false;
        processCompleted = false;
        objectRemovedTimerStarted = false;

        Serial.println("System Reset");

        Serial.println("=================================");
        Serial.println("WAITING FOR NEXT OBJECT...");
        Serial.println("=================================");
      }
    }
  }
}

// ============================================================
// SERVO1 MOVEMENT FUNCTION
// ============================================================

void moveServo1(int startAngle, int endAngle) {

  if (startAngle < endAngle) {

    for (int pos = startAngle;
         pos <= endAngle;
         pos++) {

      servo1.write(pos);

      delay(10);
    }

  } else {

    for (int pos = startAngle;
         pos >= endAngle;
         pos--) {

      servo1.write(pos);

      delay(10);
    }
  }
}

// ============================================================
// SERVO2 MOVEMENT FUNCTION
// ============================================================

void moveServo2(int startAngle, int endAngle) {

  if (startAngle < endAngle) {

    for (int pos = startAngle;
         pos <= endAngle;
         pos++) {

      servo2.write(pos);

      delay(10);
    }

  } else {

    for (int pos = startAngle;
         pos >= endAngle;
         pos--) {

      servo2.write(pos);

      delay(10);
    }
  }
}

// ============================================================
// MOTOR FUNCTIONS
// ============================================================

void setMotorCW() {

  digitalWrite(IN1, LOW);

  digitalWrite(IN2, HIGH);

  analogWrite(ENA, motorSpeed);
}

void stopMotor() {

  analogWrite(ENA, 0);
}
