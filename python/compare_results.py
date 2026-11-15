"""
Script tự động đối chiếu kết quả thực thi (Mô phỏng hoặc từ KIT phần cứng)
với mô hình chuẩn lý thuyết trong results/python_reference.csv.
"""

import sys
import csv
from pathlib import Path

def compare_results(captured_csv_path, ref_csv_path="results/python_reference.csv", filter_mode="ma"):
    captured_file = Path(captured_csv_path)
    ref_file = Path(ref_csv_path)

    if not captured_file.exists():
        print(f"[ERROR] Không tìm thấy file kết quả đo: {captured_file}")
        return

    if not ref_file.exists():
        print(f"[ERROR] Không tìm thấy file chuẩn: {ref_file}")
        return

    # Đọc dữ liệu chuẩn từ reference model
    ref_samples = []
    col_name = "ma_output" if filter_mode.lower() == "ma" else "fir_output"
    valid_col = "ma_valid" if filter_mode.lower() == "ma" else "fir_valid"

    with ref_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[valid_col] == "1":
                ref_samples.append(int(row[col_name]))

    # Đọc dữ liệu từ file thu thập được (từ Testbench ROM hoặc từ UART KIT)
    captured_samples = []
    with captured_file.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        # Tìm vị trí cột dữ liệu ngõ ra và cột valid nếu có
        col_idx = 1
        val_idx = None
        if header:
            header_lower = [h.strip().lower() for h in header]
            if col_name in header_lower:
                col_idx = header_lower.index(col_name)
            elif "data_out" in header_lower:
                col_idx = header_lower.index("data_out")
            elif "captured_output" in header_lower:
                col_idx = header_lower.index("captured_output")
                
            if valid_col in header_lower:
                val_idx = header_lower.index(valid_col)
            elif "valid_out" in header_lower:
                val_idx = header_lower.index("valid_out")
                
        for row in reader:
            if row and len(row) > col_idx:
                try:
                    if val_idx is not None and len(row) > val_idx:
                        if row[val_idx].strip() != "1":
                            continue
                    captured_samples.append(int(row[col_idx]))
                except ValueError:
                    pass

    print("=" * 65)
    print(f"ĐỐI CHIẾU DỮ LIỆU BỘ LỌC ({filter_mode.upper()}) GIỮA PHẦN CỨNG & PYTHON")
    print("=" * 65)
    print(f"Số mẫu chuẩn hợp lệ (Python):  {len(ref_samples)}")
    print(f"Số mẫu thu được từ Verilog/KIT: {len(captured_samples)}")

    check_len = min(len(ref_samples), len(captured_samples))
    mismatches = 0
    max_diff = 0

    for i in range(check_len):
        diff = abs(captured_samples[i] - ref_samples[i])
        if diff > 0:
            mismatches += 1
            if diff > max_diff:
                max_diff = diff
            if mismatches <= 5:
                print(f"  [Mẫu {i+7}]: Đo={captured_samples[i]}, Chuẩn={ref_samples[i]} (Lệch: {diff})")

    print("-" * 65)
    if mismatches == 0 and check_len > 0:
        print(">>>>> KẾT QUẢ: KHỚP HOÀN TOÀN 100% TỪNG BIT (0 MẪU LỆCH)! <<<<<")
        print("Mô hình Verilog trên KIT DE25 phản ánh chính xác số học Fixed-Point của Python.")
    else:
        print(f"[CẢNH BÁO] Phát hiện {mismatches}/{check_len} mẫu bị sai lệch! Độ lệch lớn nhất: {max_diff}")
    print("=" * 65)

if __name__ == "__main__":
    cap_path = sys.argv[1] if len(sys.argv) > 1 else "results/verilog_rom_output.csv"
    mode = sys.argv[2] if len(sys.argv) > 2 else "ma"
    compare_results(cap_path, filter_mode=mode)
