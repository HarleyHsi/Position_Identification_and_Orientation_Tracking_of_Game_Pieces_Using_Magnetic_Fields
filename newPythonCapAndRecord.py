import serial
import tkinter as tk
from tkinter import ttk, simpledialog
from threading import Thread, Lock
import time
import csv
from datetime import datetime

# Configuration 
SERIAL_PORT  = "COM4"
BAUD_RATE    = 115200
NUM_SENSORS  = 9
CAL_DURATION = 10.0   # seconds to collect calibration data
CAPTURE_MAX  = 10    # number of samples per capture burst



class SensorWindow:
    def __init__(self, root, sensor_index):
        self.root          = root
        self.index         = sensor_index
        self.offset        = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.calibrating   = False
        self.cal_samples   = []
        self.lock          = Lock()
        self.recording     = False
        self.record_file   = None
        self.record_writer = None

        # Capture state 
        self.capturing        = False
        self.capture_data     = []
        self.capture_filename = None

        # Window setup 
        self.win = tk.Toplevel(root)
        self.win.title(f"Sensor {sensor_index} — MLX90393")
        self.win.geometry("380x430")
        self.win.resizable(True, True)
        self.win.rowconfigure(0, weight=1)
        self.win.columnconfigure(0, weight=1)

        x_offset = 20 + sensor_index * 300
        self.win.geometry(f"+{x_offset}+100")

        # Title 
        tk.Label(self.win, text=f"Sensor {sensor_index}",
                 font=("Helvetica", 14, "bold")).pack(pady=(10, 2))

        self.status_var = tk.StringVar(value="Waiting...")
        tk.Label(self.win, textvariable=self.status_var,
                 fg="grey", font=("Helvetica", 9)).pack()

        # Data table 
        frame = tk.Frame(self.win)
        frame.pack(pady=8)

        headers = ["Axis", "Raw (µT)", "Calibrated (µT)"]
        for col, header in enumerate(headers):
            tk.Label(frame, text=header,
                     font=("Helvetica", 9, "bold"),
                     width=13, anchor="center").grid(row=0, column=col, padx=3)

        self.raw_vars = {}
        self.cal_vars = {}
        for row, axis in enumerate(["X", "Y", "Z"], start=1):
            tk.Label(frame, text=axis, font=("Helvetica", 10),
                     width=13, anchor="center").grid(row=row, column=0, padx=3, pady=2)

            raw_var = tk.StringVar(value="—")
            tk.Label(frame, textvariable=raw_var, font=("Courier", 10),
                     width=13, anchor="center").grid(row=row, column=1, padx=3, pady=2)

            cal_var = tk.StringVar(value="—")
            tk.Label(frame, textvariable=cal_var, font=("Courier", 10),
                     width=13, anchor="center", fg="#007700").grid(row=row, column=2, padx=3, pady=2)

            self.raw_vars[axis] = raw_var
            self.cal_vars[axis] = cal_var

        # Offset display 
        self.offset_var = tk.StringVar(value="Offsets: not calibrated")
        tk.Label(self.win, textvariable=self.offset_var,
                 fg="#888800", font=("Helvetica", 8)).pack()

        # Calibration progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.win,
                                            variable=self.progress_var,
                                            maximum=100, length=220)
        self.progress_bar.pack(pady=4)

        # Calibrate button 
        self.cal_btn = tk.Button(self.win, text="⟳ Calibrate This Sensor",
                                 command=self.start_calibration,
                                 bg="#4a90d9", fg="white",
                                 font=("Helvetica", 9, "bold"),
                                 relief="flat", padx=8, pady=4)
        self.cal_btn.pack(pady=4)

        # Record button 
        self.rec_btn = tk.Button(self.win, text="⏺ Start Recording",
                                 command=self.toggle_recording,
                                 bg="#228B22", fg="white",
                                 font=("Helvetica", 9, "bold"),
                                 relief="flat", padx=8, pady=4)
        self.rec_btn.pack(pady=(4, 0))

        # Recording status label
        self.rec_status_var = tk.StringVar(value="")
        tk.Label(self.win, textvariable=self.rec_status_var,
                 fg="#228B22", font=("Helvetica", 8)).pack()

        # Capture button 
        self.cap_btn = tk.Button(self.win,
                                 text=f"📷 Capture ({CAPTURE_MAX} samples)",
                                 command=self.start_capture,
                                 bg="#7B3F9E", fg="white",
                                 font=("Helvetica", 9, "bold"),
                                 relief="flat", padx=8, pady=4)
        self.cap_btn.pack(pady=(4, 0))

        # Capture status label
        self.cap_status_var = tk.StringVar(value="")
        tk.Label(self.win, textvariable=self.cap_status_var,
                 fg="#7B3F9E", font=("Helvetica", 8)).pack()

        # Timestamp 
        self.ts_var = tk.StringVar(value="")
        tk.Label(self.win, textvariable=self.ts_var,
                 fg="grey", font=("Helvetica", 8)).pack()

    # Filename dialog
    def _ask_filename(self, default_name):
        # Prompt to type a filename.
        name = simpledialog.askstring(
            "Save As",
            "Enter filename (without .csv extension):",
            initialvalue=default_name,
            parent=self.win
        )
        if name is None:
            return None
        name = name.strip()
        if not name:
            return None
        if not name.lower().endswith(".csv"):
            name += ".csv"
        return name

    # Calibration logic 
    def start_calibration(self):
        with self.lock:
            self.cal_samples = []
            self.calibrating = True

        self.cal_btn.config(state="disabled", text="Calibrating...")
        self.status_var.set("⏳ Collecting calibration data...")
        self.progress_var.set(0)

        self._cal_start_time = time.time()
        self.win.after(100, self._update_calibration_progress)

    def _update_calibration_progress(self):
        elapsed = time.time() - self._cal_start_time
        progress = min((elapsed / CAL_DURATION) * 100, 100)
        self.progress_var.set(progress)

        if elapsed >= CAL_DURATION:
            self._finish_calibration()
        else:
            self.win.after(100, self._update_calibration_progress)

    def _finish_calibration(self):
        with self.lock:
            self.calibrating = False
            samples = list(self.cal_samples)

        if len(samples) == 0:
            self.status_var.set("⚠ No samples collected!")
            self.cal_btn.config(state="normal", text="⟳ Calibrate This Sensor")
            return

        self.offset["X"] = sum(s[0] for s in samples) / len(samples)
        self.offset["Y"] = sum(s[1] for s in samples) / len(samples)
        self.offset["Z"] = sum(s[2] for s in samples) / len(samples)

        sample_count = len(samples)
        self.offset_var.set(
            f"Offsets  X:{self.offset['X']:+.3f}  "
            f"Y:{self.offset['Y']:+.3f}  "
            f"Z:{self.offset['Z']:+.3f}  "
            f"({sample_count} samples)"
        )
        self.status_var.set(f"✔ Calibrated ({sample_count} samples)")
        self.progress_var.set(100)
        self.cal_btn.config(state="normal", text="⟳ Re-Calibrate")

    # Recording logic 
    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self, filename=None):
        if filename is None:
            default  = f"sensor_{self.index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            filename = self._ask_filename(default)
            if filename is None:
                return   

        self.record_file   = open(filename, "w", newline="")
        self.record_writer = csv.writer(self.record_file)
        self.record_writer.writerow([
            "timestamp", "sensor_id",
            "x_raw", "y_raw", "z_raw",
            "x_cal", "y_cal", "z_cal"
        ])

        self.recording = True
        self.rec_btn.config(text="⏹ Stop Recording", bg="#cc0000")
        self.rec_status_var.set(f"Recording → {filename}")

    def stop_recording(self):
        self.recording = False

        if self.record_file:
            self.record_file.flush()
            self.record_file.close()
            self.record_file   = None
            self.record_writer = None

        self.rec_btn.config(text="⏺ Start Recording", bg="#228B22")
        self.rec_status_var.set("Recording saved ✔")

    def write_record(self, x, y, z, cx, cy, cz):
        """Called during _apply() if recording is active."""
        if self.recording and self.record_writer:
            self.record_writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                self.index,
                f"{x:.4f}", f"{y:.4f}", f"{z:.4f}",
                f"{cx:.4f}", f"{cy:.4f}", f"{cz:.4f}"
            ])
            self.record_file.flush()

    # Capture logic
    def start_capture(self, filename=None):
        if self.capturing:
            return  

        if filename is None:
            default  = f"capture_sensor_{self.index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            filename = self._ask_filename(default)
            if filename is None:
                return  

        self.capture_filename = filename
        self.capture_data     = []
        self.capturing        = True

        self.cap_btn.config(state="disabled",
                            text=f"📷 Capturing 0/{CAPTURE_MAX}...")
        self.cap_status_var.set(f"Capturing → {filename}")

    def _add_capture_sample(self, x, y, z, cx, cy, cz):
        if not self.capturing:
            return

        self.capture_data.append((
            datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            self.index,
            f"{x:.4f}", f"{y:.4f}", f"{z:.4f}",
            f"{cx:.4f}", f"{cy:.4f}", f"{cz:.4f}"
        ))

        count = len(self.capture_data)
        self.cap_btn.config(text=f"📷 Capturing {count}/{CAPTURE_MAX}...")

        if count >= CAPTURE_MAX:
            self._finish_capture()

    def _finish_capture(self):
        self.capturing = False

        try:
            with open(self.capture_filename, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "sensor_id",
                    "x_raw", "y_raw", "z_raw",
                    "x_cal", "y_cal", "z_cal"
                ])
                writer.writerows(self.capture_data)
            self.cap_status_var.set(f"Capture saved ✔ → {self.capture_filename}")
        except Exception as e:
            self.cap_status_var.set(f"⚠ Save error: {e}")

        self.capture_data     = []
        self.capture_filename = None
        self.cap_btn.config(state="normal",
                            text=f"📷 Capture ({CAPTURE_MAX} samples)")

    def update(self, x_str, y_str, z_str):
        self.win.after(0, self._apply, x_str, y_str, z_str)

    def _apply(self, x_str, y_str, z_str):
        if x_str == "ERROR":
            self.status_var.set("⚠ Read failed")
            for var in list(self.raw_vars.values()) + list(self.cal_vars.values()):
                var.set("ERROR")
            return

        x, y, z = float(x_str), float(y_str), float(z_str)

        if self.calibrating:
            with self.lock:
                self.cal_samples.append((x, y, z))

        # Apply offsets
        cx = x - self.offset["X"]
        cy = y - self.offset["Y"]
        cz = z - self.offset["Z"]

        self.write_record(x, y, z, cx, cy, cz)
        self._add_capture_sample(x, y, z, cx, cy, cz)

        self.raw_vars["X"].set(f"{x:+.4f}")
        self.raw_vars["Y"].set(f"{y:+.4f}")
        self.raw_vars["Z"].set(f"{z:+.4f}")

        self.cal_vars["X"].set(f"{cx:+.4f}")
        self.cal_vars["Y"].set(f"{cy:+.4f}")
        self.cal_vars["Z"].set(f"{cz:+.4f}")

        if not self.calibrating:
            self.status_var.set("● Live")

        self.ts_var.set(f"Updated: {time.strftime('%H:%M:%S')}")


