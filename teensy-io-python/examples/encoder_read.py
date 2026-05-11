from teensy_io import TeensyIO


io = TeensyIO("/dev/ttyACM0").connect()
try:
    encoder = io.encoder("rotary").attach(pin_a=5, pin_b=6, mode="x4")
    print(encoder.read())
finally:
    io.close()
