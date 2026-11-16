/**
 * ============================================================================
 * Project: DOIT ESP32 DevKit V1 <--> DE0-Nano FPGA Intelligent UART Bridge
 * Board: DOIT ESP32 DEVKIT V1 (ESP-WROOM-32)
 * Baud rate: 115200 baud
 * 
 * Functions:
 *   1. Nhận lệnh từ Python GUI qua USB (UART0):ti
 *      - "D:<value>\n" -> Gửi 1 mẫu 12-bit signed [-2048, +2047] sang FPGA (2-byte binary)
 *      - "GEN:SINE\n"  -> Tự sinh sóng sin 64 mẫu
 *      - "GEN:STEP\n"  -> Tự sinh hàm bước nhảy
 *   2. Nhận kết quả lọc 6-byte (+XXXX\n / -XXXX\n) từ FPGA (UART2, GPIO16/17):
 *      - Chuyển tiếp ngay lập tức lên Python GUI qua USB
 * ============================================================================
 */

#include <Arduino.h>

#define PIN_FPGA_RX 16 // GPIO16 (RX2): Nhận từ FPGA Pin 4 JP1 (UART_TX)
#define PIN_FPGA_TX 17 // GPIO17 (TX2): Phát sang FPGA Pin 2 JP1 (UART_RX)
#define PIN_LED      2 // LED xanh trên ESP32

HardwareSerial fpgaSerial(2);

// Gửi mẫu nhị phân 2-byte sang FPGA: {4'b0, data[11:8]}, data[7:0]
void sendSampleToFPGA(int16_t sample) {
    if (sample > 2047) sample = 2047;
    if (sample < -2048) sample = -2048;

    uint16_t raw12 = (uint16_t)(sample & 0x0FFF);
    uint8_t byte1 = (uint8_t)((raw12 >> 8) & 0x0F);
    uint8_t byte2 = (uint8_t)(raw12 & 0x00FF);

    fpgaSerial.write(byte1);
    fpgaSerial.write(byte2);

    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
}

// Chuyển tiếp tức thì dữ liệu từ FPGA lên PC
void forwardFPGAToPC() {
    while (fpgaSerial.available()) {
        uint8_t b = fpgaSerial.read();
        Serial.write(b); // Chuyển thẳng lên PC
    }
}

// Xử lý lệnh từ PC gửi xuống
String pcCmd = "";

void processPCCommands() {
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            pcCmd.trim();
            if (pcCmd.length() > 0) {
                if (pcCmd.startsWith("D:") || pcCmd.startsWith("d:")) {
                    // Dữ liệu mẫu từ Python GUI: D:<số>
                    int16_t val = (int16_t)pcCmd.substring(2).toInt();
                    sendSampleToFPGA(val);
                } else if (pcCmd.equalsIgnoreCase("GEN:SINE") || pcCmd.equalsIgnoreCase("s")) {
                    for (int i = 0; i < 64; i++) {
                        float angle = 2.0 * PI * (float)i / 32.0;
                        int16_t val = (int16_t)(sin(angle) * 1000.0);
                        sendSampleToFPGA(val);
                        delay(5);
                        forwardFPGAToPC();
                    }
                } else if (pcCmd.equalsIgnoreCase("GEN:STEP") || pcCmd.equalsIgnoreCase("u")) {
                    for (int i = 0; i < 16; i++) { sendSampleToFPGA(0); delay(5); forwardFPGAToPC(); }
                    for (int i = 0; i < 16; i++) { sendSampleToFPGA(1000); delay(5); forwardFPGAToPC(); }
                } else if (pcCmd.equalsIgnoreCase("PING")) {
                    Serial.println("PONG:ESP32_READY");
                }
                pcCmd = "";
            }
        } else {
            pcCmd += c;
        }
    }
}

void setup() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    Serial.begin(115200);
    fpgaSerial.begin(115200, SERIAL_8N1, PIN_FPGA_RX, PIN_FPGA_TX);

    Serial.println("SYS:ESP32_BRIDGE_READY");
}

void loop() {
    forwardFPGAToPC();
    processPCCommands();
}
