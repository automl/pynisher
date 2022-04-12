from typing import Any
from pynisher.limiters.limiter import Limiter
import signal
import resource

from pynisher.exceptions import (
    MemorylimitException,
    CpuTimeoutException,
    TimeoutException,
    SignalException,
)

Frame = Any


class LimiterMac(Limiter):
    def limit_memory(self) -> None:
        """Limit's the memory of this process."""
        raise NotImplementedError()

    def limit_cpu_time(self) -> None:
        """Limit's the cpu time of this process."""
        raise NotImplementedError()

    def limit_wall_time(self) -> None:
        """Limit's the wall time of this process."""
        raise NotImplementedError()


class LimiterDarwin(Limiter):
    @staticmethod
    def handler(signum: signal.Signals, *args: Any, **kwargs: Any) -> None:
        if signum == signal.SIGXCPU:
            # When process reaches soft limit a SIGXCPU signal is sent, normally terminating the process
            raise CpuTimeoutException
        elif signum == signal.SIGALRM:
            # SIGALRM is sent to process when the specified time limit to an alarm function elapses
            # (when real or clock time elapses)
            raise TimeoutException
        else:
            raise SignalException

    def limit_memory(self, memory: int) -> None:
        """Limit's the memory of this process."""
        # Convert megabyte to byte
        mem_in_b = int(memory * 1024 * 1024)
        resource.setrlimit(resource.RLIMIT_AS, (mem_in_b, mem_in_b))

    def limit_cpu_time(self, cpu_time: int, grace_period: int = 0) -> None:
        """Limit's the cpu time of this process."""
        # From the Linux man page:
        # When the process reaches the soft limit, it is sent a SIGXCPU signal.
        # The default action for this signal is to terminate the process.
        # However, the signal can be caught, and the handler can return control
        # to the main program. If the process continues to consume CPU time,
        # it will be sent SIGXCPU once per second until the hard limit is reached,
        # at which time it is sent SIGKILL.
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (cpu_time, cpu_time + grace_period),
        )

    def limit_wall_time(self, wall_time: int) -> None:
        """Limit's the wall time of this process."""

        signal.signal(signal.SIGALRM, LimiterDarwin.handler)
        signal.alarm(wall_time)
