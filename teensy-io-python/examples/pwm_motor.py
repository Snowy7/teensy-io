from teensy_io import TeensyIO


io = TeensyIO("/dev/ttyACM0").connect()
try:
    io.pwm("output").configure(physical_pin=3, frequency=20_000, initial_duty=0.0)
    io.pwm("output").write(0.35)
finally:
    io.pwm("output").write(0.0)
    io.close()
