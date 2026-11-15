"""
Topic 22 - Python fixed-point reference model
Arithmetic contract:
- Input/output: signed 12-bit
- MA: 8 valid samples, divide by 8, round-to-nearest ties away from zero
- FIR: 8 taps, signed Q1.15 coefficients, round-to-nearest ties away from zero
- Output: signed 12-bit saturation
- valid=0 means no new sample; history is held
- First output becomes valid after 8 valid input samples
"""
from pathlib import Path
import re
import numpy as np

N_TAPS = 8
# H=[4437,3023,3639,5285,5285,3639,3023,4437]
COEFF_Q15 = np.array([4437,3023,3639,5285,5285,3639,3023,4437], dtype=np.int32)
assert int(COEFF_Q15.sum()) == 32768

def round_shift_away_from_zero(value: int, shift: int) -> int:
    half = 1 << (shift - 1)
    if value >= 0:
        return (value + half) >> shift
    return -(((-value) + half) >> shift)

def saturate_signed(value: int, bits: int = 12) -> int:
    minimum = -(1 << (bits - 1))
    maximum = (1 << (bits - 1)) - 1
    return min(max(int(value), minimum), maximum)

def decode_signed_hex(word: str, bits: int = 12) -> int:
    value = int(word.strip(), 16)
    value &= (1 << bits) - 1
    if value & (1 << (bits - 1)):
        value -= (1 << bits)
    return value

def read_rom_mem(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    
    # Xử lý trường hợp file bị ghi dính chuỗi ký tự "\n" thay vì ký tự xuống dòng thật
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    
    values = []
    for line in text.splitlines():
        line = line.strip()
        # Bỏ qua dòng trống, dòng comment Verilog (//) hoặc Python (#)
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        
        # Bỏ qua các chỉ thị địa chỉ trong file mem (ví dụ: @00000000) nếu có
        if line.startswith("@"):
            continue

        # Nếu một dòng chứa nhiều từ hex cách nhau bởi khoảng trắng, tách từng từ
        words = line.split()
        for w in words:
            # Chỉ lấy các từ hex hợp lệ (tối đa 3 ký tự hex cho 12-bit)
            w_clean = re.sub(r"[^0-9a-fA-F]", "", w)
            if w_clean:
                values.append(decode_signed_hex(w_clean, 12))
                
    return np.asarray(values, dtype=np.int16)

def moving_average(samples, valid=None):
    if valid is None:
        valid = np.ones(len(samples), dtype=np.uint8)
    history, outputs, valids = [], [], []
    for sample, vin in zip(samples, valid):
        if vin:
            history.append(int(sample))
            if len(history) > N_TAPS:
                history.pop(0)
        if len(history) == N_TAPS and vin:
            acc = sum(history)
            y = round_shift_away_from_zero(acc, 3)
            outputs.append(saturate_signed(y, 12))
            valids.append(1)
        else:
            outputs.append(0)
            valids.append(0)
    return np.asarray(outputs, dtype=np.int16), np.asarray(valids, dtype=np.uint8)

def fir_lowpass(samples, valid=None):
    if valid is None:
        valid = np.ones(len(samples), dtype=np.uint8)
    history, outputs, valids = [], [], []
    for sample, vin in zip(samples, valid):
        if vin:
            history.append(int(sample))
            if len(history) > N_TAPS:
                history.pop(0)
        if len(history) == N_TAPS and vin:
            # history[0] là x[n-7], history[7] là x[n] (mới nhất)
            # Tích chập: h[0]*x[n] + h[1]*x[n-1] + ... + h[7]*x[n-7]
            acc = sum(int(c) * int(v) for c, v in zip(COEFF_Q15, reversed(history)))
            y = round_shift_away_from_zero(acc, 15)
            outputs.append(saturate_signed(y, 12))
            valids.append(1)
        else:
            outputs.append(0)
            valids.append(0)
    return np.asarray(outputs, dtype=np.int16), np.asarray(valids, dtype=np.uint8)

def main():
    import csv
    root = Path(__file__).resolve().parents[1]
    mem = root / "rom" / "test_vectors.mem"
    
    if not mem.exists():
        # Fallback tìm kiếm nếu đường dẫn tương đối khác
        print(f"Error: Không tìm thấy file {mem}")
        return

    samples = read_rom_mem(mem)
    ma, ma_v = moving_average(samples)
    fir, fir_v = fir_lowpass(samples)
    out = root / "results" / "python_reference.csv"
    out.parent.mkdir(exist_ok=True, parents=True)
    
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "input_signed", "ma_valid", "ma_output", "fir_valid", "fir_output"])
        for i, (xi, mv, my, fv, fy) in enumerate(zip(samples, ma_v, ma, fir_v, fir)):
            w.writerow([i, int(xi), int(mv), int(my), int(fv), int(fy)])
            
    print(f"Loaded {len(samples)} ROM samples")
    print(f"MA valid outputs: {int(ma_v.sum())}; FIR valid outputs: {int(fir_v.sum())}")
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()