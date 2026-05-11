class TeensyIOError(Exception):
    """Base exception for teensy-io."""


class ConnectionLostError(TeensyIOError):
    pass


class TeensyIOTimeoutError(TeensyIOError):
    pass


class ProtocolError(TeensyIOError):
    pass


class InvalidPinError(TeensyIOError):
    pass


class InvalidModeError(TeensyIOError):
    pass


class CommandRejectedError(TeensyIOError):
    pass


class EmergencyStopActiveError(CommandRejectedError):
    pass


class WatchdogTimeoutError(TeensyIOError):
    pass
