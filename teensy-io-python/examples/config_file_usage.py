from teensy_io import TeensyIO


io = TeensyIO.from_config("examples/io.yaml")
io.connect()
try:
    io.configure_all()
    io.pwm("motor_pwm").write(0.3)
finally:
    io.close()
