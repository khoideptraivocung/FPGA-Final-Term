// ============================================================================
// Module: rom_sensor_reader
// Description: ROM reader for synthetic sensor test vectors (1024 samples)
//              Generates paced valid_in at selectable sample rates (>= 1 kS/s).
// ============================================================================

module rom_sensor_reader #(
    parameter MEM_FILE       = "test_vectors_clean.mem",
    parameter CLK_FREQ_HZ    = 50_000_000, // 50 MHz kit clock
    parameter SAMPLE_RATE_HZ = 1_000       // 1,000 samples/sec target
)(
    input  wire               clk,
    input  wire               rst_n,
    input  wire               enable,        // Enable reading
    input  wire               single_step,   // Manual single-step pulse (optional)
    output reg                rom_valid,
    output reg  signed [11:0] rom_data,
    output reg  [9:0]         rom_addr       // Current address 0..1023
);

    // 1024 words x 12 bits ROM array
    reg signed [11:0] rom_array [0:1023];

    initial begin
        $readmemh(MEM_FILE, rom_array);
    end

    // Sample rate pacer counter for Auto-Stream mode (enable = 1)
    // 50 MHz / 1 kHz = 50,000 clock cycles per sample
    localparam integer TICKS_PER_SAMPLE = CLK_FREQ_HZ / SAMPLE_RATE_HZ;
    reg [31:0] pacer_cnt;
    wire pacer_pulse = enable && (pacer_cnt >= TICKS_PER_SAMPLE - 1);

    // Reading trigger: either from manual single_step (KEY1) or auto pacer (SW2)
    wire step_trigger = single_step || pacer_pulse;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pacer_cnt <= 32'd0;
            rom_addr  <= 10'd0;
            rom_valid <= 1'b0;
            rom_data  <= 12'sd0;
        end else begin
            // Pacer counter advances when auto-streaming is enabled
            if (enable) begin
                if (pacer_cnt >= TICKS_PER_SAMPLE - 1)
                    pacer_cnt <= 32'd0;
                else
                    pacer_cnt <= pacer_cnt + 32'd1;
            end else begin
                pacer_cnt <= 32'd0;
            end

            // Emit sample on either single_step pulse or pacer pulse
            if (step_trigger) begin
                rom_data  <= rom_array[rom_addr];
                rom_valid <= 1'b1;
                rom_addr  <= rom_addr + 10'd1; // Wrap around after 1023
            end else begin
                rom_valid <= 1'b0;
            end
        end
    end

endmodule
