/**
 * ============================================================================
 * Project: Arduino Uno R3 UART Bridge & Sensor Streamer for DE0-Nano FPGA
 * Board: Arduino Uno R3 (ATmega328P @ 16 MHz)
 * Topic: Topic 22 - Sensor Digital Filter (MA & FIR)
 * 
 * Functions:
 *   1. Gửi chuỗi mẫu cảm biến (12-bit signed) sang FPGA qua gói nhị phân 2-byte:
 *      - Byte 1: {4'b0, data[11:8]}
 *      - Byte 2: data[7:0]
 *   2. Nhận kết quả lọc từ FPGA dạng chuỗi ASCII 6-byte (+XXXX\n hoặc -XXXX\n)
 *   3. Giao diện điều khiển qua Serial Monitor (PC USB) ở 115200 baud.
 * 
 * Hardware Connections:
 *   - Arduino Pin 8 (RX) <-- Nối trực tiếp từ FPGA Header JP1 Pin 4 (UART_TX)
 *   - Arduino Pin 9 (TX) --> Nối qua cầu phân áp (1k / 2k) tới FPGA Header JP1 Pin 2 (UART_RX)
 *   - Arduino GND        <-- Nối tới FPGA Header JP1 Pin 12 (GND chung)
 * 
 * LƯU Ý BẢO VỆ FPGA (3.3V vs 5V):
 *   - FPGA DE0-Nano dùng mức điện áp 3.3V LVTTL.
 *   - Arduino TX (5V) cần qua cầu phân áp (1k nối tiếp, 2k xuống GND) để giảm về ~3.3V
 *     trước khi vào chân UART_RX của FPGA.
 *   - FPGA TX (3.3V) có thể cắm trực tiếp vào Arduino RX (Pin 8).
 * ============================================================================
 */

#include <Arduino.h>
#include <SoftwareSerial.h>

// Cấu hình chân kết nối với FPGA
#define PIN_FPGA_RX 8 // Arduino nhận dữ liệu từ FPGA (FPGA TX -> Pin 8)
#define PIN_FPGA_TX 9 // Arduino gửi dữ liệu sang FPGA (Pin 9 -> FPGA RX qua trở)

// Khởi tạo cổng SoftwareSerial nối với FPGA
SoftwareSerial fpgaSerial(PIN_FPGA_RX, PIN_FPGA_TX);

// Cấu hình LED báo trạng thái trên Arduino Uno (Pin 13)
#define PIN_STATUS_LED 13

// Biến lưu trữ chuỗi nhận được từ FPGA
char rxBuffer[16];
uint8_t rxIndex = 0;
uint32_t totalSamplesSent = 0;
uint32_t totalSamplesReceived = 0;

/**
 * Gửi một mẫu số cảm biến signed 12-bit [-2048, +2047] sang FPGA
 * Giao thức: 2-byte nhị phân
 *   Byte 1: {4'b0, sample[11:8]}
 *   Byte 2: sample[7:0]
 */
void sendSampleToFPGA(int16_t sample) {
    // Bão hòa về dải 12-bit signed
    if (sample > 2047) sample = 2047;
    if (sample < -2048) sample = -2048;

    uint16_t raw12 = (uint16_t)(sample & 0x0FFF);
    uint8_t byte1 = (uint8_t)((raw12 >> 8) & 0x0F);
    uint8_t byte2 = (uint8_t)(raw12 & 0x00FF);

    fpgaSerial.write(byte1);
    fpgaSerial.write(byte2);
    totalSamplesSent++;

    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
}

/**
 * Đọc dữ liệu gửi về từ FPGA (+XXXX\n hoặc -XXXX\n)
 */
void processFPGAResponse() {
    while (fpgaSerial.available()) {
        char c = (char)fpgaSerial.read();
        if (c == '\n' || c == '\r') {
            if (rxIndex > 0) {
                rxBuffer[rxIndex] = '\0';
                totalSamplesReceived++;
                Serial.print(F("[FPGA OUT #"));
                Serial.print(totalSamplesReceived);
                Serial.print(F("]: "));
                Serial.println(rxBuffer);
                rxIndex = 0;
            }
        } else {
            if (rxIndex < sizeof(rxBuffer) - 1) {
                rxBuffer[rxIndex++] = c;
            } else {
                rxIndex = 0; // Tràn bộ đệm, reset
            }
        }
    }
}

