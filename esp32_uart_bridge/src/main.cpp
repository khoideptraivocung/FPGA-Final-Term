/**
 * ============================================================================
 * Project: DOIT ESP32 DevKit V1 <--> DE0-Nano FPGA UART Bridge
 * Board: DOIT ESP32 DEVKIT V1 (ESP-WROOM-32 @ 240 MHz)
 * Topic: Topic 22 - Sensor Digital Filter (MA & FIRục đi
 * 
 * ƯU ĐIỂM KHI DÙNG ESP32:
 *   1. Điện áp chuẩn 3.3V: Khớp 100% với chuẩn 3.3-V LVTTL của Cyclone IV E trên DE0-Nano.
 *      --> CẮM TRỰC TIẾP, KHÔNG CẦN CẦU PHÂN ÁP HAY IC CHUYỂN MỨC!
 *   2. Đa phần cứng UART (Hardware Serial):
 *      - Serial  (UART0): Giao tiếp với PC qua cáp Micro-USB (115200 baud).
 *      - Serial2 (UART2): Giao tiếp riêng biệt tốc độ cao với FPGA (115200 baud).
 * 
 * SƠ ĐỒ NỐI DÂY TRỰC TIẾP:
 *   - ESP32 GND     <--> FPGA Header JP1 Pin 12 (GND)
 *   - ESP32 GPIO16  <--> FPGA Header JP1 Pin 4  (UART_TX, PIN_C3 - ESP32 nhận từ FPGA)
 *   - ESP32 GPIO17  <--> FPGA Header JP1 Pin 2  (UART_RX, PIN_D3 - ESP32 gửi sang FPGA)
 * ============================================================================
 */

#include <Arduino.h>

// Định nghĩa chân Hardware UART2 kết nối với FPGA
#define PIN_FPGA_RX 16 // GPIO16 (RX2): Nhận dữ liệu từ FPGA TX
#define PIN_FPGA_TX 17 // GPIO17 (TX2): Phát dữ liệu sang FPGA RX
#define PIN_LED      2 // LED xanh tích hợp trên kit DOIT ESP32

// Sử dụng Hardware Serial 2
HardwareSerial fpgaSerial(2);

// Bộ đệm nhận dữ liệu từ FPGA
char rxBuffer[32];
uint8_t rxIndex = 0;
uint32_t totalSent = 0;
uint32_t totalRecv = 0;

/**
 * Gửi một mẫu số cảm biến signed 12-bit [-2048, +2047] sang FPGA
 * Giao thức: 2-byte nhị phân
 *   Byte 1: {4'b0, sample[11:8]}
 *   Byte 2: sample[7:0]
 */
void sendSampleToFPGA(int16_t sample) {
    if (sample > 2047) sample = 2047;
    if (sample < -2048) sample = -2048;

    uint16_t raw12 = (uint16_t)(sample & 0x0FFF);
    uint8_t byte1 = (uint8_t)((raw12 >> 8) & 0x0F);
    uint8_t byte2 = (uint8_t)(raw12 & 0x00FF);

    fpgaSerial.write(byte1);
    fpgaSerial.write(byte2);
    totalSent++;

    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
}

/**
 * Nhận chuỗi mẫu đã lọc từ FPGA (+XXXX\n hoặc -XXXX\n)
 */
void processFPGAResponse() {
    while (fpgaSerial.available()) {
        char c = (char)fpgaSerial.read();
        if (c == '\n' || c == '\r') {
            if (rxIndex > 0) {
                rxBuffer[rxIndex] = '\0';
                totalRecv++;
                Serial.printf("[FPGA OUT #%u]: %s\n", totalRecv, rxBuffer);
                rxIndex = 0;
            }
        } else {
            if (rxIndex < sizeof(rxBuffer) - 1) {
                rxBuffer[rxIndex++] = c;
            } else {
                rxIndex = 0;
            }
        }
    }
}

/**
 * Phát sóng sin thử nghiệm 64 mẫu (biên độ +/- 1000)
 */
