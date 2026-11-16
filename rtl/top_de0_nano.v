// ============================================================================
// Module: top_de0_nano
// Board: Terasic DE0-Nano (Cyclone IV E EP4CE22F17C6N)
// Description: Top-level integration for Sensor Digital Filter (MA & FIR)
// Peripherals on DE0-Nano:
//   - CLOCK_50 : 50 MHz oscillator (PIN_R8)
//   - KEY[0]   : Reset active-low (PIN_J15)
//   - KEY[1]   : Single-step manual sample trigger (PIN_E1)
//   - SW[0]    : Filter select (0: Moving Average, 1: FIR) (PIN_M1)
//   - SW[1]    : Source select (0: ROM, 1: UART RX) (PIN_T8)
//   - SW[2]    : ROM Auto-stream enable (1: Stream at 1 kS/s) (PIN_B9)
//   - LED[7:0] : On-board status and filter mode indicators (PIN_A15, etc.)
// Expansion GPIO_0 (JP1 Header - Optional):
//   - GPIO_0[6:0]: 7-segment display module (segments a..g)
//   - GPIO_0[7]  : UART TX (Serial output to PC)
//   - GPIO_0[8]  : UART RX (Serial input from PC/Sensor)
// ============================================================================

module top_de0_nano (
    // On-board Clock
    input  wire        CLOCK_50,
    
    // On-board Push Buttons (Active-Low)
    input  wire [1:0]  KEY,
    
    // On-board DIP Switches
    input  wire [2:0]  SW,
    
    // On-board 8 Green LEDs (Active-High)
    output wire [7:0]  LED,
    
    // Optional Expansion Pins on GPIO_0 header (JP1)
    output wire [6:0]  gpio_hex,    // Optional 7-segment display on GPIO_0[6:0]
    output wire        gpio_uart_tx,// UART TX pin on GPIO_0[7]
    input  wire        gpio_uart_rx // UART RX pin on GPIO_0[8]
);

    // ------------------------------------------------------------------------
    // Control and Selection Mapping
    // ------------------------------------------------------------------------
    wire rst_n      = KEY[0]; // Active-low reset
    wire filter_sel = SW[0];  // 0: Moving Average, 1: FIR
    wire source_sel = SW[1];  // 0: ROM nội, 1: UART RX ngoài
    wire rom_enable = SW[2];  // 1: Tự phát 1024 mẫu ROM ở 1.000 mẫu/giây

    // Debounce / Edge detection on KEY[1] for single-step manual sample
    reg key1_d1, key1_d2;
    always @(posedge CLOCK_50 or negedge rst_n) begin
        if (!rst_n) begin
            key1_d1 <= 1'b1;
            key1_d2 <= 1'b1;
        end else begin
            key1_d1 <= KEY[1];
            key1_d2 <= key1_d1;
        end
    end
    wire key1_press = (key1_d2 == 1'b1) && (key1_d1 == 1'b0);

    // ------------------------------------------------------------------------
    // 1. Input Sources: ROM Reader & UART RX
    // ------------------------------------------------------------------------
    wire               rom_valid;
    wire signed [11:0] rom_data;
    wire [9:0]         rom_addr;

    rom_sensor_reader #(
        .MEM_FILE("test_vectors_clean.mem"),
        .CLK_FREQ_HZ(50_000_000),
        .SAMPLE_RATE_HZ(1_000) // Đạt chuẩn >= 1.000 mẫu/giây
    ) u_rom_reader (
        .clk(CLOCK_50),
        .rst_n(rst_n),
        .enable(rom_enable),
        .single_step(key1_press),
        .rom_valid(rom_valid),
        .rom_data(rom_data),
        .rom_addr(rom_addr)
    );

    wire               uart_valid;
    wire signed [11:0] uart_data;

    // Pull-up for RX if pin is floating
    wire uart_rx_in = (gpio_uart_rx === 1'bz) ? 1'b1 : gpio_uart_rx;

    uart_rx #(
        .CLK_FREQ(50_000_000),
        .BAUD(115_200)
    ) u_uart_rx (
        .clk(CLOCK_50),
        .rst_n(rst_n),
        .rx_pin(uart_rx_in),
        .sample_valid(uart_valid),
        .sample_out(uart_data)
    );

    // Multiplexer: Select between ROM and UART RX
    wire               core_valid_in = source_sel ? uart_valid : rom_valid;
    wire signed [11:0] core_data_in  = source_sel ? uart_data  : rom_data;

    // ------------------------------------------------------------------------
    // 2. Sensor Digital Filter Core (MA 8-sample & FIR 8-tap Q1.15)
    // ------------------------------------------------------------------------
    wire               core_valid_out;
    wire signed [11:0] core_data_out;

    sensor_filter_core u_filter_core (
        .clk(CLOCK_50),
        .rst_n(rst_n),
        .valid_in(core_valid_in),
        .data_in(core_data_in),
        .filter_sel(filter_sel),
        .valid_out(core_valid_out),
        .data_out(core_data_out)
    );

    // ------------------------------------------------------------------------
    // 3. UART TX Output (Serial stream to PC at 115200 baud)
    // ------------------------------------------------------------------------
    wire uart_tx_busy;

    uart_tx #(
        .CLK_FREQ(50_000_000),
        .BAUD(115_200)
    ) u_uart_tx (
        .clk(CLOCK_50),
        .rst_n(rst_n),
        .tx_start(core_valid_out),
        .sample_in(core_data_out),
        .tx_pin(gpio_uart_tx),
        .busy(uart_tx_busy)
    );

    // ------------------------------------------------------------------------
    // 4. 7-Segment Decoder (Optional external module on GPIO_0)
    // ------------------------------------------------------------------------
    wire [6:0] hex0_wire;
    wire [6:0] hex1_wire;
    wire [6:0] hex2_wire;

    seg7_decoder u_seg7 (
        .filter_sel(filter_sel),
        .source_sel(source_sel),
        .valid_out(core_valid_out),
        .hex0(hex0_wire),
        .hex1(hex1_wire),
        .hex2(hex2_wire)
    );

    assign gpio_hex = hex0_wire; // 'A' (MA) hoặc 'F' (FIR)

    // ------------------------------------------------------------------------
    // 5. On-Board 8 LEDs Display (Active-High: 1 = ON)
    // ------------------------------------------------------------------------
    // Pulse stretch for valid_out so it's clearly visible to human eye
    reg [23:0] pulse_stretch;
    always @(posedge CLOCK_50 or negedge rst_n) begin
        if (!rst_n) begin
            pulse_stretch <= 24'd0;
        end else if (core_valid_out) begin
            pulse_stretch <= 24'd2_500_000; // ~50 ms flash at 50 MHz
        end else if (pulse_stretch > 24'd0) begin
            pulse_stretch <= pulse_stretch - 24'd1;
        end
    end

    // LED[0]: Valid Out blinker
    assign LED[0] = (pulse_stretch > 0);

    // LED[1]: Filter mode (0 = Tắt cho Moving Average, 1 = Sáng cho FIR)
    assign LED[1] = filter_sel;

    // LED[2]: Data source (0 = Tắt cho ROM, 1 = Sáng cho UART)
    assign LED[2] = source_sel;

    // LED[3]: ROM streaming active
    assign LED[3] = rom_enable;

    // LED[7:4]: ROM address low nibble (hiển thị ROM đang quét mẫu)
    assign LED[7:4] = rom_addr[3:0];

    // ------------------------------------------------------------------------
    // 6. Signal Tap Logic Analyzer Probes
    // ------------------------------------------------------------------------
    (* keep = "true" *) wire               probe_valid_in   = core_valid_in;
    (* keep = "true" *) wire signed [11:0] probe_data_in    = core_data_in;
    (* keep = "true" *) wire               probe_filter_sel = filter_sel;
    (* keep = "true" *) wire               probe_valid_out  = core_valid_out;
    (* keep = "true" *) wire signed [11:0] probe_data_out   = core_data_out;

endmodule
