// ============================================================================
// Module: seg7_3digit_controller
// Description: Time-multiplexed 3-digit 7-segment display controller for DE0-Nano
// Displays:
//   - DIG 1 (DIG[2]): Filter selection -> 'A' (Moving Average) or 'F' (FIR)
//   - DIG 2 (DIG[1]): Data source      -> 'r' (ROM nội) or 'U' (UART)
//   - DIG 3 (DIG[0]): System status    -> '-' (Nhấp nháy khi có mẫu valid_out)
// ============================================================================

module seg7_3digit_controller #(
    parameter CLK_FREQ_HZ = 50_000_000,
    parameter SCAN_FREQ_HZ = 1_000       // 1 kHz scan frequency (~333 Hz per digit)
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       filter_sel,  // 0: MA, 1: FIR
    input  wire       source_sel,  // 0: ROM, 1: UART
    input  wire       valid_out,   // Pulse on valid output sample
    output reg  [6:0] SEG,         // Segments a, b, c, d, e, f, g (Common Anode: 0=ON, 1=OFF)
    output reg  [2:0] DIG          // Digit enables: DIG[2]=DIG1, DIG[1]=DIG2, DIG[0]=DIG3
);

    // Refresh rate counter: 50 MHz / 1 kHz = 50,000 cycles
    localparam integer REFRESH_TICKS = CLK_FREQ_HZ / SCAN_FREQ_HZ;
    reg [17:0] clk_div;
    reg [1:0]  digit_pos; // 0, 1, 2 for the 3 digits

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_div   <= 18'd0;
            digit_pos <= 2'd0;
        end else begin
            if (clk_div >= REFRESH_TICKS - 1) begin
                clk_div <= 18'd0;
                if (digit_pos == 2'd2)
                    digit_pos <= 2'd0;
                else
                    digit_pos <= digit_pos + 2'd1;
            end else begin
                clk_div <= clk_div + 18'd1;
            end
        end
    end

    // Pulse stretcher for valid_out on DIG 3
    reg [23:0] pulse_stretch;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pulse_stretch <= 24'd0;
        end else if (valid_out) begin
            pulse_stretch <= 24'd2_500_000; // ~50 ms flash at 50 MHz
        end else if (pulse_stretch > 24'd0) begin
            pulse_stretch <= pulse_stretch - 24'd1;
        end
    end

    // 7-Segment Patterns (Common Anode: 0 = Segment ON, 1 = Segment OFF)
    // SEG[0]=a, SEG[1]=b, SEG[2]=c, SEG[3]=d, SEG[4]=e, SEG[5]=f, SEG[6]=g
    localparam [6:0] CHAR_A     = 7'b000_1000; // 'A' for Average: a,b,c,e,f,g ON
    localparam [6:0] CHAR_F     = 7'b000_1110; // 'F' for FIR: a,e,f,g ON
    localparam [6:0] CHAR_R     = 7'b010_1111; // 'r' for ROM: e,g ON
    localparam [6:0] CHAR_U     = 7'b100_0001; // 'U' for UART: b,c,d,e,f ON
    localparam [6:0] CHAR_DASH  = 7'b011_1111; // '-' for activity: g ON
    localparam [6:0] CHAR_BLANK = 7'b111_1111; // Blank: all OFF

    wire [6:0] seg_dig1 = filter_sel ? CHAR_F : CHAR_A;
    wire [6:0] seg_dig2 = source_sel ? CHAR_U : CHAR_R;
    wire [6:0] seg_dig3 = (pulse_stretch > 0) ? CHAR_DASH : CHAR_BLANK;

    // Multiplexer for segments and digit selector
    // Common Anode DIG pins: active-high enables the digit (Pin 12, 9, 8 connect to Anodes)
    always @(*) begin
        case (digit_pos)
            2'd0: begin // DIG 1
                DIG = 3'b100; // DIG[2] ON
                SEG = seg_dig1;
            end
            2'd1: begin // DIG 2
                DIG = 3'b010; // DIG[1] ON
                SEG = seg_dig2;
            end
            2'd2: begin // DIG 3
                DIG = 3'b001; // DIG[0] ON
                SEG = seg_dig3;
            end
            default: begin
                DIG = 3'b000;
                SEG = CHAR_BLANK;
            end
        endcase
    end

endmodule
