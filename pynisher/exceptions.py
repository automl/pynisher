class PynisherException(Exception):
    """Base class for any Pynisher related exceptions"""

    pass


class TimeoutException(PynisherException):
    """Base class for Timeout based errors"""

    pass


class CpuTimeoutException(TimeoutException):
    """Exception when hitting CPU time limit."""

    pass


class WallTimeoutException(TimeoutException):
    """Exception when hitting the wall time limit."""

    pass


class MemoryLimitException(PynisherException, MemoryError):
    """Exception when hitting the Memory Limit."""

    pass
