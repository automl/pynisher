class CpuTimeoutException(Exception):
    """Exception when hitting CPU time limit."""

    pass


class TimeoutException(Exception):
    """Exception when hitting the time limit."""

    pass


class MemorylimitException(Exception):
    """Exception when hitting the memory limit"""

    pass


class SubprocessException(Exception):
    """Exception when receiving an OSError while executing the subprocess."""

    pass


class PynisherError(Exception):
    """Exception in case of an internal error"""

    pass


class SignalException(Exception):
    """Exception when a process signal was caught by the pynisher"""

    pass


class AnythingException(Exception):
    """Exception for anything else"""

    pass
