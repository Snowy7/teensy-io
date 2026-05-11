from teensy_io import TeensyIO


io = TeensyIO("/dev/ttyACM0").connect()
try:
    io.i2c_bus("main").configure(bus=0, frequency=400_000)
    dac = io.dac("analog_out").attach_i2c(
        bus="main",
        address=0x60,
        channels=1,
        resolution_bits=12,
    )
    dac.write_normalized(0.5)
    dac.write_raw(2048)
finally:
    io.close()
