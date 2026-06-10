import serial
import csv
import os
import time
import re
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURATION - Matching Arduino Settings
# ─────────────────────────────────────────────
PORT = "/dev/ttyUSB0"                    # ← Change to your ESP32 port
BAUD_RATE = 115200

# Sensor Settings (exactly as in Arduino code)
GAIN = 3                          # 0=1x, 1=3.7x, 2=16x, 3=64x
MODE = 3                          # 3 = Continuous reading of all channels
INTEGRATION_VALUE = 60            # Each unit = 2.8 ms → 60 * 2.8 = 168 ms
BULB_CURRENT = 2                  # 1 = 25 mA, 2 = 50 mA
LED_ENABLED = True

DURATION_SEC = 10                 # Total data collection time (seconds)
BASE_NAME = "AS7263"              # Base filename → AS72631, AS72632...
OUTPUT_DIR = r"/home/pratham/Arduino/spectrography/data_store"

# ─────────────────────────────────────────────
# SENSOR & PLOTTING CONFIG
# ─────────────────────────────────────────────
CHANNELS = ["R", "S", "T", "U", "V", "W"]
WAVELENGTHS = {"R": 610, "S": 680, "T": 730, "U": 760, "V": 810, "W": 860}
CH_COLORS = {
    "R": "#e63946", "S": "#f4a261", "T": "#2a9d8f",
    "U": "#457b9d", "V": "#6a4c93", "W": "#1d3557"
}

# ─────────────────────────────────────────────
# AUTO-INCREMENT LABEL
# ─────────────────────────────────────────────
def next_label(folder: str, base: str) -> str:
    pattern = re.compile(rf"^{re.escape(base)}(\d+)\.csv$", re.IGNORECASE)
    highest = 0
    try:
        for fname in os.listdir(folder):
            m = pattern.match(fname)
            if m:
                highest = max(highest, int(m.group(1)))
    except FileNotFoundError:
        pass
    return f"{base}{highest + 1}"


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def f_to_c(fahrenheit: float) -> float:
    return round((fahrenheit - 32) * 5 / 9, 2)


def parse_line(line: str):
    """Parse exact Arduino output format"""
    values = {}
    for ch in CHANNELS:
        m = re.search(rf"{ch}:\s*([\d.]+)", line)
        if m:
            values[ch] = float(m.group(1))

    m = re.search(r"Temp:\s*([\d.]+)\s*F", line)
    if m:
        values["Temp_C"] = f_to_c(float(m.group(1)))

    if len(values) == len(CHANNELS) + 1:
        return values
    return None


def compute_average(rows: list) -> dict:
    if not rows:
        return {}
    keys = list(rows[0].keys())
    return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in keys}


