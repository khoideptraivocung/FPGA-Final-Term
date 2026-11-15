# Topic 22 — Specification v1.0 (simulation-first)

## Configuration
- ROM depth: 1024 samples
- Input: signed 12-bit two's-complement
- Moving average: 8 samples
- FIR: 8-tap low-pass, signed Q1.15 coefficients
- Simulator: Questa Intel FPGA
- Output: signed 12-bit with valid_out
- Startup: valid_out remains 0 until 8 valid input samples have been accepted

## ROM format
`rom/test_vectors.mem` contains exactly one 3-hex-digit word per line.
The word is a 12-bit two's-complement value. Examples:
- 000 = 0
- 001 = +1
- 7FF = +2047
- 800 = -2048
- FFF = -1

## FIR coefficients
Q1.15 integer coefficients:
[-169, -750, 3170, 14133, 14133, 3170, -750, -169]
The sum is exactly 32768, so DC gain is 1.0.
The coefficients are symmetric, giving linear phase.

## Arithmetic rules
- MA accumulator: signed 16-bit is sufficient for 8 signed 12-bit samples (range -16384..16376).
- FIR products: signed 28-bit (12x16).
- FIR accumulator: signed 32-bit (sum of 8 products).
- MA output: round accumulator / 8 to nearest integer, ties away from zero.
- FIR output: round accumulator / 32768 to nearest integer, ties away from zero.
- Saturate final result to signed 12-bit [-2048, 2047].
- `valid_in=0`: no sample is accepted; history and valid-sample count hold.
- `valid_in=1`: accept one sample and update history.
- `valid_out=1` only on cycles where a new valid sample is accepted and at least 8 valid samples have been accepted since reset.
- Gaps in valid do not clear history.

## ROM test signal
The included deterministic sequence is a mixture of a low-frequency sinusoid, a high-frequency sinusoid, and Gaussian noise, clipped to signed 12-bit range. It is a synthetic verification signal, not measured PECT data.

## Important indexing convention
The history is ordered oldest to newest. Coefficient h[0] multiplies the oldest sample in the 8-sample window; h[7] multiplies the newest. Keep this convention identical in Verilog and Python.

## Project status
This is a simulation-first specification. DE25 pin assignments, exact FPGA device, UART baud/data framing, and physical 7-segment wiring remain TBD until the board/device documentation is available.
