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
        self.root.geometry("1260x860")
        self.root.minsize(1100, 750)

        # Serial state
        self.ser = None
        self.is_connected = False
        self.reader_thread = None
        self.is_streaming = False

        # Data buffers for real-time visualization (up to 2048 points)
        self.MAX_POINTS = 2048
        self.raw_inputs = deque(maxlen=self.MAX_POINTS)
        self.filtered_outputs = deque(maxlen=self.MAX_POINTS)
        self.sample_indices = deque(maxlen=self.MAX_POINTS)
        self.current_idx = 0

        # Generator & File loaded data
        self.generated_samples = []
        self.csv_raw_matrix = [] # Parsed full matrix for CSV files
        self.csv_headers = []

        # ROM 1024-sample capture state
        self.is_recording_rom = False
        self.rom_captured_samples = []

        # Setup UI
        self._build_ui()
        self._refresh_ports()

        # Periodic GUI update timer (30 FPS)
        self.root.after(33, self._gui_update_loop)

    def _build_ui(self):
        # ---------------------------------------------------------------------
        # 1. Hướng dẫn nhanh Switch & Phím bấm DE0-Nano (Ngay ngoài trang chính)
        # ---------------------------------------------------------------------
        guide_frame = ttk.LabelFrame(self.root, text=" 📌 BẢNG HƯỚNG DẪN CÔNG TẮC & NÚT NHẤN TRÊN KIT DE0-NANO ", padding=(10, 6))
        guide_frame.pack(fill=tk.X, padx=10, pady=(6, 3))

        guide_grid = ttk.Frame(guide_frame)
        guide_grid.pack(fill=tk.X, expand=True)

        # Column 1: SW[0] & SW[1]
        col1 = ttk.Frame(guide_grid)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        lbl_sw0 = ttk.Label(col1, text="• SW[0] (Loại bộ lọc):", font=("Segoe UI", 9, "bold"), foreground="#0055aa")
        lbl_sw0.pack(anchor="w")
        ttk.Label(col1, text="  - GẠT XUỐNG (0) : Bộ lọc Moving Average 8 mẫu (LED 7 đoạn hiện chữ 'A')\n  - GẠT LÊN (1)   : Bộ lọc FIR 8-tap Q1.15 (LED 7 đoạn hiện chữ 'F')").pack(anchor="w")

        lbl_sw1 = ttk.Label(col1, text="• SW[1] (Nguồn dữ liệu):", font=("Segoe UI", 9, "bold"), foreground="#0055aa")
        lbl_sw1.pack(anchor="w", pady=(4, 0))
        ttk.Label(col1, text="  - GẠT XUỐNG (0) : Lấy từ ROM nội (1024 mẫu có sẵn)\n  - GẠT LÊN (1)   : Nhận từ UART RX ngoài (Gửi từ GUI / ESP32)").pack(anchor="w")

        # Column 2: SW[2] & Buttons KEY[0], KEY[1]
        col2 = ttk.Frame(guide_grid)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        lbl_sw2 = ttk.Label(col2, text="• SW[2] (Chế độ phát ROM):", font=("Segoe UI", 9, "bold"), foreground="#0055aa")
        lbl_sw2.pack(anchor="w")
        ttk.Label(col2, text="  - GẠT XUỐNG (0) : Chế độ bấm tay (Nhấn nút KEY[1] để kích từng mẫu)\n  - GẠT LÊN (1)   : Tự động phát liên tục tuần hoàn 1.000 mẫu/giây").pack(anchor="w")

        lbl_keys = ttk.Label(col2, text="• Nút nhấn KEY:", font=("Segoe UI", 9, "bold"), foreground="#0055aa")
        lbl_keys.pack(anchor="w", pady=(4, 0))
        ttk.Label(col2, text="  - KEY[0] : Reset hệ thống (Nhấn giữ = Reset, Thả = Chạy bình thường)\n  - KEY[1] : Kích phát đúng 1 mẫu đơn khi SW[2]=0 (Đã khử rung 5ms)").pack(anchor="w")

        # ---------------------------------------------------------------------
        # 2. Thanh kết nối Cổng COM (ESP32 Bridge)
        # ---------------------------------------------------------------------
        conn_frame = ttk.LabelFrame(self.root, text=" Kết nối Cổng COM (ESP32 UART Bridge) ", padding=(10, 5))
        conn_frame.pack(fill=tk.X, padx=10, pady=3)

        ttk.Label(conn_frame, text="Cổng COM:").pack(side=tk.LEFT, padx=(0, 5))
        self.cbo_port = ttk.Combobox(conn_frame, width=15, state="readonly")
        self.cbo_port.pack(side=tk.LEFT, padx=5)

        btn_refresh = ttk.Button(conn_frame, text="Quét cổng", command=self._refresh_ports)
        btn_refresh.pack(side=tk.LEFT, padx=5)

        ttk.Label(conn_frame, text="Baudrate:").pack(side=tk.LEFT, padx=(15, 5))
        self.cbo_baud = ttk.Combobox(conn_frame, width=10, state="readonly", values=["115200", "57600", "9600"])
        self.cbo_baud.current(0)
        self.cbo_baud.pack(side=tk.LEFT, padx=5)

        self.btn_connect = ttk.Button(conn_frame, text="Kết nối", command=self._toggle_connection)
        self.btn_connect.pack(side=tk.LEFT, padx=15)

        self.lbl_status = ttk.Label(conn_frame, text="● Chưa kết nối", foreground="red", font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # ---------------------------------------------------------------------
        # 3. Main horizontal split
        # ---------------------------------------------------------------------
        main_split = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_split.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # Left panel: Tabs (Generator, CSV/File Loader, ROM Monitor)
        left_panel = ttk.Frame(main_split, width=460)
        main_split.add(left_panel, weight=2)

        notebook = ttk.Notebook(left_panel)
        notebook.pack(fill=tk.BOTH, expand=True)

        # TAB 1: CSV / File Loader (Hỗ trợ chọn theo HÀNG hoặc theo CỘT)
        tab_csv = ttk.Frame(notebook, padding=8)
        notebook.add(tab_csv, text="Nạp File (CSV / MEM / TXT)")
        self._build_csv_tab(tab_csv)

        # TAB 2: Signal Generator
        tab_gen = ttk.Frame(notebook, padding=8)
        notebook.add(tab_gen, text="Tự sinh tín hiệu")
        self._build_generator_tab(tab_gen)

        # TAB 3: ROM Monitor & Statistics
        tab_rom = ttk.Frame(notebook, padding=8)
        notebook.add(tab_rom, text="Giám sát ROM nội")
        self._build_rom_tab(tab_rom)

        # Right panel: Real-time Matplotlib Graphs
        right_panel = ttk.LabelFrame(main_split, text=" Dạng sóng Thời gian thực (Input x[n] vs Output y[n]) ", padding=5)
        main_split.add(right_panel, weight=3)

        # Thanh công cụ điều khiển đồ thị & Trục Y
        graph_ctrl = ttk.Frame(right_panel)
        graph_ctrl.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(graph_ctrl, text="🔍 Chế độ trục Y:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(5, 5))
        self.cbo_scale_mode = ttk.Combobox(graph_ctrl, state="readonly", width=25, values=[
            "Tự động tối ưu (Auto-Fit + 15%)",
            "Đối xứng qua 0 (Symmetric)",
            "Toàn dải 12-bit [-2048, +2047]",
            "Dải 10-bit [-512, +511]",
            "Dải 8-bit [-128, +127]"
        ])
        self.cbo_scale_mode.current(0) # Mặc định tự động co giãn đẹp nhất
        self.cbo_scale_mode.pack(side=tk.LEFT, padx=5)

        ttk.Label(graph_ctrl, text="Số điểm hiển thị:").pack(side=tk.LEFT, padx=(15, 5))
        self.spn_view_pts = ttk.Spinbox(graph_ctrl, from_=32, to=2048, increment=64, width=6)
        self.spn_view_pts.set(256)
        self.spn_view_pts.pack(side=tk.LEFT, padx=2)

        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("So sánh Tín hiệu vào x[n] và Tín hiệu lọc ra y[n] trên FPGA", fontsize=11, fontweight="bold")
        self.ax.set_xlabel("Chỉ số mẫu (Sample Index n)")
        self.ax.set_ylabel("Biên độ tín hiệu")
        self.ax.grid(True, linestyle="--", alpha=0.6)

        self.line_in, = self.ax.plot([], [], label="Đầu vào x[n] (Gốc)", color="#1f77b4", alpha=0.65, lw=1.5, linestyle="--")
        self.line_out, = self.ax.plot([], [], label="FPGA Lọc ra y[n]", color="#2ca02c", lw=2.2)
        self.ax.legend(loc="upper right")

        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, right_panel)
        toolbar.update()

        # ---------------------------------------------------------------------
        # 4. Bottom panel: Log Console & Export
        # ---------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # TAB 1: CSV LOADER (Theo Cột hoặc Theo Hàng)
    # -------------------------------------------------------------------------
    def _build_csv_tab(self, parent):
        ttk.Label(parent, text="1. Chọn file dữ liệu (.csv / .mem / .txt):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))

        pick_frame = ttk.Frame(parent)
        pick_frame.pack(fill=tk.X, pady=2)

        self.txt_file_path = ttk.Entry(pick_frame)
        self.txt_file_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(pick_frame, text="Duyệt...", command=self._browse_file).pack(side=tk.LEFT)

        # Tùy chọn trích xuất dữ liệu CSV
        opt_frame = ttk.LabelFrame(parent, text=" 2. Tuỳ chọn trích xuất dữ liệu CSV ", padding=8)
        opt_frame.pack(fill=tk.X, pady=8)

        # Chế độ: Theo Cột hay Theo Hàng
        mode_row = ttk.Frame(opt_frame)
        mode_row.pack(fill=tk.X, pady=3)
        ttk.Label(mode_row, text="Chiều dữ liệu:").pack(side=tk.LEFT, padx=(0, 10))

        self.csv_mode_var = tk.StringVar(value="COL")
        rb_col = ttk.Radiobutton(mode_row, text="Theo CỘT (Column)", variable=self.csv_mode_var, value="COL", command=self._update_csv_ui_state)
        rb_col.pack(side=tk.LEFT, padx=5)
        rb_row = ttk.Radiobutton(mode_row, text="Theo HÀNG (Row)", variable=self.csv_mode_var, value="ROW", command=self._update_csv_ui_state)
        rb_row.pack(side=tk.LEFT, padx=5)

        # Chọn số Cột hoặc số Hàng
        self.idx_frame = ttk.Frame(opt_frame)
        self.idx_frame.pack(fill=tk.X, pady=4)

        self.lbl_target = ttk.Label(self.idx_frame, text="Chọn Cột cần lấy:")
        self.lbl_target.pack(side=tk.LEFT, padx=(0, 5))

        self.cbo_target_col = ttk.Combobox(self.idx_frame, width=22, state="readonly")
        self.cbo_target_col.pack(side=tk.LEFT, padx=5)
        self.cbo_target_col.bind("<<ComboboxSelected>>", lambda e: self._preview_csv_selection())

        self.spn_target_row = ttk.Spinbox(self.idx_frame, from_=0, to=99999, width=10)
        self.spn_target_row.set(0)

        # Bỏ qua dòng Header đầu tiên
        self.chk_skip_header_var = tk.BooleanVar(value=True)
        self.chk_skip_header = ttk.Checkbutton(opt_frame, text="Bỏ qua dòng Header đầu tiên (nếu có chữ)", variable=self.chk_skip_header_var, command=self._preview_csv_selection)
        self.chk_skip_header.pack(anchor="w", pady=2)

        # Giới hạn số mẫu
        lim_row = ttk.Frame(opt_frame)
        lim_row.pack(fill=tk.X, pady=4)
        ttk.Label(lim_row, text="Số mẫu tối đa lấy:").pack(side=tk.LEFT, padx=(0, 5))
        self.spn_max_samples = ttk.Spinbox(lim_row, from_=10, to=10000, increment=100, width=10)
        self.spn_max_samples.set(1024)
        self.spn_max_samples.pack(side=tk.LEFT, padx=5)
        ttk.Label(lim_row, text="(mẫu)").pack(side=tk.LEFT)

        ttk.Button(opt_frame, text="Trích xuất & Xem trước", command=self._preview_csv_selection).pack(fill=tk.X, pady=5)

        # Khung thông tin xem trước (Preview)
        prev_frame = ttk.LabelFrame(parent, text=" 3. Dữ liệu trích xuất sẵn sàng gửi ", padding=8)
        prev_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        self.lbl_csv_summary = ttk.Label(prev_frame, text="Chưa nạp file.", foreground="#666")
        self.lbl_csv_summary.pack(anchor="w", pady=2)

        self.txt_csv_preview = tk.Text(prev_frame, height=5, font=("Consolas", 8), wrap=tk.NONE)
        self.txt_csv_preview.pack(fill=tk.BOTH, expand=True, pady=3)

        send_row = ttk.Frame(parent)
        send_row.pack(fill=tk.X, pady=5)

        ttk.Label(send_row, text="Tốc độ gửi:").pack(side=tk.LEFT, padx=(0, 5))
        self.spn_file_rate = ttk.Spinbox(send_row, from_=10, to=1000, increment=50, width=7)
        self.spn_file_rate.set(100)
        self.spn_file_rate.pack(side=tk.LEFT, padx=5)
        ttk.Label(send_row, text="mẫu/s").pack(side=tk.LEFT, padx=(0, 15))

        self.btn_send_file = ttk.Button(send_row, text="🚀 Gửi sang FPGA lọc", command=self._send_file_data)
        self.btn_send_file.pack(side=tk.RIGHT, expand=True, fill=tk.X)

    def _update_csv_ui_state(self):
        mode = self.csv_mode_var.get()
        if mode == "COL":
            self.lbl_target.config(text="Chọn Cột cần lấy:")
            self.spn_target_row.pack_forget()
            self.cbo_target_col.pack(side=tk.LEFT, padx=5)
            self.chk_skip_header.pack(anchor="w", pady=2)
        else: # ROW
            self.lbl_target.config(text="Chọn Hàng (Row Index):")
            self.cbo_target_col.pack_forget()
            self.spn_target_row.pack(side=tk.LEFT, padx=5)
            self.chk_skip_header.pack_forget()

        self._preview_csv_selection()

    def _browse_file(self):
        p = filedialog.askopenfilename(filetypes=[("Data files", "*.csv;*.mem;*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            self.txt_file_path.delete(0, tk.END)
            self.txt_file_path.insert(0, p)
            self._parse_raw_file(p)

    def _parse_raw_file(self, path):
        if not os.path.exists(path):
            return

        self.csv_raw_matrix = []
        self.csv_headers = []

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                # Detect delimiter for CSV
                first_few_lines = [f.readline() for _ in range(5)]
                f.seek(0)

                sample_text = "".join(first_few_lines)
                delimiter = ","
                if ";" in sample_text and sample_text.count(";") > sample_text.count(","):
                    delimiter = ";"
                elif "\t" in sample_text and sample_text.count("\t") > sample_text.count(","):
                    delimiter = "\t"

                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    cleaned_row = [item.strip() for item in row if item.strip()]
                    if cleaned_row:
                        self.csv_raw_matrix.append(cleaned_row)

            if not self.csv_raw_matrix:
                self.lbl_csv_summary.config(text="File rỗng!")
                return

            num_rows = len(self.csv_raw_matrix)
            num_cols = max(len(r) for r in self.csv_raw_matrix)

            # Update combobox columns
            col_options = []
            for c in range(num_cols):
                header_name = self.csv_raw_matrix[0][c] if c < len(self.csv_raw_matrix[0]) else ""
                col_options.append(f"Cột {c}: {header_name}")

            self.cbo_target_col["values"] = col_options
            if col_options:
                # Pick column 1 if column 0 looks like an index/time
                self.cbo_target_col.current(1 if len(col_options) > 1 else 0)

            self.spn_target_row.config(to=num_rows - 1)
            self._log(f"Đã mở file: {os.path.basename(path)} ({num_rows} hàng, {num_cols} cột)")
            self._preview_csv_selection()

        except Exception as e:
            messagebox.showerror("Lỗi đọc file", f"Không thể phân tích cấu trúc file:\n{e}")

    def _preview_csv_selection(self):
        if not self.csv_raw_matrix:
            return

        mode = self.csv_mode_var.get()
        max_samples = int(self.spn_max_samples.get())
        extracted_vals = []

        if mode == "COL":
            col_idx = self.cbo_target_col.current()
            if col_idx < 0:
                col_idx = 0
            skip_header = self.chk_skip_header_var.get()
            start_row = 1 if skip_header else 0

            for r in range(start_row, len(self.csv_raw_matrix)):
                row = self.csv_raw_matrix[r]
                if col_idx < len(row):
                    cell = row[col_idx]
                    try:
                        # Parse decimal or hex
                        if cell.startswith("0x") or cell.startswith("0X"):
                            v = int(cell, 16)
                        else:
                            v = int(float(cell))
                        # Saturate signed 12-bit
                        v = max(-2048, min(2047, v))
                        extracted_vals.append(v)
                    except ValueError:
                        continue # Skip text/NaN cells
                if len(extracted_vals) >= max_samples:
                    break

        else: # ROW mode
            try:
                row_idx = int(self.spn_target_row.get())
            except ValueError:
                row_idx = 0
            row_idx = max(0, min(len(self.csv_raw_matrix) - 1, row_idx))
            target_row = self.csv_raw_matrix[row_idx]

            for cell in target_row:
                try:
                    if cell.startswith("0x") or cell.startswith("0X"):
                        v = int(cell, 16)
                    else:
                        v = int(float(cell))
                    v = max(-2048, min(2047, v))
                    extracted_vals.append(v)
                except ValueError:
                    continue
                if len(extracted_vals) >= max_samples:
                    break

        self.generated_samples = extracted_vals

        if extracted_vals:
            preview_str = ", ".join(str(v) for v in extracted_vals[:20])
            if len(extracted_vals) > 20:
                preview_str += f", ... (còn {len(extracted_vals) - 20} mẫu)"
            self.lbl_csv_summary.config(
                text=f"Trích xuất thành công: {len(extracted_vals)} mẫu\nDải biên độ: [{min(extracted_vals)} .. {max(extracted_vals)}]",
                foreground="#007700"
            )
            self.txt_csv_preview.delete("1.0", tk.END)
            self.txt_csv_preview.insert(tk.END, preview_str)
        else:
            self.lbl_csv_summary.config(text="Không tìm thấy số liệu hợp lệ trong lựa chọn!", foreground="red")
            self.txt_csv_preview.delete("1.0", tk.END)

    def _send_file_data(self):
        if not self.is_connected:
            messagebox.showwarning("Cảnh báo", "Vui lòng kết nối cổng COM trước!")
            return
        if not self.generated_samples:
            messagebox.showwarning("Cảnh báo", "Chưa có mẫu nào được trích xuất để gửi!")
            return

        rate = int(self.spn_file_rate.get())
        delay = 1.0 / rate
        threading.Thread(target=self._stream_samples_worker, args=(self.generated_samples, delay), daemon=True).start()

    # -------------------------------------------------------------------------
    # TAB 2: SIGNAL GENERATOR
    # -------------------------------------------------------------------------
    def _build_generator_tab(self, parent):
        ttk.Label(parent, text="Dạng sóng thử nghiệm:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
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

    # -------------------------------------------------------------------------
    # TAB 3: ROM MONITOR & 1024 SAMPLES CAPTURE
    # -------------------------------------------------------------------------
    def _build_rom_tab(self, parent):
        ttk.Label(parent, text="Chế độ giám sát & Thu thập ROM 1024 mẫu:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=3)

        info_box = ttk.Label(parent, text=(
            "Thao tác trên bo mạch DE0-Nano:\n"
            "1. Gạt SW[1] XUỐNG (0): Chọn nguồn ROM nội (1024 mẫu có sẵn).\n"
            "2. Gạt SW[0]: Gạt XUỐNG (0) = MA Filter | Gạt LÊN (1) = FIR Filter.\n"
            "3. Gạt SW[2] LÊN (1): Tự phát liên tục tuần hoàn 1.000 mẫu/giây."
        ), justify=tk.LEFT, foreground="#222", relief="groove", padding=6)
        info_box.pack(fill=tk.X, pady=4)

        # Khung thu thập trọn vẹn 1024 mẫu ROM
        rec_frame = ttk.LabelFrame(parent, text=" ⏺ Thu thập & Xuất trọn vẹn 1024 mẫu ROM ", padding=8)
        rec_frame.pack(fill=tk.X, pady=5)

        ttk.Label(rec_frame, text="Quy trình ghi đồng bộ 1 chu kỳ 1024 mẫu:\n"
                                  "1. Bấm nút 'Bắt đầu ghi 1024 mẫu' bên dưới.\n"
                                  "2. Nhấn giữ nút KEY[0] trên kit rồi thả ra (để Reset ROM về mẫu 0).\n"
                                  "3. GUI tự động ghi đủ 1024 mẫu rồi xuất file CSV.",
                  font=("Segoe UI", 8), foreground="#333").pack(anchor="w", pady=(0, 4))

        self.btn_rec_rom = ttk.Button(rec_frame, text="⏺ Bắt đầu ghi 1024 mẫu ROM", command=self._toggle_rom_record)
        self.btn_rec_rom.pack(fill=tk.X, pady=3)

        self.prog_rom = ttk.Progressbar(rec_frame, orient=tk.HORIZONTAL, mode="determinate", maximum=1024)
        self.prog_rom.pack(fill=tk.X, pady=3)

        self.lbl_rom_rec_status = ttk.Label(rec_frame, text="Trạng thái: Chưa ghi", foreground="#555", font=("Segoe UI", 9, "bold"))
        self.lbl_rom_rec_status.pack(anchor="w", pady=2)

        btn_act_row = ttk.Frame(rec_frame)
        btn_act_row.pack(fill=tk.X, pady=3)

        self.btn_save_rom_csv = ttk.Button(btn_act_row, text="💾 Xuất file CSV (1024 mẫu)", command=self._export_rom_captured_csv, state=tk.DISABLED)
        self.btn_save_rom_csv.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_plot_rom_1024 = ttk.Button(btn_act_row, text="📊 Xem trọn 1024 mẫu", command=self._plot_captured_rom, state=tk.DISABLED)
        self.btn_plot_rom_1024.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # Khung thống kê trực tiếp
        stat_frame = ttk.LabelFrame(parent, text=" Thống kê trực tiếp ", padding=8)
        stat_frame.pack(fill=tk.X, pady=4)

        self.lbl_stat_count = ttk.Label(stat_frame, text="Tổng số mẫu nhận: 0")
        self.lbl_stat_count.pack(anchor="w", pady=1)
        self.lbl_stat_latest = ttk.Label(stat_frame, text="Giá trị mới nhất: N/A")
        self.lbl_stat_latest.pack(anchor="w", pady=1)
        self.lbl_stat_range = ttk.Label(stat_frame, text="Dải biên độ: [N/A, N/A]")
        self.lbl_stat_range.pack(anchor="w", pady=1)

    def _toggle_rom_record(self):
        if not self.is_connected:
            messagebox.showwarning("Cảnh báo", "Vui lòng kết nối cổng COM trước!")
            return

        if not self.is_recording_rom:
            self.rom_captured_samples = []
            self.is_recording_rom = True
            self.prog_rom["value"] = 0
            self.btn_rec_rom.config(text="⏹ Dừng thu thập")
            self.lbl_rom_rec_status.config(text="Đang chờ nhận 1024 mẫu... (Bấm KEY[0] trên kit để reset về 0)", foreground="#0055aa")
            self._log("Bắt đầu chế độ ghi 1024 mẫu từ ROM... (Hãy bấm phím KEY[0] trên kit DE0-Nano để đồng bộ)")
        else:
            self.is_recording_rom = False
            self.btn_rec_rom.config(text="⏺ Bắt đầu ghi 1024 mẫu ROM")
            self.lbl_rom_rec_status.config(text=f"Đã dừng ghi. Đã nhận: {len(self.rom_captured_samples)}/1024 mẫu", foreground="#aa5500")
            if len(self.rom_captured_samples) > 0:
                self.btn_save_rom_csv.config(state=tk.NORMAL)
                self.btn_plot_rom_1024.config(state=tk.NORMAL)

    def _on_rom_capture_completed(self):
        self.prog_rom["value"] = 1024
        self.btn_rec_rom.config(text="⏺ Bắt đầu ghi 1024 mẫu ROM")
        self.lbl_rom_rec_status.config(text="✓ Đã thu thập đủ 1024 mẫu ROM!", foreground="green")
        self.btn_save_rom_csv.config(state=tk.NORMAL)
        self.btn_plot_rom_1024.config(state=tk.NORMAL)
        self._log("Đã thu thập trọn vẹn 1024 mẫu từ ROM nội FPGA!")

        if messagebox.askyesno("Thu thập thành công", "Đã thu thập thành công 1024 mẫu từ ROM nội FPGA!\n\nBạn có muốn lưu thành file CSV ngay bây giờ không?"):
            self._export_rom_captured_csv()

    def _load_rom_ground_truth(self):
        """Đọc 1024 mẫu x[n] gốc từ file .mem trong thư mục rom để đối chiếu."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cand_paths = [
            os.path.join(script_dir, "..", "rom", "test_vectors_clean.mem"),
            os.path.join(script_dir, "..", "rom", "test_vectors.mem"),
            os.path.join("rom", "test_vectors_clean.mem"),
            os.path.join("rom", "test_vectors.mem")
        ]
        for p in cand_paths:
            if os.path.exists(p):
                try:
                    vals = []
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            s = line.strip()
                            if not s or s.startswith("//"):
                                continue
                            raw_hex = int(s, 16)
                            signed_val = raw_hex - 4096 if raw_hex >= 2048 else raw_hex
                            vals.append(signed_val)
                    if len(vals) >= 1024:
                        return vals[:1024]
                except Exception:
                    pass
        return None

    def _export_rom_captured_csv(self):
        if not self.rom_captured_samples:
            messagebox.showinfo("Thông báo", "Chưa có dữ liệu 1024 mẫu ROM để xuất!")
            return

        ground_truth = self._load_rom_ground_truth()
        default_name = "fpga_rom_filtered_1024.csv"
        p = filedialog.asksaveasfilename(initialfile=default_name, defaultextension=".csv", filetypes=[("CSV file", "*.csv")])
        if not p:
            return

        try:
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if ground_truth and len(ground_truth) >= 1024:
                    writer.writerow(["Index", "ROM_Input_x[n]", "FPGA_Filtered_y[n]"])
                    for i in range(1024):
                        out_val = self.rom_captured_samples[i] if i < len(self.rom_captured_samples) else ""
                        writer.writerow([i, ground_truth[i], out_val])
                    self._log(f"Đã xuất 1024 mẫu ROM (kèm Input x[n] đối chiếu) ra: {p}")
                else:
                    writer.writerow(["Index", "FPGA_Filtered_y[n]"])
                    for i, val in enumerate(self.rom_captured_samples[:1024]):
                        writer.writerow([i, val])
                    self._log(f"Đã xuất 1024 mẫu ngõ ra ROM ra: {p}")
            messagebox.showinfo("Thành công", f"Đã lưu thành công 1024 mẫu ROM vào:\n{p}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file CSV:\n{e}")

    def _plot_captured_rom(self):
        if not self.rom_captured_samples:
            return
        ground_truth = self._load_rom_ground_truth()
        self.raw_inputs.clear()
        self.filtered_outputs.clear()
        self.sample_indices.clear()

        n = min(1024, len(self.rom_captured_samples))
        for i in range(n):
            self.sample_indices.append(i)
            self.filtered_outputs.append(self.rom_captured_samples[i])
            if ground_truth and i < len(ground_truth):
                self.raw_inputs.append(ground_truth[i])

        self.current_idx = n
        self.spn_view_pts.set(1024)
        self._log("Đã hiển thị trọn vẹn 1024 mẫu ROM lên đồ thị.")

    # -------------------------------------------------------------------------
    # Serial Worker & Communication
    # -------------------------------------------------------------------------
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

                # Ghi nhận trọn vẹn 1024 mẫu ROM nếu chế độ ghi đang bật
                if hasattr(self, 'is_recording_rom') and self.is_recording_rom:
                    self.rom_captured_samples.append(val)
                    if len(self.rom_captured_samples) >= 1024:
                        self.is_recording_rom = False
                        self.root.after(0, self._on_rom_capture_completed)
        except ValueError:
            pass

    def _stream_samples_worker(self, samples, delay_sec):
        self.is_streaming = True
        self._log(f"Bắt đầu phát {len(samples)} mẫu sang FPGA qua ESP32 (tốc độ {1.0/delay_sec:.0f} mẫu/s)...")

        for val in samples:
            if not self.is_connected:
                break
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
        """Periodic refresh of plots and statistics with dynamic Y-axis auto-scaling."""
        if self.filtered_outputs:
            try:
                view_n = int(self.spn_view_pts.get())
            except (ValueError, AttributeError):
                view_n = 256
            view_n = max(32, min(view_n, 2048))

            x_all = list(self.sample_indices)
            y_out_all = list(self.filtered_outputs)

            # Cắt lát cửa sổ hiển thị theo số điểm người dùng chọn
            x_data = x_all[-view_n:]
            y_out = y_out_all[-view_n:]

            self.line_out.set_data(x_data, y_out)

            all_visible_y = list(y_out)

            # If raw inputs exist, align and plot
            if self.raw_inputs:
                y_in_all = list(self.raw_inputs)
                y_in_slice = y_in_all[-len(x_data):]
                x_in_slice = x_data[-len(y_in_slice):]
                self.line_in.set_data(x_in_slice, y_in_slice)
                all_visible_y.extend(y_in_slice)
            else:
                self.line_in.set_data([], [])

            min_x = x_data[0]
            max_x = x_data[-1] + 1 if x_data[-1] > x_data[0] else min_x + 10
            self.ax.set_xlim(min_x, max_x)

            # -------------------------------------------------------------
            # TỰ ĐỘNG TÍNH TOÁN TRỤC Y TỐI ƯU THEO DẢI DỮ LIỆU ĐANG HIỂN THỊ
            # -------------------------------------------------------------
            scale_mode = self.cbo_scale_mode.get() if hasattr(self, 'cbo_scale_mode') else "Tự động tối ưu (Auto-Fit + 15%)"

            if "Toàn dải 12-bit" in scale_mode:
                ymin, ymax = -2100, 2100
            elif "10-bit" in scale_mode:
                ymin, ymax = -520, 520
            elif "8-bit" in scale_mode:
                ymin, ymax = -135, 135
            elif "Đối xứng qua 0" in scale_mode:
                if all_visible_y:
                    max_abs = max(abs(min(all_visible_y)), abs(max(all_visible_y)))
                    margin = max(20, int(math.ceil(max_abs * 1.15)))
                else:
                    margin = 100
                ymin, ymax = -margin, margin
            else:
                # Mặc định: "Tự động tối ưu (Auto-Fit + 15%)"
                if all_visible_y:
                    v_min = min(all_visible_y)
                    v_max = max(all_visible_y)
                    span = v_max - v_min
                    if span < 1e-3:
                        # Tín hiệu phẳng hằng số: đệm 20 đơn vị trên/dưới
                        pad = 20
                    else:
                        # Đệm thêm 15% span để đỉnh sóng không bị chạm sát mép đồ thị
                        pad = max(10, int(math.ceil(span * 0.15)))
                    ymin = v_min - pad
                    ymax = v_max + pad
                else:
                    ymin, ymax = -2100, 2100

            self.ax.set_ylim(ymin, ymax)
            self.canvas.draw_idle()

            # Update stats
            self.lbl_stat_count.config(text=f"Tổng số mẫu nhận: {self.current_idx}")
            self.lbl_stat_latest.config(text=f"Giá trị mới nhất: {y_out[-1]}")
            self.lbl_stat_range.config(text=f"Dải biên độ hiển thị: [{min(y_out)} .. {max(y_out)}]  (Trục Y: [{ymin} .. {ymax}])")

        # Cập nhật thanh tiến trình ghi 1024 mẫu ROM nếu đang chạy
        if hasattr(self, 'is_recording_rom') and self.is_recording_rom:
            c = len(self.rom_captured_samples)
            self.prog_rom["value"] = c
            self.lbl_rom_rec_status.config(text=f"Đang thu thập: {c}/1024 mẫu ({c*100//1024}%)...", foreground="#0055aa")

        self.root.after(40, self._gui_update_loop)

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
