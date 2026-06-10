# ESP32 Material Segregation System

This project implements an automated material segregation system using an ESP32 microcontroller, an AS7263 NIR (Near-Infrared) spectral sensor, and machine learning. The system identifies materials like Wood, Metal, and Plastic based on their spectral signatures and sorts them using a conveyor belt and servo-controlled arms.

## Features

- **Spectral Analysis**: Uses the AS7263 NIR sensor to capture spectral data across 6 channels (610nm to 860nm).
- **Machine Learning**: Random Forest Classifier for high-accuracy material identification.
- **Automated Sorting**: Integrated control for DC motors (conveyor) and Servo motors (sorting mechanisms).
- **Data Pipeline**: Full pipeline from raw data extraction to model training and live prediction.

## Hardware Requirements

- **Microcontroller**: ESP32
- **Spectral Sensor**: AS7263 NIR Spectral Sensor
- **Object Detection**: IR Sensor
- **Actuators**:
  - DC Motor with L298N (or similar) driver for the conveyor belt.
  - 2x Servo Motors for sorting arms.
- **Power Supply**: Appropriate power for ESP32 and motors.

## Software Components

### 1. Firmware (`main.ino`)
The Arduino/C++ code for the ESP32. It handles:
- Object detection via IR sensor.
- Controlling the AS7263 sensor.
- Managing the conveyor motor and sorting servos.
- (Optional) On-device inference if integrated with Edge Impulse.

### 2. Data Extraction (`data_extraction.py`)
A Python script to collect training data.
- Connects to the ESP32 via Serial.
- Captures multiple samples of a material.
- Calculates averages and saves data to CSV.
- Generates plots for visual analysis.

### 3. Model Training (`ml_train.py`)
Trains the machine learning model.
- Performs feature engineering (ratios, gradients, statistical profiles).
- Balances classes using oversampling.
- Trains a Random Forest Classifier.
- Exports the model as `spectroscopy_model.pkl`.

### 4. Live Prediction (`ml_pred.py`)
Real-time material identification.
- Loads the trained `.pkl` model.
- Streams data from the ESP32.
- Applies the same feature engineering as the training script.
- Outputs predicted material and confidence level.

## Getting Started

### Hardware Setup
1. Connect the AS7263 sensor to the ESP32 via I2C (SDA: 21, SCL: 22).
2. Connect the IR sensor to pin 19.
3. Connect Servo 1 to pin 18 and Servo 2 to pin 17.
4. Connect the DC motor driver to pins 25, 26, and 27.

### Software Setup
1. **Flash ESP32**: Upload `main.ino` using the Arduino IDE. Ensure you have the `AS726X` and `ESP32Servo` libraries installed.
2. **Install Python Dependencies**:
   ```bash
   pip install pyserial pandas numpy scikit-learn matplotlib joblib
   ```
3. **Collect Data**: Use `data_extraction.py` to gather spectral data for different materials.
4. **Train Model**: Run `ml_train.py` to create your classifier.
5. **Run Prediction**: Execute `ml_pred.py` to see the system in action.

## Sorting Logic
- **Plastic**: Servo 1 moves to 180°.
- **Miscellaneous/Metal**: Servo 1 moves to 0° or Servo 2 moves to 60° depending on the configuration.
- **Conveyor**: Starts when an object is detected and stops after sorting and object removal.