# Control window 
def create_control_window(root, sensor_windows):
    ctrl = tk.Toplevel(root)
    ctrl.title("Calibration Control")
    ctrl.geometry("270x230")
    ctrl.geometry("+20+380")
    ctrl.resizable(True, True)
    ctrl.rowconfigure(0, weight=1)
    ctrl.columnconfigure(0, weight=1)

    tk.Label(ctrl, text="Control all sensors simultaneously",
             font=("Helvetica", 9)).pack(pady=(10, 4))

    # Calibrate ALL
    def calibrate_all():
        for sw in sensor_windows:
            sw.start_calibration()

    tk.Button(ctrl, text="⟳ Calibrate ALL Sensors",
              command=calibrate_all,
              bg="#cc5500", fg="white",
              font=("Helvetica", 10, "bold"),
              relief="flat", padx=10, pady=6).pack(pady=4)

    # Record ALL
    def toggle_record_all():
        any_recording = any(sw.recording for sw in sensor_windows)
        if not any_recording:
            base = simpledialog.askstring(
                "Save As",
                "Enter base filename for all sensors (without .csv):",
                initialvalue=f"all_sensors_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                parent=ctrl
            )
            if not base or not base.strip():
                return
            base = base.strip()
            for sw in sensor_windows:
                sw.start_recording(filename=f"{base}_sensor_{sw.index}.csv")
            rec_all_btn.config(text="⏹ Stop Recording ALL", bg="#cc0000")
        else:
            for sw in sensor_windows:
                sw.stop_recording()
            rec_all_btn.config(text="⏺ Record ALL Sensors", bg="#228B22")

    rec_all_btn = tk.Button(ctrl, text="⏺ Record ALL Sensors",
                            command=toggle_record_all,
                            bg="#228B22", fg="white",
                            font=("Helvetica", 10, "bold"),
                            relief="flat", padx=10, pady=6)
    rec_all_btn.pack(pady=4)

    # Capture ALL 
    def capture_all():
        base = simpledialog.askstring(
            "Save As",
            "Enter base filename for all sensors (without .csv):",
            initialvalue=f"capture_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            parent=ctrl
        )
        if not base or not base.strip():
            return
        base = base.strip()
        for sw in sensor_windows:
            sw.start_capture(filename=f"{base}_sensor_{sw.index}.csv")

    tk.Button(ctrl, text=f"📷 Capture ALL ({CAPTURE_MAX} samples)",
              command=capture_all,
              bg="#7B3F9E", fg="white",
              font=("Helvetica", 10, "bold"),
              relief="flat", padx=10, pady=6).pack(pady=4)


# Serial reader thread
def serial_reader(port, baud, windows):
    try:
        ser = serial.Serial(port, baud, timeout=2)
        print(f"Connected to {port}")
    except serial.SerialException as e:
        print(f"Could not open port: {e}")
        return

    while True:
        try:
            raw = ser.readline().decode("utf-8", errors="replace").strip()
            if not raw.startswith("S"):
                continue
            parts = raw.split(",")
            if len(parts) != 4:
                continue
            idx = int(parts[0][1:])
            if 0 <= idx < NUM_SENSORS:
                windows[idx].update(parts[1], parts[2], parts[3])
        except Exception as e:
            print(f"Read error: {e}")
            time.sleep(0.5)


# Main
def main():
    root = tk.Tk()
    root.withdraw()

    sensor_windows = [SensorWindow(root, i) for i in range(NUM_SENSORS)]
    create_control_window(root, sensor_windows)

    t = Thread(target=serial_reader,
               args=(SERIAL_PORT, BAUD_RATE, sensor_windows),
               daemon=True)
    t.start()

    root.mainloop()

if __name__ == "__main__":
    main()