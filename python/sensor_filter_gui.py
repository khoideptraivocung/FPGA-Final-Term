"""
================================================================================
Topic 22: Sensor Digital Filter (MA & FIR) - Real-Time FPGA GUI
Hardware: DE0-Nano (Cyclone IV E) <--> DOIT ESP32 DevKit V1 <--> PC GUI
Baud rate: 115200 bps
================================================================================
"""

import sys
import os
import time
import math
import random
import csv
import threading
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import serial
import serial.tools.list_ports

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


class SensorFilterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Topic 22: DE0-Nano FPGA Sensor Filter Controller & Visualizer")
        self.root.geometry("1200x820")
        self.root.minsize(1050, 720)

        # Serial state
        self.ser = None
        self.is_connected = False
        self.reader_thread = None
        self.is_streaming = False

        # Data buffers for real-time visualization (up to 1024 points)
        self.MAX_POINTS = 512
        self.raw_inputs = deque(maxlen=self.MAX_POINTS)
        self.filtered_outputs = deque(maxlen=self.MAX_POINTS)
        self.sample_indices = deque(maxlen=self.MAX_POINTS)
        self.current_idx = 0

        # Generator data
        self.generated_samples = []

        # Setup UI
        self._build_ui()
        self._refresh_ports()

        # Periodic GUI update timer (30 FPS)
        self.root.after(33, self._gui_update_loop)

    def _build_ui(self):
        # Top toolbar: Connection
        conn_frame = ttk.LabelFrame(self.root, text=" 1. Kết nối Cổng COM (ESP32 Bridge) ", padding=(10, 5))
        conn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(conn_frame, text="Cổng COM:").pack(side=tk.LEFT, padx=(0, 5))
        self.cbo_port = ttk.Combobox(conn_frame, width=15, state="readonly")
        self.cbo_port.pack(side=tk.LEFT, padx=5)

        btn_refresh = ttk.Button(conn_frame, text="Quét lại", command=self._refresh_ports)
        btn_refresh.pack(side=tk.LEFT, padx=5)

        ttk.Label(conn_frame, text="Baudrate:").pack(side=tk.LEFT, padx=(15, 5))
        self.cbo_baud = ttk.Combobox(conn_frame, width=10, state="readonly", values=["115200", "57600", "9600"])
        self.cbo_baud.current(0)
        self.cbo_baud.pack(side=tk.LEFT, padx=5)

        self.btn_connect = ttk.Button(conn_frame, text="Kết nối", command=self._toggle_connection)
        self.btn_connect.pack(side=tk.LEFT, padx=15)

        self.lbl_status = ttk.Label(conn_frame, text="● Chưa kết nối", foreground="red", font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # Main horizontal split
        main_split = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_split.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left panel: Controls (Tabs for Generator, File Loader, ROM Monitoring)
        left_panel = ttk.Frame(main_split, width=420)
        main_split.add(left_panel, weight=1)

        notebook = ttk.Notebook(left_panel)
        notebook.pack(fill=tk.BOTH, expand=True)

        # TAB 1: Signal Generator
        tab_gen = ttk.Frame(notebook, padding=10)
        notebook.add(tab_gen, text="Sinh tín hiệu")
        self._build_generator_tab(tab_gen)

        # TAB 2: File Loader
        tab_file = ttk.Frame(notebook, padding=10)
        notebook.add(tab_file, text="Nạp file (.csv / .mem)")
        self._build_file_tab(tab_file)

        # TAB 3: ROM Monitor & Statistics
        tab_rom = ttk.Frame(notebook, padding=10)
        notebook.add(tab_rom, text="Giám sát ROM nội")
        self._build_rom_tab(tab_rom)

        # Right panel: Real-time Matplotlib Graphs
        right_panel = ttk.LabelFrame(main_split, text=" Dạng sóng Thời gian thực (Input vs Output Filtered) ", padding=5)
        main_split.add(right_panel, weight=3)

        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("So sánh Tín hiệu vào x[n] và Tín hiệu lọc ra y[n]", fontsize=11, fontweight="bold")
        self.ax.set_xlabel("Chỉ số mẫu (Sample Index n)")
        self.ax.set_ylabel("Biên độ 12-bit [-2048, +2047]")
        self.ax.grid(True, linestyle="--", alpha=0.6)

        self.line_in, = self.ax.plot([], [], label="Đầu vào x[n] (Gửi từ PC)", color="#1f77b4", alpha=0.7, lw=1.5)
        self.line_out, = self.ax.plot([], [], label="FPGA Lọc ra y[n]", color="#2ca02c", lw=2.0)
        self.ax.legend(loc="upper right")

        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, right_panel)
        toolbar.update()

        # Bottom panel: Log Console & Export
        bottom_frame = ttk.LabelFrame(self.root, text=" Nhật ký dữ liệu truyền nhận ", padding=5)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        self.txt_log = tk.Text(bottom_frame, height=4, font=("Consolas", 9), wrap=tk.WORD)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        scb = ttk.Scrollbar(bottom_frame, command=self.txt_log.yview)
        scb.pack(side=tk.LEFT, fill=tk.Y)
        self.txt_log.config(yscrollcommand=scb.set)

        btn_box = ttk.Frame(bottom_frame)
        btn_box.pack(side=tk.RIGHT, fill=tk.Y, padx=5)

        ttk.Button(btn_box, text="Xoá đồ thị", command=self._clear_charts).pack(fill=tk.X, pady=2)
        ttk.Button(btn_box, text="Lưu CSV", command=self._export_csv).pack(fill=tk.X, pady=2)

    def _build_generator_tab(self, parent):
        ttk.Label(parent, text="Dạng sóng:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.cbo_wave = ttk.Combobox(parent, state="readonly", values=[
            "Sóng Sin + Nhiễu Gaussian",
            "Hàm bước nhảy (Step Response)",
            "Xung vuông (Square Wave)",
            "Chỉ nhiễu Gaussian (Đo giảm phương sai)"
        ])
        self.cbo_wave.current(0)
        self.cbo_wave.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Số lượng mẫu:").grid(row=1, column=0, sticky="w", pady=4)
        self.spn_count = ttk.Spinbox(parent, from_=16, to=2048, increment=16)
        self.spn_count.set(128)
        self.spn_count.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Biên độ đỉnh [-2048, 2047]:").grid(row=2, column=0, sticky="w", pady=4)
        self.spn_amp = ttk.Spinbox(parent, from_=100, to=2000, increment=100)
        self.spn_amp.set(1200)
        self.spn_amp.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Mức nhiễu sigma:").grid(row=3, column=0, sticky="w", pady=4)
        self.spn_noise = ttk.Spinbox(parent, from_=0, to=500, increment=20)
        self.spn_noise.set(100)
        self.spn_noise.grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="Tốc độ gửi (mẫu/giây):").grid(row=4, column=0, sticky="w", pady=4)
        self.spn_rate = ttk.Spinbox(parent, from_=10, to=1000, increment=50)
        self.spn_rate.set(100)
        self.spn_rate.grid(row=4, column=1, sticky="ew", pady=4)

        btn_row = ttk.Frame(parent)
        btn_row.grid(row=5, column=0, columnspan=2, pady=15, sticky="ew")

        ttk.Button(btn_row, text="1. Tạo trước mẫu", command=self._generate_signal).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_send_gen = ttk.Button(btn_row, text="2. Gửi sang FPGA", command=self._send_generated)
        self.btn_send_gen.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.lbl_gen_info = ttk.Label(parent, text="Chưa tạo mẫu nào.", foreground="#666")
        self.lbl_gen_info.grid(row=6, column=0, columnspan=2, sticky="w", pady=5)

    def _build_file_tab(self, parent):
        ttk.Label(parent, text="Chọn file chứa dữ liệu 12-bit:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=5)

        pick_frame = ttk.Frame(parent)
        pick_frame.pack(fill=tk.X, pady=5)

        self.txt_file_path = ttk.Entry(pick_frame)
        self.txt_file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(pick_frame, text="Duyệt...", command=self._browse_file).pack(side=tk.LEFT)

        ttk.Button(parent, text="Đọc và nạp dữ liệu", command=self._load_file_data).pack(fill=tk.X, pady=8)

        self.lbl_file_info = ttk.Label(parent, text="Chưa nạp file.", foreground="#666")
        self.lbl_file_info.pack(anchor="w", pady=5)

        self.btn_send_file = ttk.Button(parent, text="Gửi toàn bộ file sang FPGA lọc", command=self._send_file_data)
        self.btn_send_file.pack(fill=tk.X, pady=15)

    def _build_rom_tab(self, parent):
        ttk.Label(parent, text="Chế độ giám sát ROM 1024 mẫu:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=5)

        info_box = ttk.Label(parent, text=(
            "Hướng dẫn trên bo mạch DE0-Nano:\n"
            "1. Gạt SW[1] = 0 (Chọn nguồn ROM nội)\n"
            "2. Gạt SW[2] = 1 (Tự động phát 1.000 mẫu/s)\n"
            "   hoặc bấm nút KEY[1] để đếm tay.\n\n"
            "ESP32 sẽ liên tục nhận dữ liệu từ FPGA\n"
            "và đồ thị bên phải sẽ vẽ đường cong lọc!"
        ), justify=tk.LEFT, foreground="#333", relief="groove", padding=10)
        info_box.pack(fill=tk.X, pady=10)

        stat_frame = ttk.LabelFrame(parent, text=" Thống kê trực tiếp ", padding=10)
        stat_frame.pack(fill=tk.X, pady=10)

        self.lbl_stat_count = ttk.Label(stat_frame, text="Tổng số mẫu nhận: 0")
        self.lbl_stat_count.pack(anchor="w", pady=2)
        self.lbl_stat_latest = ttk.Label(stat_frame, text="Giá trị mới nhất: N/A")
        self.lbl_stat_latest.pack(anchor="w", pady=2)
        self.lbl_stat_range = ttk.Label(stat_frame, text="Dải biên độ: [N/A, N/A]")
        self.lbl_stat_range.pack(anchor="w", pady=2)

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.cbo_port["values"] = ports
        if "COM21" in ports:
            self.cbo_port.set("COM21")
        elif ports:
            self.cbo_port.current(0)

    def _toggle_connection(self):
        if not self.is_connected:
            port = self.cbo_port.get()
            baud = int(self.cbo_baud.get())
            if not port:
                messagebox.showerror("Lỗi", "Vui lòng chọn cổng COM!")
                return
            try:
                self.ser = serial.Serial(port, baud, timeout=0.1)
                self.is_connected = True
                self.btn_connect.config(text="Ngắt kết nối")
                self.lbl_status.config(text=f"● Đã kết nối {port}", foreground="green")
                self._log(f"Đã mở cổng {port} ở {baud} baud thành công.")

                # Start reader thread
                self.reader_thread = threading.Thread(target=self._serial_reader_loop, daemon=True)
                self.reader_thread.start()
            except Exception as e:
                messagebox.showerror("Lỗi kết nối", f"Không thể mở cổng {port}:\n{e}")
        else:
            self.is_connected = False
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
            self.ser = None
            self.btn_connect.config(text="Kết nối")
            self.lbl_status.config(text="● Đã ngắt kết nối", foreground="red")
            self._log("Đã đóng kết nối cổng COM.")

    def _serial_reader_loop(self):
        """Background thread reading from ESP32."""
        buffer = ""
        while self.is_connected and self.ser and self.ser.is_open:
            try:
                data = self.ser.read(self.ser.in_waiting or 1)
                if data:
                    text = data.decode("latin-1", errors="ignore")
                    buffer += text
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._parse_incoming_line(line)
            except Exception as e:
                break

    def _parse_incoming_line(self, line):
        """Parses output from FPGA/ESP32: +XXXX or -XXXX or SYS: messages"""
        if line.startswith("SYS:") or line.startswith("PONG:"):
            self._log(f"[ESP32]: {line}")
            return

        # Check for 12-bit signed decimal format: +XXXX / -XXXX
        try:
            if (line.startswith("+") or line.startswith("-")) and len(line) >= 2:
                val = int(line)
                self.filtered_outputs.append(val)
                self.sample_indices.append(self.current_idx)
                self.current_idx += 1
        except ValueError:
            pass

    def _generate_signal(self):
        wtype = self.cbo_wave.get()
        count = int(self.spn_count.get())
        amp = int(self.spn_amp.get())
        noise = int(self.spn_noise.get())

        samples = []
        for i in range(count):
            if "Sin" in wtype:
                clean = amp * math.sin(2.0 * math.pi * i / 32.0)
                n = random.gauss(0, noise) if noise > 0 else 0
                val = int(clean + n)
            elif "bước nhảy" in wtype:
                clean = 0 if i < (count // 2) else amp
                n = random.gauss(0, noise) if noise > 0 else 0
                val = int(clean + n)
            elif "vuông" in wtype:
                clean = amp if (i % 32) < 16 else -amp
                n = random.gauss(0, noise) if noise > 0 else 0
                val = int(clean + n)
            else: # Gaussian noise only
                val = int(random.gauss(0, noise))

            # Saturate to signed 12-bit
            val = max(-2048, min(2047, val))
            samples.append(val)

        self.generated_samples = samples
        self.lbl_gen_info.config(text=f"Đã tạo {len(samples)} mẫu [{min(samples)} .. {max(samples)}].")
        self._log(f"Đã sinh {len(samples)} mẫu dạng '{wtype}'. Sẵn sàng gửi sang FPGA.")

    def _send_generated(self):
        if not self.is_connected:
            messagebox.showwarning("Cảnh báo", "Vui lòng kết nối cổng COM trước!")
            return
        if not self.generated_samples:
            self._generate_signal()

        rate = int(self.spn_rate.get())
        delay = 1.0 / rate

        threading.Thread(target=self._stream_samples_worker, args=(self.generated_samples, delay), daemon=True).start()

    def _browse_file(self):
        p = filedialog.askopenfilename(filetypes=[("Data files", "*.csv;*.mem;*.txt"), ("All files", "*.*")])
        if p:
            self.txt_file_path.delete(0, tk.END)
            self.txt_file_path.insert(0, p)
            self._load_file_data()

    def _load_file_data(self):
        p = self.txt_file_path.get().strip()
        if not os.path.exists(p):
            messagebox.showerror("Lỗi", "File không tồn tại!")
            return

        samples = []
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Check hex (.mem) or decimal (.csv/.txt)
                    if p.endswith(".mem"):
                        val = int(line, 16)
                        if val >= 2048:
                            val -= 4096
                    else:
                        parts = line.split(",")
                        val = int(float(parts[0]))
                    val = max(-2048, min(2047, val))
                    samples.append(val)

            self.generated_samples = samples
            self.lbl_file_info.config(text=f"Đã nạp {len(samples)} mẫu từ file.\nDải: [{min(samples)} .. {max(samples)}]")
            self._log(f"Đã nạp {len(samples)} mẫu từ {os.path.basename(p)}")
        except Exception as e:
            messagebox.showerror("Lỗi đọc file", f"Không thể đọc file:\n{e}")

    def _send_file_data(self):
        if not self.is_connected:
            messagebox.showwarning("Cảnh báo", "Vui lòng kết nối cổng COM trước!")
            return
        if not self.generated_samples:
            messagebox.showwarning("Cảnh báo", "Chưa có dữ liệu nào được nạp!")
            return

        delay = 0.005 # 5ms per sample (~200 samples/sec)
        threading.Thread(target=self._stream_samples_worker, args=(self.generated_samples, delay), daemon=True).start()

    def _stream_samples_worker(self, samples, delay_sec):
        self.is_streaming = True
        self._log(f"Bắt đầu phát {len(samples)} mẫu sang FPGA qua ESP32 (giãn cách {delay_sec*1000:.1f}ms)...")

        for val in samples:
            if not self.is_connected:
                break
            # Send sample command: D:<val>\n
            cmd = f"D:{val}\n"
            try:
                self.ser.write(cmd.encode("ascii"))
                self.raw_inputs.append(val)
            except:
                break
            time.sleep(delay_sec)

        self.is_streaming = False
        self._log("Hoàn tất truyền dữ liệu sang FPGA!")

    def _gui_update_loop(self):
        """Called periodically to refresh plot and statistics."""
        if self.filtered_outputs:
            n_pts = len(self.filtered_outputs)
            x_data = list(self.sample_indices)
            y_out = list(self.filtered_outputs)

            self.line_out.set_data(x_data, y_out)

            # If we also sent raw inputs, align and plot
            if self.raw_inputs:
                y_in = list(self.raw_inputs)[-n_pts:]
                x_in = x_data[-len(y_in):]
                self.line_in.set_data(x_in, y_in)

            # Adjust axes limits
            min_x = x_data[0]
            max_x = x_data[-1] + 1 if x_data[-1] > x_data[0] else min_x + 10
            self.ax.set_xlim(min_x, max_x)
            self.ax.set_ylim(-2100, 2100)
            self.canvas.draw_idle()

            # Update stats
            self.lbl_stat_count.config(text=f"Tổng số mẫu nhận: {self.current_idx}")
            self.lbl_stat_latest.config(text=f"Giá trị mới nhất: {y_out[-1]}")
            self.lbl_stat_range.config(text=f"Dải biên độ: [{min(y_out)} .. {max(y_out)}]")

        self.root.after(50, self._gui_update_loop)

    def _clear_charts(self):
        self.raw_inputs.clear()
        self.filtered_outputs.clear()
        self.sample_indices.clear()
        self.current_idx = 0
        self.line_in.set_data([], [])
        self.line_out.set_data([], [])
        self.canvas.draw_idle()
        self._log("Đã làm mới đồ thị.")

    def _export_csv(self):
        if not self.filtered_outputs:
            messagebox.showinfo("Thông báo", "Không có dữ liệu ngõ ra để xuất!")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV file", "*.csv")])
        if p:
            try:
                with open(p, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Index", "Data_Out"])
                    for idx, val in zip(self.sample_indices, self.filtered_outputs):
                        writer.writerow([idx, val])
                self._log(f"Đã xuất {len(self.filtered_outputs)} mẫu ra file: {p}")
                messagebox.showinfo("Thành công", f"Đã lưu file thành công tại:\n{p}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file:\n{e}")

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{ts}] {msg}\n")
        self.txt_log.see(tk.END)


def main():
    root = tk.Tk()
    app = SensorFilterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
