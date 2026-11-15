"""
Script vẽ đồ thị trực quan hóa kết quả từ reference_model.py
Đọc dữ liệu từ results/python_reference.csv và hiển thị:
1. Tín hiệu đầu vào (Input)
2. Kết quả lọc trung bình trượt (Moving Average)
3. Kết quả lọc thông thấp (FIR Lowpass)
"""

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd


def plot_reference_results():
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "results" / "python_reference.csv"

    if not csv_path.exists():
        print(f"Lỗi: Không tìm thấy file dữ liệu tại {csv_path}")
        print("Vui lòng chạy file reference_model.py trước để tạo file CSV.")
        return

    # Đọc dữ liệu từ file CSV đã xuất
    df = pd.read_csv(csv_path)

    # Khởi tạo khung đồ thị
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(
        "Topic 22 - Fixed-Point Reference Model Results",
        fontsize=14,
        fontweight="bold",
    )

    idx = df["index"]

    # 1. Đồ thị Tín hiệu đầu vào
    axes[0].plot(
        idx,
        df["input_signed"],
        color="steelblue",
        linewidth=1.2,
        label="Input (Signed 12-bit)",
    )
    axes[0].set_ylabel("Amplitude")
    axes[0].set_title("Input Signal (ROM Samples)")
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend(loc="upper right")

    # 2. Đồ thị Moving Average (MA)
    axes[1].plot(
        idx,
        df["input_signed"],
        color="lightgray",
        linewidth=0.8,
        label="Original Input",
    )
    # Lọc chỉ vẽ những điểm valid = 1 để thấy rõ độ trễ 8 mẫu ban đầu
    valid_ma = df[df["ma_valid"] == 1]
    axes[1].plot(
        valid_ma["index"],
        valid_ma["ma_output"],
        color="darkorange",
        linewidth=1.5,
        label="MA Output",
    )
    axes[1].set_ylabel("Amplitude")
    axes[1].set_title("Moving Average Filter (8-tap, Boxcar)")
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(loc="upper right")

    # 3. Đồ thị FIR Lowpass Filter
    axes[2].plot(
        idx,
        df["input_signed"],
        color="lightgray",
        linewidth=0.8,
        label="Original Input",
    )
    valid_fir = df[df["fir_valid"] == 1]
    axes[2].plot(
        valid_fir["index"],
        valid_fir["fir_output"],
        color="forestgreen",
        linewidth=1.5,
        label="FIR Output (Q1.15)",
    )
    axes[2].set_xlabel("Sample Index")
    axes[2].set_ylabel("Amplitude")
    axes[2].set_title("FIR Lowpass Filter (8-tap)")
    axes[2].grid(True, linestyle="--", alpha=0.6)
    axes[2].legend(loc="upper right")

    plt.tight_layout()

    # Lưu hình ảnh vào thư mục results
    output_png = root / "results" / "filter_comparison.png"
    plt.savefig(output_png, dpi=300)
    print(f"Đã lưu biểu đồ tại: {output_png}")

    # Hiển thị biểu đồ
    plt.show()


if __name__ == "__main__":
    plot_reference_results()