/**
 * Gửi sóng hình sin thử nghiệm gồm n mẫu (biên độ +/- 1000)
 */
void sendTestSineWave(uint16_t numSamples, uint16_t delayMs) {
    Serial.println(F("\n>>> Đang phát sóng sin thử nghiệm sang FPGA..."));
    for (uint16_t i = 0; i < numSamples; i++) {
        float angle = 2.0 * 3.14159265 * (float)i / 32.0; // Chu kỳ 32 mẫu
        int16_t val = (int16_t)(sin(angle) * 1000.0);
        
        sendSampleToFPGA(val);
        
        Serial.print(F("Arduino TX ["));
        Serial.print(i + 1);
        Serial.print(F("]: "));
        if (val >= 0) Serial.print('+');
        Serial.println(val);

        // Kiểm tra và nhận phản hồi từ FPGA
        unsigned long startWait = millis();
        while (millis() - startWait < delayMs) {
            processFPGAResponse();
        }
    }
    Serial.println(F(">>> Hoàn thành phát sóng sin!\n"));
}

/**
 * Gửi hàm bước nhảy (Step Function: 0 -> 1000) để đo độ trễ đáp ứng của bộ lọc
 */
void sendStepFunction() {
    Serial.println(F("\n>>> Gửi hàm bước nhảy (Step Function) để kiểm tra độ trễ nhóm..."));
    // 16 mẫu 0
    for (int i = 0; i < 16; i++) {
        sendSampleToFPGA(0);
        delay(20);
        processFPGAResponse();
    }
    // 16 mẫu +1000
    for (int i = 0; i < 16; i++) {
        sendSampleToFPGA(1000);
        delay(20);
        processFPGAResponse();
    }
    Serial.println(F(">>> Hoàn thành gửi hàm bước nhảy!\n"));
}

void printHelp() {
    Serial.println(F("\n======================================================="));
    Serial.println(F("     ARDUINO UNO R3 <--> DE0-NANO FPGA UART BRIDGE     "));
    Serial.println(F("======================================================="));
    Serial.println(F("Các lệnh điều khiển (Gõ vào Serial Monitor rồi nhấn Enter):"));
    Serial.println(F("  '1' : Gửi 1 mẫu thử nghiệm (+1000) sang FPGA"));
    Serial.println(F("  '2' : Gửi 1 mẫu thử nghiệm (-1000) sang FPGA"));
    Serial.println(F("  's' : Phát chuỗi sóng sin 64 mẫu (chu kỳ 32 mẫu, +/-1000)"));
    Serial.println(F("  'u' : Phát hàm bước nhảy (Step response) để đo trễ"));
    Serial.println(F("  'c' : Reset bộ đếm số mẫu gửi/nhận"));
    Serial.println(F("  'h' : Hiển thị lại menu này"));
    Serial.println(F("=======================================================\n"));
}

void setup() {
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    // Khởi động Serial giao tiếp với PC
    Serial.begin(115200);
    while (!Serial && millis() < 2000); // Đợi Serial kết nối

    // Khởi động cổng kết nối với FPGA (115200 baud)
    fpgaSerial.begin(115200);

    printHelp();
}

void loop() {
    // 1. Luôn lắng nghe kết quả gửi về từ FPGA
    processFPGAResponse();

    // 2. Nhận lệnh từ Serial Monitor trên máy tính
    if (Serial.available()) {
        char cmd = (char)Serial.read();
        
        switch (cmd) {
            case '1':
                Serial.println(F("-> Gửi mẫu +1000 sang FPGA"));
                sendSampleToFPGA(1000);
                break;
            case '2':
                Serial.println(F("-> Gửi mẫu -1000 sang FPGA"));
                sendSampleToFPGA(-1000);
                break;
            case 's':
            case 'S':
                sendTestSineWave(64, 30); // 64 mẫu, giãn cách 30ms/mẫu
                break;
            case 'u':
            case 'U':
                sendStepFunction();
                break;
            case 'c':
            case 'C':
                totalSamplesSent = 0;
                totalSamplesReceived = 0;
                Serial.println(F("-> Đã reset bộ đếm mẫu về 0."));
                break;
            case 'h':
            case 'H':
                printHelp();
                break;
            case '\n':
            case '\r':
                break;
            default:
                Serial.print(F("Lệnh không xác định: '"));
                Serial.print(cmd);
                Serial.println(F("'. Gõ 'h' để xem menu hướng dẫn."));
                break;
        }
    }
}
