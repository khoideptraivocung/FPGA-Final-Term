// ============================================================================
// Module: seg7_decoder
// Description: Decodes filter selection and status onto 7-segment displays
//              Common Anode: 0 = segment ON, 1 = segment OFF
//              Segments: {g, f, e, d, c, b, a}
// ============================================================================

module seg7_decoder (
    input  wire       filter_sel,   // 0: Moving Average ('A'), 1: FIR ('F')
    input  wire       source_sel,   // 0: ROM ('r'), 1: UART ('U')
    input  wire       valid_out,    // Activity indicator
    output reg  [6:0] hex0,         // Filter mode display
    output reg  [6:0] hex1,         // Source mode display
    output reg  [6:0] hex2          // Status display (dot or tick)
);

    // HEX0: Filter mode display
    always @(*) begin
        if (filter_sel == 1'b0) begin
            // Display 'A' for Average: segments a, b, c, e, f, g ON (d OFF)
            hex0 = 7'b000_1000;
        end else begin
            // Display 'F' for FIR: segments a, e, f, g ON (b, c, d OFF)
            hex0 = 7'b000_1110;
        end
    end

    // HEX1: Source mode display
    always @(*) begin
        if (source_sel == 1'b0) begin
            // Display 'r' for ROM: segments e, g ON
            hex1 = 7'b010_1111;
        end else begin
            // Display 'U' for UART: segments b, c, d, e, f ON
            hex1 = 7'b100_0001;
        end
    end

    // HEX2: Activity indicator (segments toggle with valid_out)
    always @(*) begin
        if (valid_out) begin
            hex2 = 7'b011_1111; // center dash '-'
        end else begin
            hex2 = 7'b111_1111; // blank
        end
    end

endmodule
