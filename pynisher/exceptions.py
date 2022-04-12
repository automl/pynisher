class CpuTimeoutException(Exception):
    """Pynisher exception object returned on a CPU time limit."""
    pass


class TimeoutException(Exception):
    """Pynisher exception object returned when hitting the time limit."""
    pass


class MemorylimitException(Exception):
    """Pynisher exception object returned when hitting the memory limit."""
    pass


class SubprocessException(Exception):
    """Pynisher exception object returned when receiving an OSError while
    executing the subprocess."""
    pass


class PynisherError(Exception):
    """Pynisher exception object returned in case of an internal error.

    This should not happen, please open an issue at github.com/automl/pynisher
    if you run into this."""
    pass


class SignalException(Exception):
    """Pynisher exception object returned in case of a signal being handled by
    the pynisher"""
    pass


class AnythingException(Exception):
    """Pynisher exception object returned if the function call closed
    prematurely and no cause can be determined.

    In this case, the stdout and stderr can contain helpful debug information.
    """
    pass