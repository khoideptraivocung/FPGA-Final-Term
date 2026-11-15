// ============================================================================
// Module: uart_tx
// Description: UART Transmitter (115200 Baud, 8-N-1)
//              Formats signed 12-bit sample as 6-byte ASCII: '+1023\n'
// ============================================================================

module uart_tx #(
    parameter CLK_FREQ = 50_000_000,
    parameter BAUD     = 115_200
)(
    input  wire               clk,
    input  wire               rst_n,
    input  wire               tx_start,
    input  wire signed [11:0] sample_in,
    output reg                tx_pin,
    output wire               busy
);

    localparam integer BIT_TICKS = CLK_FREQ / BAUD;

    // Convert signed 12-bit [-2048, 2047] to ASCII string:
    // Format: [Sign][Thousands][Hundreds][Tens][Units]['\n'] (6 bytes)
    reg [7:0] bytes_to_send [0:5];
    reg [2:0] byte_idx;
    reg [2:0] total_bytes;

    reg [31:0] tick_count;
    reg [3:0]  bit_idx;
    reg [9:0]  shift_reg; // start (0) + 8 data + stop (1)
    reg        transmitting;

    assign busy = transmitting || (byte_idx < total_bytes);

    integer abs_val;
    integer u, t, h, th;

    // Buffer samples and convert to ASCII
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byte_idx     <= 3'd0;
            total_bytes  <= 3'd0;
            transmitting <= 1'b0;
            tx_pin       <= 1'b1;
            tick_count   <= 32'd0;
            bit_idx      <= 4'd0;
            shift_reg    <= 10'h3FF;
        end else begin
            if (tx_start && !busy) begin
                // Format ASCII
                if (sample_in < 12'sd0) begin
                    bytes_to_send[0] <= 8'h2D; // '-'
                    abs_val = -sample_in;
                end else begin
                    bytes_to_send[0] <= 8'h2B; // '+'
                    abs_val = sample_in;
                end
                
                th = (abs_val / 1000) % 10;
                h  = (abs_val / 100) % 10;
                t  = (abs_val / 10) % 10;
                u  = abs_val % 10;

                bytes_to_send[1] <= 8'd48 + th[7:0];
                bytes_to_send[2] <= 8'd48 + h[7:0];
                bytes_to_send[3] <= 8'd48 + t[7:0];
                bytes_to_send[4] <= 8'd48 + u[7:0];
                bytes_to_send[5] <= 8'h0A; // '\n'

                byte_idx    <= 3'd0;
                total_bytes <= 3'd6;
            end

            // Byte transmission engine
            if (!transmitting && (byte_idx < total_bytes)) begin
                // Start sending current byte
                shift_reg    <= {1'b1, bytes_to_send[byte_idx], 1'b0};
                transmitting <= 1'b1;
                tick_count   <= 32'd0;
                bit_idx      <= 4'd0;
            end else if (transmitting) begin
                if (tick_count < BIT_TICKS - 1) begin
                    tick_count <= tick_count + 32'd1;
                end else begin
                    tick_count <= 32'd0;
                    tx_pin     <= shift_reg[0];
                    shift_reg  <= {1'b1, shift_reg[9:1]};
                    bit_idx    <= bit_idx + 4'd1;

                    if (bit_idx == 4'd9) begin
                        transmitting <= 1'b0;
                        byte_idx     <= byte_idx + 3'd1;
                    end
                end
            end else begin
                tx_pin <= 1'b1;
            end
        end
    end

endmodule
