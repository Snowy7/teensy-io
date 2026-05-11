from teensy_io import TeensyIO


io = TeensyIO("/dev/ttyACM0").connect()
try:
    analog = io.analog("input").configure(physical_pin=14, samples=8)
    print(analog.read_raw())
    print(analog.read_normalized())
finally:
    io.close()
