// ============================================================================
// Module: sensor_filter_core
// Description: Fixed-point 8-sample Moving Average and 8-tap FIR Filter
// Features:
//   - Input/Output: 12-bit signed two's complement [-2048, 2047]
//   - MA: 8 valid samples window, divide by 8, round ties away from zero
//   - FIR: 8 taps, signed Q1.15 coefficients, round ties away from zero
//   - Saturated output: [-2048, +2047]
//   - Valid control: valid_in=0 halts history shift and sample count
//   - Startup: valid_out remains 0 until 8 valid samples have been accumulated
// ============================================================================

module sensor_filter_core #(
    // Q1.15 fixed-point FIR coefficients (sum = 32768, DC gain = 1.0)
    parameter signed [15:0] COEFF_0 = 16'sd4437,
    parameter signed [15:0] COEFF_1 = 16'sd3023,
    parameter signed [15:0] COEFF_2 = 16'sd3639,
    parameter signed [15:0] COEFF_3 = 16'sd5285,
    parameter signed [15:0] COEFF_4 = 16'sd5285,
    parameter signed [15:0] COEFF_5 = 16'sd3639,
    parameter signed [15:0] COEFF_6 = 16'sd3023,
    parameter signed [15:0] COEFF_7 = 16'sd4437
)(
    input  wire                    clk,
    input  wire                    rst_n,        // Active-low asynchronous reset
    input  wire                    valid_in,     // Sample valid strobe
    input  wire signed [11:0]      data_in,      // 12-bit signed sensor sample
    input  wire                    filter_sel,   // 0: Moving Average, 1: FIR Filter
    output reg                     valid_out,    // Filtered output valid
    output reg  signed [11:0]      data_out      // 12-bit signed filtered output
);

    // ------------------------------------------------------------------------
    // 1. History Shift Register (8 samples delay line)
    //    history[0] = oldest (x[n-7]), history[7] = newest (x[n])
    // ------------------------------------------------------------------------
    reg signed [11:0] history [0:7];
    reg [3:0]         valid_count;   // Count up to 8 valid samples
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 8; i = i + 1) begin
                history[i] <= 12'sd0;
            end
            valid_count <= 4'd0;
        end else if (valid_in) begin
            // Shift history
            history[0] <= history[1];
            history[1] <= history[2];
            history[2] <= history[3];
            history[3] <= history[4];
            history[4] <= history[5];
            history[5] <= history[6];
            history[6] <= history[7];
            history[7] <= data_in;

            // Increment valid counter until 8
            if (valid_count < 4'd8) begin
                valid_count <= valid_count + 4'd1;
            end
        end
        // When valid_in == 0: history and valid_count hold unchanged
    end

    // ------------------------------------------------------------------------
    // Effective samples for current calculation on posedge clk when valid_in=1
    // When valid_in is high, the current window consists of history[1..7] and data_in.
    // ------------------------------------------------------------------------
    wire signed [11:0] w_samples [0:7];
    assign w_samples[0] = history[1];
    assign w_samples[1] = history[2];
    assign w_samples[2] = history[3];
    assign w_samples[3] = history[4];
    assign w_samples[4] = history[5];
    assign w_samples[5] = history[6];
    assign w_samples[6] = history[7];
    assign w_samples[7] = data_in;      // Newest sample

    // ------------------------------------------------------------------------
    // 2. Moving Average Filter Logic
    // ------------------------------------------------------------------------
    // Accumulator: 8 * [-2048, 2047] -> [-16384, +16376], fits in signed 16-bit
    wire signed [15:0] ma_acc = w_samples[0] + w_samples[1] + w_samples[2] + w_samples[3] +
                               w_samples[4] + w_samples[5] + w_samples[6] + w_samples[7];

    // Rounding: divide by 8 (shift 3), round-to-nearest, ties away from zero
    // Half value for shift 3 is 4 (1 << 2)
    wire signed [16:0] ma_rounded = (ma_acc >= 16'sd0) ? (ma_acc + 16'sd4) : (ma_acc - 16'sd4);
    wire signed [13:0] ma_div     = ma_rounded >>> 3;

    // Saturated 12-bit output [-2048, 2047]
    wire signed [11:0] ma_sat = (ma_div > 14'sd2047)  ? 12'sd2047 :
                                (ma_div < -14'sd2048) ? 12'h800 :
                                ma_div[11:0];

    // ------------------------------------------------------------------------
    // 3. FIR Filter Logic (8 taps, Q1.15)
    //    y[n] = sum(h[k] * x[n-k])
    //    h[0] * w_samples[7] (x[n]) + ... + h[7] * w_samples[0] (x[n-7])
    // ------------------------------------------------------------------------
    // 28-bit signed multiplication (12-bit signed * 16-bit signed)
    wire signed [27:0] fir_prod [0:7];
    assign fir_prod[0] = w_samples[7] * COEFF_0; // newest x[n]   * h[0]
    assign fir_prod[1] = w_samples[6] * COEFF_1; // x[n-1]        * h[1]
    assign fir_prod[2] = w_samples[5] * COEFF_2; // x[n-2]        * h[2]
    assign fir_prod[3] = w_samples[4] * COEFF_3; // x[n-3]        * h[3]
    assign fir_prod[4] = w_samples[3] * COEFF_4; // x[n-4]        * h[4]
    assign fir_prod[5] = w_samples[2] * COEFF_5; // x[n-5]        * h[5]
    assign fir_prod[6] = w_samples[1] * COEFF_6; // x[n-6]        * h[6]
    assign fir_prod[7] = w_samples[0] * COEFF_7; // oldest x[n-7] * h[7]

    // 32-bit signed accumulation
    wire signed [31:0] fir_acc = fir_prod[0] + fir_prod[1] + fir_prod[2] + fir_prod[3] +
                                fir_prod[4] + fir_prod[5] + fir_prod[6] + fir_prod[7];

    // Rounding: divide by 32768 (shift 15), round-to-nearest, ties away from zero
    // Half value for shift 15 is 16384 (1 << 14)
    wire signed [32:0] fir_rounded = (fir_acc >= 32'sd0) ? (fir_acc + 33'sd16384) : (fir_acc - 33'sd16384);
    wire signed [17:0] fir_div     = fir_rounded >>> 15;

    // Saturated 12-bit output [-2048, 2047]
    wire signed [11:0] fir_sat = (fir_div > 18'sd2047)  ? 12'sd2047 :
                                 (fir_div < -18'sd2048) ? 12'h800 :
                                 fir_div[11:0];

    // ------------------------------------------------------------------------
    // 4. Output Registering & Valid Control
    //    Output is registered on posedge clk with 1 cycle latency when valid_in=1
    // ------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            data_out  <= 12'sd0;
        end else if (valid_in) begin
            // Ready when at least 8 valid samples received
            if (valid_count >= 4'd7) begin
                valid_out <= 1'b1;
                data_out  <= filter_sel ? fir_sat : ma_sat;
            end else begin
                valid_out <= 1'b0;
                data_out  <= 12'sd0;
            end
        end else begin
            // When valid_in is 0, valid_out is deasserted
            valid_out <= 1'b0;
        end
    end

endmodule
