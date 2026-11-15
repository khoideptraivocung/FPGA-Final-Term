# ============================================================================
# Questa / ModelSim Simulation Script with Analog Waveform Display
# ============================================================================

# 1. Create work library
vlib work
vmap work work

# 2. Compile RTL and Testbench files
vlog -work work rtl/sensor_filter_core.v
vlog -work work rtl/rom_sensor_reader.v
vlog -work work rtl/uart_tx.v
vlog -work work rtl/uart_rx.v
vlog -work work rtl/seg7_decoder.v
vlog -work work rtl/top_de25.v
vlog -work work tb/tb_sensor_filter.v

# 3. Start simulation
vsim -voptargs="+acc" work.tb_sensor_filter

# 4. Clear old waves
delete wave *

# 5. Add signals with Analog & Signed Decimal formatting
add wave -divider "CLOCK & RESET"
add wave -color Yellow /tb_sensor_filter/clk
add wave -color Red    /tb_sensor_filter/rst_n

add wave -divider "INPUT SENSOR SIGNAL"
add wave -color Cyan   /tb_sensor_filter/valid_in
add wave -color Orange -radix decimal -height 80 -min -2048 -max 2047 -format Analog-Step /tb_sensor_filter/data_in
add wave -color Magenta /tb_sensor_filter/filter_sel

add wave -divider "FILTERED OUTPUT (MA / FIR)"
add wave -color Cyan   /tb_sensor_filter/valid_out
add wave -color Green  -radix decimal -height 80 -min -2048 -max 2047 -format Analog-Step /tb_sensor_filter/data_out

add wave -divider "AUTOMATED VERIFICATION"
add wave -color White  -radix decimal /tb_sensor_filter/errors

# 6. Run simulation and zoom to active area
run 5000ns
wave zoom full
