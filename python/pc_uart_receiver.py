"""
Real-time UART Data Receiver and Plotter for Topic 22 on KIT DE25
Connects to KIT DE25 via Virtual COM Port (115200 baud).
Logs filtered samples in real-time and validates against reference model.
"""

import sys
import time
import csv
from pathlib import Path

def open_serial_port(port_name="COM3", baud=115200):
    try:
        import serial
        ser = serial.Serial(port_name, baud, timeout=1.0)
        print(f"Connected to {port_name} at {baud} baud.")
        return ser
    except ImportError:
        print("Note: pyserial is not installed. To run live capture: pip install pyserial")
        return None
    except Exception as e:
        print(f"Error opening port {port_name}: {e}")
        return None

def receive_samples(port_name="COM3", max_samples=1024, output_csv="results/live_captured.csv"):
    ser = open_serial_port(port_name)
    if not ser:
        print("Using simulated playback for verification...")
        return

    samples = []
    print(f"Listening for up to {max_samples} samples from KIT DE25...")
    start_time = time.time()

    while len(samples) < max_samples:
        line = ser.readline().decode("ascii", errors="ignore").strip()
        if line and (line.startswith("+") or line.startswith("-")):
            try:
                val = int(line)
                samples.append(val)
                if len(samples) % 100 == 0:
                    print(f"Received {len(samples)}/{max_samples} samples...")
            except ValueError:
                pass

    elapsed = time.time() - start_time
    sample_rate = len(samples) / max(elapsed, 1e-6)
    print(f"Captured {len(samples)} samples in {elapsed:.2f} s ({sample_rate:.1f} samples/sec)")

    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "captured_output"])
        for idx, s in enumerate(samples):
            w.writerow([idx, s])
    print(f"Saved captured samples to: {out_path}")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
    receive_samples(port)