void sendSineWave(uint16_t count, uint16_t delayMs) {
    Serial.printf("\n>>> Đang phát chuỗi sóng sin %u mẫu sang FPGA...\n", count);
    for (uint16_t i = 0; i < count; i++) {
        float angle = 2.0 * PI * (float)i / 32.0; // Chu kỳ 32 mẫu
        int16_t val = (int16_t)(sin(angle) * 1000.0);

        sendSampleToFPGA(val);
        Serial.printf("ESP32 TX [%3u]: %+5d\n", i + 1, val);

        unsigned long startWait = millis();
        while (millis() - startWait < delayMs) {
            processFPGAResponse();
        }
    }
    Serial.println(F(">>> Hoàn tất phát sóng sin!\n"));
}

/**
 * Gửi hàm bước nhảy (Step Response) để đo độ trễ nhóm của bộ lọc
 */
void sendStepFunction() {
    Serial.println(F("\n>>> Gửi hàm bước nhảy (Step Function: 16 mẫu 0 -> 16 mẫu 1000)..."));
    // 16 mẫu mức 0
    for (int i = 0; i < 16; i++) {
        sendSampleToFPGA(0);
        delay(15);
        processFPGAResponse();
    }
    // 16 mẫu mức +1000
    for (int i = 0; i < 16; i++) {
        sendSampleToFPGA(1000);
        delay(15);
        processFPGAResponse();
    }
    Serial.println(F(">>> Hoàn tất gửi hàm bước nhảy!\n"));
}

void printHelp() {
    Serial.println(F("\n======================================================="));
    Serial.println(F("   DOIT ESP32 DEVKIT V1 <--> DE0-NANO FPGA UART BRIDGE  "));
    Serial.println(F("======================================================="));
    Serial.println(F("Các phím lệnh (Gõ vào Serial Monitor rồi nhấn Enter):"));
    Serial.println(F("  '1' : Gửi 1 mẫu (+1000) sang FPGA"));
    Serial.println(F("  '2' : Gửi 1 mẫu (-1000) sang FPGA"));
    Serial.println(F("  's' : Phát chuỗi sóng sin 64 mẫu (chu kỳ 32 mẫu, +/-1000)"));
    Serial.println(F("  'u' : Phát hàm bước nhảy (Step response) để đo trễ"));
    Serial.println(F("  'c' : Reset bộ đếm thống kê mẫu"));
    Serial.println(F("  'h' : In lại menu hướng dẫn này"));
    Serial.println(F("=======================================================\n"));
}

void setup() {
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    // UART0: Giao tiếp với máy tính qua cổng USB
    Serial.begin(115200);
    delay(500);

    // UART2: Giao tiếp với FPGA DE0-Nano (RX=GPIO16, TX=GPIO17, 115200 baud, 8-N-1)
    fpgaSerial.begin(115200, SERIAL_8N1, PIN_FPGA_RX, PIN_FPGA_TX);

    printHelp();
}

void loop() {
    // 1. Luôn lắng nghe kết quả từ FPGA
    processFPGAResponse();

    // 2. Nhận lệnh từ Serial Monitor
    if (Serial.available()) {
        char cmd = (char)Serial.read();

        switch (cmd) {
            case '1':
                Serial.println(F("-> ESP32 gửi mẫu: +1000"));
                sendSampleToFPGA(1000);
                break;
            case '2':
                Serial.println(F("-> ESP32 gửi mẫu: -1000"));
                sendSampleToFPGA(-1000);
                break;
            case 's':
            case 'S':
                sendSineWave(64, 25);
                break;
            case 'u':
            case 'U':
                sendStepFunction();
                break;
            case 'c':
            case 'C':
                totalSent = 0;
                totalRecv = 0;
                Serial.println(F("-> Đã reset bộ đếm thống kê về 0."));
                break;
            case 'h':
            case 'H':
                printHelp();
                break;
            case '\n':
            case '\r':
                break;
            default:
                Serial.printf("Lệnh không xác định: '%c'. Gõ 'h' để xem menu.\n", cmd);
                break;
        }
    }
}
