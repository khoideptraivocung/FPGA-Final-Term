// ============================================================================
// Module: top_de25
// Description: Top-level integration for DE25 (Agilex 5) Kit
// Features:
//   - Input streams: Synthetic 1024-sample ROM or external UART RX
//   - Filter Core: 8-tap MA & FIR fixed-point filters with rounding & saturation
//   - Output Streams: UART TX to PC & Signal Tap logic analyzer bus
//   - Visuals: 7-segment display mode ('A'/'F', 'r'/'U') and status LEDs
// ============================================================================

module top_de25 (
    input  wire       clk,        // 50 MHz kit clock (PIN_CH128)
    input  wire       rst_n,      // KEY0 (PIN_BW59)
    input  wire       key1,       // KEY1 manual single-step trigger (PIN_CA59)
    input  wire [2:0] sw,         // SW[0]: filter_sel, SW[1]: source_sel, SW[2]: rom_enable
    
    // UART interface to PC
    input  wire       uart_rxd,   // Serial RX from PC
    output wire       uart_txd,   // Serial TX to PC
    
    // 7-segment displays
    output wire [6:0] hex0,       // Mode: 'A' (MA) or 'F' (FIR)
    output wire [6:0] hex1,       // Source: 'r' (ROM) or 'U' (UART)
    output wire [6:0] hex2,       // Status
    
    // Status LEDs
    output wire [6:0] ledr        // LEDR indicators
);

    // ------------------------------------------------------------------------
    // Control and Selection
    // ------------------------------------------------------------------------
    wire filter_sel = sw[0]; // 0: Moving Average, 1: FIR
    wire source_sel = sw[1]; // 0: ROM, 1: UART
    wire rom_enable = sw[2]; // 1: Auto-stream ROM at 1 kS/s

    // Debounce / detect edge on KEY1 for manual single-step
    reg key1_d1, key1_d2;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            key1_d1 <= 1'b1;
            key1_d2 <= 1'b1;
        end else begin
            key1_d1 <= key1;
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
        .SAMPLE_RATE_HZ(1_000) // Target >= 1,000 samples/sec
    ) u_rom_reader (
        .clk(clk),
        .rst_n(rst_n),
        .enable(rom_enable),
        .single_step(key1_press),
        .rom_valid(rom_valid),
        .rom_data(rom_data),
        .rom_addr(rom_addr)
    );

    wire               uart_valid;
    wire signed [11:0] uart_data;

    uart_rx #(
        .CLK_FREQ(50_000_000),
        .BAUD(115_200)
    ) u_uart_rx (
        .clk(clk),
        .rst_n(rst_n),
        .rx_pin(uart_rxd),
        .sample_valid(uart_valid),
        .sample_out(uart_data)
    );

    // Multiplex selected source into filter core
    wire               core_valid_in = source_sel ? uart_valid : rom_valid;
    wire signed [11:0] core_data_in  = source_sel ? uart_data  : rom_data;

    // ------------------------------------------------------------------------
    // 2. Sensor Digital Filter Core (MA / FIR)
    // ------------------------------------------------------------------------
    wire               core_valid_out;
    wire signed [11:0] core_data_out;

    sensor_filter_core u_filter_core (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(core_valid_in),
        .data_in(core_data_in),
        .filter_sel(filter_sel),
        .valid_out(core_valid_out),
        .data_out(core_data_out)
    );

    // ------------------------------------------------------------------------
    // 3. UART TX Output to PC
    // ------------------------------------------------------------------------
    wire uart_tx_busy;

    uart_tx #(
        .CLK_FREQ(50_000_000),
        .BAUD(115_200)
    ) u_uart_tx (
        .clk(clk),
        .rst_n(rst_n),
        .tx_start(core_valid_out),
        .sample_in(core_data_out),
        .tx_pin(uart_txd),
        .busy(uart_tx_busy)
    );

    // ------------------------------------------------------------------------
    // 4. 7-Segment Displays and LEDs
    // ------------------------------------------------------------------------
    seg7_decoder u_seg7 (
        .filter_sel(filter_sel),
        .source_sel(source_sel),
        .valid_out(core_valid_out),
        .hex0(hex0),
        .hex1(hex1),
        .hex2(hex2)
    );

    // LED indicators:
    // ledr[0]: valid_out pulse stretch for visibility
    reg [23:0] pulse_stretch;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pulse_stretch <= 24'd0;
        end else if (core_valid_out) begin
            pulse_stretch <= 24'd2_500_000; // ~50 ms flash at 50 MHz
        end else if (pulse_stretch > 24'd0) begin
            pulse_stretch <= pulse_stretch - 24'd1;
        end
    end

    assign ledr[0] = (pulse_stretch > 0);
    assign ledr[1] = filter_sel;
    assign ledr[2] = source_sel;
    assign ledr[6:3] = rom_addr[3:0];

    // ------------------------------------------------------------------------
    // 5. Signal Tap Logic Analyzer Probes
    // Preserve probe nets to prevent synthesis optimization
    // ------------------------------------------------------------------------
    (* keep = "true" *) wire               probe_valid_in  = core_valid_in;
    (* keep = "true" *) wire signed [11:0] probe_data_in   = core_data_in;
    (* keep = "true" *) wire               probe_filter_sel= filter_sel;
    (* keep = "true" *) wire               probe_valid_out = core_valid_out;
    (* keep = "true" *) wire signed [11:0] probe_data_out  = core_data_out;

endmodule
