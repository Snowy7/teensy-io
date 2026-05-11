from .client import TeensyIO
from .protocol.frames import EdgeEvent, TelemetryFrame
from .protocol.errors import (
    CommandRejectedError,
    ConnectionLostError,
    EmergencyStopActiveError,
    InvalidModeError,
    InvalidPinError,
    ProtocolError,
    QueueFullError,
    TeensyIOError,
    TeensyIOTimeoutError,
    WatchdogTimeoutError,
)

__all__ = [
    "CommandRejectedError",
    "ConnectionLostError",
    "EdgeEvent",
    "EmergencyStopActiveError",
    "InvalidModeError",
    "InvalidPinError",
    "ProtocolError",
    "QueueFullError",
    "TelemetryFrame",
    "TeensyIO",
    "TeensyIOError",
    "TeensyIOTimeoutError",
    "WatchdogTimeoutError",
]
