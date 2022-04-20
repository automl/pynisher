class PynisherExcpetion(Exception):
    """Base class for any Pynisher related exceptions"""

    pass


class TimeoutException(PynisherExcpetion):
    """Base class for Timeout based errors"""

    pass


class CpuTimeoutException(TimeoutException):
    """Exception when hitting CPU time limit."""

    pass


class WallTimeoutException(TimeoutException):
    """Exception when hitting the wall time limit."""

    pass


class MemoryLimitException(PynisherExcpetion, MemoryError):
    """Exception when hitting the Memory Limit."""

    pass
