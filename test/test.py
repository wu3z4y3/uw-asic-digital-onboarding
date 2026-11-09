# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x00, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

# return the pwm frequency for the specified bit, don't use for edge cases
async def check_pwm_frequency(dut, signal, index):
    period = 0
    prev = (int(signal.value) >> index) & 1
    # find first rising edge
    while True:
        await ClockCycles(dut.clk, 1)
        curr = (int(signal.value) >> index) & 1
        if prev == 0 and curr == 1:
            break
        prev = curr

    prev = (int(signal.value) >> index) & 1
    # find second rising edge
    while True:
        await ClockCycles(dut.clk, 1)
        period += 1
        curr = (int(signal.value) >> index) & 1
        if prev == 0 and curr == 1:
            break
        prev = curr

    # each clock period is 100 ns
    return 1e9 / (period * 100)

# return the pwm duty cycle in % for the specified bit, don't use for edge cases
async def check_pwm_duty(dut, signal, index):
    high = 0
    period = 0
    prev = (int(signal.value) >> index) & 1
    # find first rising edge
    while True:
        await ClockCycles(dut.clk, 1)
        curr = (int(signal.value) >> index) & 1
        if prev == 0 and curr == 1:
            break
        prev = curr

    prev = (int(signal.value) >> index) & 1
    # find first falling edge
    while True:
        await ClockCycles(dut.clk, 1)
        period += 1
        high += 1
        curr = (int(signal.value) >> index) & 1
        if prev == 1 and curr == 0:
            break
        prev = curr

    prev = (int(signal.value) >> index) & 1
    # find second rising edge
    while True:
        await ClockCycles(dut.clk, 1)
        period += 1
        curr = (int(signal.value) >> index) & 1
        if prev == 0 and curr == 1:
            break
        prev = curr

    # return duty cycle in percent
    return high/period * 100

@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("Start PWM Frequency test")

    # 3kHz with 1% error
    expected_frequency = 3000
    error = 30

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("PWM enabled on all bits in uo_out with 0x01 duty cycle")
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xFF)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  
    for index in range(8):
        frequency = await check_pwm_frequency(dut, dut.uo_out, index)
        assert abs(frequency - expected_frequency) <= error, f"Frequency {frequency} is out of range for bit {index}"

    dut._log.info("PWM enabled on all bits in uio_out with 0x01 duty cycle")
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xFF)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  
    for index in range(8):
        frequency = await check_pwm_frequency(dut, dut.uio_out, index)
        assert abs(frequency - expected_frequency) <= error, f"Frequency {frequency} is out of range for bit {index}"

    dut._log.info("PWM Frequency test completed successfully")

@cocotb.test()
async def test_pwm_duty(dut):
    dut._log.info("Start PWM Duty Cycle test")
        # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("PWM enabled on all bits in uo_out with 0xF0 duty cycle")
    test_duty = 0xF0
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xFF)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, test_duty)  
    for index in range(8):
        duty = await check_pwm_duty(dut, dut.uo_out, index)
        assert abs((test_duty/256 * 100) - duty) <= 1, f"Duty cycle {duty} is out of range for bit {index}"

    dut._log.info("PWM enabled on all bits in uio_out with 0xF0 duty cycle")
    test_duty = 0xF0
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xFF)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, test_duty)  
    for index in range(8):
        duty = await check_pwm_duty(dut, dut.uio_out, index)
        assert abs((test_duty/256 * 100) - duty) <= 1, f"Duty cycle {duty} is out of range for bit {index}"

    # 13 * 256
    pwm_cycles = 3328

    dut._log.info("PWM enabled on all bits in uo_out with 0x00 duty cycle")
    test_duty = 0x00
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xFF)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, test_duty)  
    for _ in range(pwm_cycles):
        await ClockCycles(dut.clk, 1)
        assert int(dut.uo_out.value) == 0, f"0x00 duty cycle failed with uo_out = {dut.uo_out.value}"

    dut._log.info("PWM enabled on all bits in uio_out with 0x00 duty cycle")
    test_duty = 0x00
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xFF)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, test_duty)  
    for _ in range(pwm_cycles):
        await ClockCycles(dut.clk, 1)
        assert int(dut.uio_out.value) == 0, f"0x00 duty cycle failed with uio_out = {dut.uio_out.value}"

    dut._log.info("PWM enabled on all bits in uo_out with 0xFF duty cycle")
    test_duty = 0xFF
    test_uo_out = 0x67
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, test_uo_out)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, test_duty)  
    for _ in range(pwm_cycles):
        await ClockCycles(dut.clk, 1)
        assert int(dut.uo_out.value) == test_uo_out, f"0xFF duty cycle failed with uo_out = {dut.uo_out.value}"

    dut._log.info("PWM enabled on all bits in uio_out with 0xFF duty cycle")
    test_duty = 0xFF
    test_uio_out = 0x67
    # en_reg_out_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, test_uio_out)  
    # en_reg_pwm_7_0
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xFF)  
    # pwm_duty_cycle
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, test_duty)  
    for _ in range(pwm_cycles):
        await ClockCycles(dut.clk, 1)
        assert int(dut.uio_out.value) == test_uio_out, f"0xFF duty cycle failed with uio_out = {dut.uio_out.value}"

    dut._log.info("PWM Duty Cycle test completed successfully")