# ─────────────────────────────────────────────
# PLOTTING FUNCTION
# ─────────────────────────────────────────────
def plot_results(all_rows: list, avg: dict, label: str, plot_file: str):
    total = len(all_rows)
    fig = plt.figure(figsize=(16, 10), facecolor="#f8f9fa")
    gs = gridspec.GridSpec(2, 1, hspace=0.45, figure=fig)

    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor("#ffffff")
    for ch in CHANNELS:
        y = [r[ch] for r in all_rows]
        ax1.plot(range(1, total + 1), y, color=CH_COLORS[ch], linewidth=1.1,
                 label=f"{ch} ({WAVELENGTHS[ch]} nm)")

    ax1.set_title(f"Raw AS7263 NIR Readings — {total} Samples ({DURATION_SEC}s window)",
                  fontsize=13, fontweight="bold", pad=12)
    ax1.set_xlabel("Sample Number")
    ax1.set_ylabel("Calibrated Value")
    ax1.legend(loc="upper right", ncol=3, fontsize=9.5)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    # Bar chart of averages
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor("#ffffff")
    ch_labels = [f"{ch}\n{WAVELENGTHS[ch]} nm" for ch in CHANNELS]
    ch_avgs = [avg[ch] for ch in CHANNELS]

    bars = ax2.bar(ch_labels, ch_avgs, color=[CH_COLORS[ch] for ch in CHANNELS],
                   edgecolor="white", linewidth=1.3, width=0.6)

    for bar, val in zip(bars, ch_avgs):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(ch_avgs)*0.01,
                 f"{val:.3f}", ha="center", va="bottom", fontweight="bold", fontsize=10)

    ax2.set_title(f"Channel Averages (n = {total})", fontsize=13, fontweight="bold", pad=12)
    ax2.set_ylabel("Average Calibrated Value")
    ax2.set_ylim(0, max(ch_avgs) * 1.18)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    ax2.text(0.98, 0.96, f"Avg Temp: {avg.get('Temp_C', 0):.1f} °C   |   GAIN: 64x   |   Int.Time: {INTEGRATION_VALUE * 2.8:.0f}ms",
             transform=ax2.transAxes, ha="right", va="top", fontsize=10.5,
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#e9ecef"))

    fig.suptitle(f"AS7263 NIR Spectral Sensor — {label} | LED 25mA ON", 
                 fontsize=16, fontweight="bold", y=0.97)

    plt.savefig(plot_file, dpi=180, bbox_inches="tight")
    print(f"Plot saved → {plot_file}")
    plt.show()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    label = next_label(OUTPUT_DIR, BASE_NAME)

    raw_file = os.path.join(OUTPUT_DIR, f"{label}.csv")
    avg_file = os.path.join(OUTPUT_DIR, f"{label}avg.csv")
    plot_file = os.path.join(OUTPUT_DIR, f"{label}_plot.png")

    print(f"\n{'═' * 70}")
    print(f" AS7263 NIR SENSOR DATA COLLECTION")
    print(f"{'═' * 70}")
    print(f" Run Label       : {label}")
    print(f" Gain            : {GAIN} → 64x")
    print(f" Mode            : {MODE} (Continuous)")
    print(f" Integration Time: {INTEGRATION_VALUE} → {INTEGRATION_VALUE * 2.8:.0f} ms")
    print(f" Bulb Current    : {BULB_CURRENT} → 25 mA  (LED ON)")
    print(f" Duration        : {DURATION_SEC} seconds")
    print(f" Raw File        : {raw_file}")
    print(f" Average File    : {avg_file}")
    print(f"{'═' * 70}\n")

    header = CHANNELS + ["Temp_C"]
    all_rows = []

    print("Opening serial port...")
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=2)
        ser.reset_input_buffer()
        time.sleep(2.5)  # Give time for Arduino to boot and print "Ready"
    except Exception as e:
        print(f"[ERROR] Could not open port {PORT}: {e}")
        return

    # Simulate Arduino startup messages
    print("AS7263 Ready")
    print(f"GAIN = 64x ({GAIN})")
    print(f"MODE = {MODE} (Continuous)")
    print("LED = 25mA")
    print(f"Integration Time = {INTEGRATION_VALUE * 2.8:.0f} ms")
    print("-" * 50)

    deadline = time.time() + DURATION_SEC
    sample_count = 0

    print(f"Starting data collection for {DURATION_SEC} seconds...\n")

    while time.time() < deadline:
        raw = ser.readline().decode("utf-8", errors="ignore").strip()
        if not raw:
            continue

        reading = parse_line(raw)
        if reading is None:
            continue  # Skip invalid lines

        all_rows.append(reading)
        sample_count += 1

        print(f" #{sample_count:4d} | R={reading['R']:.2f}  S={reading['S']:.2f}  "
              f"T={reading['T']:.2f}  U={reading['U']:.2f}  V={reading['V']:.2f}  "
              f"W={reading['W']:.2f}  | Temp={reading['Temp_C']:.1f}°C  "
              f"| {deadline - time.time():.0f}s left")

    ser.close()
    print(f"\nCollection completed. {len(all_rows)} valid readings captured.")

    if not all_rows:
        print("[ERROR] No valid data received. Check wiring and port.")
        return

    avg = compute_average(all_rows)

    # Save Raw Data
    with open(raw_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Reading"] + header)
        writer.writeheader()
        for i, row in enumerate(all_rows, 1):
            writer.writerow({"Reading": i, **row})

    # Save Average
    with open(avg_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Label", "N_samples", "Timestamp"] + header)
        writer.writeheader()
        writer.writerow({
            "Label": label,
            "N_samples": len(all_rows),
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **avg
        })

    # Console Summary
    print("\n" + "─" * 60)
    print("FINAL CHANNEL AVERAGES")
    print("─" * 60)
    for ch in CHANNELS:
        print(f" {ch} ({WAVELENGTHS[ch]} nm) : {avg[ch]:.4f}")
    print(f" Temperature              : {avg['Temp_C']:.2f} °C")
    print("─" * 60)

    # Generate Plot
    print("\nGenerating plot...")
    plot_results(all_rows, avg, label, plot_file)

    print(f"\n✅ All tasks completed successfully!")
    print(f"   Raw data    → {raw_file}")
    print(f"   Average     → {avg_file}")
    print(f"   Plot        → {plot_file}")


if __name__ == "__main__":
    main()
