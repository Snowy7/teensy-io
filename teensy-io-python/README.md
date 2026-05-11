# teensy-io Python

Python client library for the `teensy-io` firmware.

```python
from teensy_io import TeensyIO

io = TeensyIO("/dev/ttyACM0").connect()
print(io.ping())
io.close()
```
