// ============================================================================
// Module: uart_rx
// Description: UART Receiver (115200 Baud, 8-N-1)
//              Receives 2-byte signed 12-bit binary packets:
//              Byte 1: {4'b0, data[11:8]}
//              Byte 2: data[7:0]
// ============================================================================

module uart_rx #(
    parameter CLK_FREQ = 50_000_000,
    parameter BAUD     = 115_200
)(
    input  wire               clk,
    input  wire               rst_n,
    input  wire               rx_pin,
    output reg                sample_valid,
    output reg  signed [11:0] sample_out
);

    localparam integer BIT_TICKS = CLK_FREQ / BAUD;

    // Synchronize RX pin
    reg [1:0] rx_sync;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rx_sync <= 2'b11;
        else        rx_sync <= {rx_sync[0], rx_pin};
    end
    wire rx_in = rx_sync[1];

    // State machine
    localparam IDLE  = 2'd0;
    localparam START = 2'd1;
    localparam DATA  = 2'd2;
    localparam STOP  = 2'd3;

    reg [1:0]  state;
    reg [31:0] tick_count;
    reg [2:0]  bit_idx;
    reg [7:0]  rx_byte;
    reg        byte_ready;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= IDLE;
            tick_count <= 32'd0;
            bit_idx    <= 3'd0;
            rx_byte    <= 8'd0;
            byte_ready <= 1'b0;
        end else begin
            byte_ready <= 1'b0;
            case (state)
                IDLE: begin
                    if (!rx_in) begin // Falling edge: start bit
                        state      <= START;
                        tick_count <= 32'd0;
                    end
                end

                START: begin
                    if (tick_count == BIT_TICKS / 2) begin
                        if (!rx_in) begin
                            state      <= DATA;
                            tick_count <= 32'd0;
                            bit_idx    <= 3'd0;
                        end else begin
                            state <= IDLE;
                        end
                    end else begin
                        tick_count <= tick_count + 32'd1;
                    end
                end

                DATA: begin
                    if (tick_count == BIT_TICKS - 1) begin
                        tick_count         <= 32'd0;
                        rx_byte[bit_idx]   <= rx_in;
                        if (bit_idx == 3'd7) begin
                            state <= STOP;
                        end else begin
                            bit_idx <= bit_idx + 3'd1;
                        end
                    end else begin
                        tick_count <= tick_count + 32'd1;
                    end
                end

                STOP: begin
                    if (tick_count == BIT_TICKS - 1) begin
                        state      <= IDLE;
                        byte_ready <= 1'b1;
                    end else begin
                        tick_count <= tick_count + 32'd1;
                    end
                end
            endcase
        end
    end

    // 2-byte packet assembler
    reg       have_first_byte;
    reg [3:0] high_nibble;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            have_first_byte <= 1'b0;
            high_nibble     <= 4'd0;
            sample_valid    <= 1'b0;
            sample_out      <= 12'sd0;
        end else begin
            sample_valid <= 1'b0;
            if (byte_ready) begin
                if (!have_first_byte) begin
                    high_nibble     <= rx_byte[3:0];
                    have_first_byte <= 1'b1;
                end else begin
                    sample_out      <= {high_nibble, rx_byte};
                    sample_valid    <= 1'b1;
                    have_first_byte <= 1'b0;
                end
            end
        end
    end

endmodule
