import serial
import pickle
import numpy as np
import re
import time

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SERIAL_PORT = '/dev/ttyUSB0'  
BAUD_RATE = 115200
MODEL_PATH = '/home/pratham/Arduino/spectrography/spectroscopy_model.pkl'

# Matches your exact ESP32 layout: 
# "R: 299.15  S: 738.97  T: 169.06  U: 158.33  V: 340.51  W: 220.52  Temp: 91.4 F"
DATA_PATTERN = re.compile(
    r"R:\s*([\d\.\-]+)\s+"
    r"S:\s*([\d\.\-]+)\s+"
    r"T:\s*([\d\.\-]+)\s+"
    r"U:\s*([\d\.\-]+)\s+"
    r"V:\s*([\d\.\-]+)\s+"
    r"W:\s*([\d\.\-]+)\s+"
    r"Temp:\s*([\d\.\-]+)\s*F"
)

def live_predict():
    print("Loading engineered machine learning model (WOOD, METAL, PLASTIC)...")
    try:
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
    except Exception as e:
        print(f"Error loading model: {e}. Make sure you run ml_train.py first!")
        return
    
    print(f"Connecting to ESP32 stream on {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Settle time for serial hardware connection
        print("Pipeline active! Listening for targets...\n")
    except Exception as e:
        print(f"Failed to open port: {e}")
        return

    while True:
        if ser.in_waiting > 0:
            try:
                raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw_line:
                    continue
                
                match = DATA_PATTERN.search(raw_line)
                if match:
                    # 1. Extract baseline raw measurements
                    raw_floats = [float(val) for val in match.groups()]
                    channels = raw_floats[:6]   # [R, S, T, U, V, W]
                    temp_f = raw_floats[6]      # Read from stream for logging display
                    temp_c = (temp_f - 32) * 5 / 9
                    
                    # 2. Live Feature Engineering (Identical 21-feature structure to training)
                    total_intensity = sum(channels) if sum(channels) > 0 else 1
                    normalized_channels = [ch / total_intensity for ch in channels]
                    
                    # Gradients / Slopes
                    diffs = [
                        channels[0] - channels[1],  # R_S_diff
                        channels[1] - channels[2],  # S_T_diff
                        channels[2] - channels[3],  # T_U_diff
                        channels[3] - channels[4],  # U_V_diff
                        channels[4] - channels[5]   # V_W_diff
                    ]
                    
                    # Row-wise Statistical Context
                    spectral_mean = float(np.mean(channels))
                    spectral_std = float(np.std(channels, ddof=1)) # Sample standard deviation
                    spectral_max = float(np.max(channels))
                    
                    # Combine all 21 values in precise positional sequence (Temperature excluded)
                    live_features = (
                        channels + 
                        [total_intensity] + 
                        normalized_channels + 
                        diffs + 
                        [spectral_mean, spectral_std, spectral_max]
                    )
                    
                    input_data = np.array([live_features])
                    
                    # 3. Process with Classifier
                    prediction = model.predict(input_data)[0]
                    probabilities = model.predict_proba(input_data)
                    confidence = np.max(probabilities) * 100
                    
                    print(f"🟢 [Data Pack]: {channels} | Temp: {temp_c:.1f}°C")
                    print(f"   ➔ Detected Material: **{prediction.upper()}** ({confidence:.2f}% confidence)")
                    print("-" * 65)
                else:
                    # Echo non-data lines from your MCU boot loops or menus
                    if any(msg in raw_line for msg in ["AS7263", "GAIN", "MODE", "---"]):
                        print(f"ℹ️ [ESP32 Log]: {raw_line}")

            except ValueError:
                print(f"⚠️ Corrupted frame dropped: {raw_line}")
            except KeyboardInterrupt:
                print("\nShutting down prediction stream loop.")
                break
            except Exception as e:
                print(f"Unexpected operational pipeline failure: {e}")
                
    ser.close()

if __name__ == "__main__":
    live_predict()
