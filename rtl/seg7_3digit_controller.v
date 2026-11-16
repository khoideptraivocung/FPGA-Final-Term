// ============================================================================
// Module: seg7_3digit_controller
// Description: Time-multiplexed 3-digit 7-segment display controller for DE0-Nano
// Hardware: COMMON CATHODE (Cathode chung - Âm chung)
// Polarity:
//   - SEG[6:0]: Active-High (1 = Segment ON, 0 = Segment OFF)
//               SEG[0]=a, SEG[1]=b, SEG[2]=c, SEG[3]=d, SEG[4]=e, SEG[5]=f, SEG[6]=g
//   - DIG[2:0]: Active-Low  (0 = Digit ON/GND, 1 = Digit OFF)
//               DIG[2] = DIG 1 (Chân 12)
//               DIG[1] = DIG 2 (Chân 9)
//               DIG[0] = DIG 3 (Chân 8)
// Displays:
//   - DIG 1 (DIG[2]): Loại bộ lọc -> 'A' (Moving Average) hoặc 'F' (FIR)
//   - DIG 2 (DIG[1]): Nguồn vào   -> 'r' (ROM nội) hoặc 'U' (UART)
//   - DIG 3 (DIG[0]): Trạng thái  -> '-' (Nhấp nháy khi có mẫu valid_out)
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
    output reg  [6:0] SEG,         // Segments a..g (Common Cathode: 1 = ON, 0 = OFF)
    output reg  [2:0] DIG          // Digit Cathodes (Common Cathode: 0 = ON, 1 = OFF)
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

    // ------------------------------------------------------------------------
    // 7-Segment Patterns for COMMON CATHODE (1 = Segment ON, 0 = Segment OFF)
    // SEG = {g, f, e, d, c, b, a}
    // ------------------------------------------------------------------------
    localparam [6:0] CHAR_A     = 7'b111_0111; // 'A' (a,b,c,e,f,g = 1; d = 0)
    localparam [6:0] CHAR_F     = 7'b111_0001; // 'F' (a,e,f,g = 1; b,c,d = 0)
    localparam [6:0] CHAR_R     = 7'b101_0000; // 'r' (e,g = 1; others = 0)
    localparam [6:0] CHAR_U     = 7'b011_1110; // 'U' (b,c,d,e,f = 1; a,g = 0)
    localparam [6:0] CHAR_DASH  = 7'b100_0000; // '-' (g = 1; others = 0)
    localparam [6:0] CHAR_BLANK = 7'b000_0000; // Tất cả tắt (0 = OFF)

    wire [6:0] seg_dig1 = filter_sel ? CHAR_F : CHAR_A;
    wire [6:0] seg_dig2 = source_sel ? CHAR_U : CHAR_R;
    wire [6:0] seg_dig3 = (pulse_stretch > 0) ? CHAR_DASH : CHAR_BLANK;

    // ------------------------------------------------------------------------
    // Multiplexer: DIG select (Active-Low: 0 = Enable digit to GND)
    // ------------------------------------------------------------------------
    always @(*) begin
        case (digit_pos)
            2'd0: begin // DIG 1 (Bên trái)
                DIG = 3'b011; // DIG[2] = 0 (ON), DIG[1]=1 (OFF), DIG[0]=1 (OFF)
                SEG = seg_dig1;
            end
            2'd1: begin // DIG 2 (Ở giữa)
                DIG = 3'b101; // DIG[1] = 0 (ON), DIG[2]=1 (OFF), DIG[0]=1 (OFF)
                SEG = seg_dig2;
            end
            2'd2: begin // DIG 3 (Bên phải)
                DIG = 3'b110; // DIG[0] = 0 (ON), DIG[2]=1 (OFF), DIG[1]=1 (OFF)
                SEG = seg_dig3;
            end
            default: begin
                DIG = 3'b111; // Tất cả tắt
                SEG = CHAR_BLANK;
            end
        endcase
    end

endmodule
