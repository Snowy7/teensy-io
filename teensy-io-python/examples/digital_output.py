from teensy_io import TeensyIO


io = TeensyIO("/dev/ttyACM0").connect()
try:
    io.pin("led").configure_output(physical_pin=13, initial=False)
    io.pin("led").write(True)
finally:
    io.close()
