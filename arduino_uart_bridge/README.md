# Arduino Uno R3 <--> DE0-Nano FPGA UART Bridge

Dự án PlatformIO điều khiển truyền/nhận UART hai chiều giữa **Arduino Uno R3** và kit **Terasic DE0-Nano (Cyclone IV E)** cho đề tài Bộ lọc số tín hiệu cảm biến (Topic 22).

---

## 1. Sơ đồ nối dây (Wiring Pinout)

| Chân Arduino Uno R3 | Chân Header JP1 DE0-Nano | Tên tín hiệu FPGA | Chức năng / Lưu ý |
| :--- | :--- | :--- | :--- |
| **GND** | **Pin 12** | `GND` | **Nối Mass chung** (Bắt buộc) |
| **Pin 8 (RX)** | **Pin 4** | `UART_TX` (`PIN_C3`) | Arduino nhận chuỗi mẫu lọc từ FPGA (3.3V cắm thẳng vào Pin 8) |
| **Pin 9 (TX)** | **Pin 2** *(qua trở)* | `UART_RX` (`PIN_D3`) | Arduino phát mẫu cảm biến sang FPGA (Cần qua cầu phân áp) |

### ⚠️ LƯU Ý BẢO VỆ FPGA (3.3V vs 5V):
- Kit Cyclone IV E trên DE0-Nano hoạt động ở chuẩn **3.3-V LVTTL** (không chịu được điện áp 5V trực tiếp).
- Arduino Uno R3 ngõ ra TX phát điện áp **5V**.
- **Cách đấu cầu phân áp bảo vệ cho Pin 9 (TX Arduino $\rightarrow$ Pin 2 JP1):**
  ```text
  Arduino Pin 9 (TX 5V) ----[ 1k ohm ]----+----> Pin 2 Header JP1 (FPGA UART_RX ~3.3V)
                                       |
                                    [ 2k ohm ]
                                       |
                                      GND
  ```
  *(Nếu không có sẵn trở 1k/2k, có thể dùng trở 1k và 2.2k hoặc module hạ áp logic 5V $\rightarrow$ 3.3V).*

---

## 2. Các lệnh điều khiển qua Serial Monitor

Mở Serial Monitor ở tốc độ **115200 baud**, gửi các ký tự sau:

| Phím lệnh | Chức năng |
| :--- | :--- |
| **`1`** | Gửi 1 mẫu thử nghiệm giá trị `+1000` sang FPGA |
| **`2`** | Gửi 1 mẫu thử nghiệm giá trị `-1000` sang FPGA |
| **`s`** | Tự động phát chuỗi sóng sin 64 mẫu (chu kỳ 32 mẫu, biên độ $\pm 1000$) |
| **`u`** | Phát hàm bước nhảy (Step response: 16 mẫu 0 rồi nhảy lên 16 mẫu 1000) để đo trễ lọc |
| **`c`** | Reset bộ đếm số lượng mẫu đã gửi/nhận |
| **`h`** | Hiển thị menu hướng dẫn |

---

## 3. Cách nạp và chạy bằng PlatformIO

### Biên dịch:
```powershell
& "C:\Users\DO DUC KHOI\.platformio\penv\Scripts\pio.exe" run -d "arduino_uart_bridge"
```

### Nạp code vào Arduino Uno:
```powershell
& "C:\Users\DO DUC KHOI\.platformio\penv\Scripts\pio.exe" run -d "arduino_uart_bridge" -t upload
```

### Mở Serial Monitor:
```powershell
& "C:\Users\DO DUC KHOI\.platformio\penv\Scripts\pio.exe" device monitor -d "arduino_uart_bridge"
```
