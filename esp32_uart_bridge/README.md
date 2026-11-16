# DOIT ESP32 DevKit V1 <--> DE0-Nano FPGA UART Bridge

Dự án PlatformIO dùng board **DOIT ESP32 DevKit V1** để truyền/nhận UART hai chiều tốc độ cao (115200 baud) với kit FPGA **Terasic DE0-Nano (Cyclone IV E)** cho đề tài Bộ lọc số tín hiệu cảm biến (Topic 22).

---

## 1. Sơ đồ nối dây TRỰC TIẾP (100% Tương thích 3.3V)

> [!TIP]
> **Ưu điểm vượt trội của ESP32 so với Arduino Uno:**
> - ESP32 hoạt động ở mức logic **3.3V**, hoàn toàn trùng khớp với chuẩn **3.3-V LVTTL** của FPGA Cyclone IV E.
> - **CẮM TRỰC TIẾP các dây nối, KHÔNG CẦN bất kỳ điện trở phân áp hay IC chuyển mức nào!**
> - Sử dụng phần cứng **UART2** độc lập trên ESP32, không xung đột với cổng nạp USB (UART0).

| Chân trên ESP32 DevKit | Chân Header JP1 DE0-Nano | Tên cổng trong Verilog | Hướng dữ liệu / Chức năng |
| :--- | :--- | :--- | :--- |
| **GND** | **Pin 12** | `GND` | **Nối Mass chung** (Bắt buộc) |
| **GPIO16 (RX2)** | **Pin 4** | `UART_TX` (`PIN_C3`) | ESP32 **nhận** kết quả lọc từ FPGA (cắm trực tiếp) |
| **GPIO17 (TX2)** | **Pin 2** | `UART_RX` (`PIN_D3`) | ESP32 **phát** mẫu cảm biến sang FPGA (cắm trực tiếp) |

---

## 2. Các phím lệnh điều khiển qua Serial Monitor

Mở Serial Monitor (tốc độ **115200 baud**), gõ phím và nhấn **Enter**:

| Phím lệnh | Chức năng thực thi |
| :---: | :--- |
| **`1`** | ESP32 gửi 1 mẫu thử nghiệm `+1000` sang FPGA |
| **`2`** | ESP32 gửi 1 mẫu thử nghiệm `-1000` sang FPGA |
| **`s`** | ESP32 tự động phát chuỗi **sóng sin 64 mẫu** (chu kỳ 32 mẫu, biên độ $\pm 1000$) |
| **`u`** | ESP32 phát **hàm bước nhảy (Step response)**: 16 mẫu `0` rồi nhảy vọt lên 16 mẫu `+1000` |
| **`c`** | Reset bộ đếm thống kê mẫu gửi/nhận |
| **`h`** | In lại menu hướng dẫn |

---

## 3. Lệnh nạp và giám sát bằng PlatformIO

- **Nạp firmware vào ESP32 (cổng COM21):**
  ```powershell
  & "C:\Users\DO DUC KHOI\.platformio\penv\Scripts\pio.exe" run -d "esp32_uart_bridge" -t upload
  ```
- **Mở Serial Monitor để điều khiển:**
  ```powershell
  & "C:\Users\DO DUC KHOI\.platformio\penv\Scripts\pio.exe" device monitor -d "esp32_uart_bridge"
  ```
