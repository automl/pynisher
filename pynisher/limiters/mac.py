"""
For documentation on MAC specific signal alarms:

** `setrlimit` **
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/setrlimit.2.html

** `signals` **
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/sigaction.2.html#//apple_ref/doc/man/2/sigaction
"""
from __future__ import annotations

from pynisher.limiters.limiter import Limiter
import signal
import resource

from pynisher.exceptions import (
    CpuTimeoutException,
    TimeoutException,
    SignalException,
)


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
    def _handler(signum: signal.Signals, frame: signal.FrameType | None) -> None:
        # SIGXCPU: cpu_time `setrlimit(RLIMIT_CPU, (soft, hard))`
        #
        #   Sent when process reaches `soft` limit of, then once a second until `hard`
        #   before finally sending SIGKILL.
        #   The default handler would just kill the process
        if signum == signal.SIGXCPU:
            raise CpuTimeoutException

        # SIGALRM `signal.alarm(wall_time)`
        #
        #   When the alarm uses `wall_time`, SIGALARM will be sent.
        #   It has no default action
        elif signum == signal.SIGALRM:
            # SIGALRM is sent to process when the specified time limit to an alarm function elapses
            # (when real or clock time elapses)
            raise TimeoutException

        # UNKNOWN
        #
        #   We have caught some unknown signal. This means we are too restrictive
        #   with the signals we are catching.
        else:
            raise SignalException

    def limit_memory(self, memory: int) -> None:
        """Limit the addressable memory

        This could technically raise `SIGSEGV` (segmentation fault) but
        we instead catch a python `MemoryError` as indication that memory
        time was exceeded. This lets us give back the traceback.

        Parameters
        ----------
        memory : int
            The memory limit in MB
        """
        # Convert megabyte to byte
        mem_in_b = int(memory * 1024 * 1024)
        resource.setrlimit(resource.RLIMIT_AS, (mem_in_b, mem_in_b))

    def limit_cpu_time(self, cpu_time: int, grace_period: int = 0) -> None:
        """Limit the cpu time for this process.

        A SIGXCPU will be sent to the `_handler` once the `soft` limit
        is reached, once per second until `hard` is reached and then
        finally a SIGKILL.

        Parameters
        ----------
        cpu_time : int
            The amount of time in seconds

        grace_period : int = 0
            The amount of extra time given to the process before a SIGKILL
            is sent.
        """
        soft = cpu_time
        hard = cpu_time + grace_period

        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
        signal.signal(signal.SIGALRM, LimiterDarwin._handler)

    def limit_wall_time(self, wall_time: int) -> None:
        """Limit the wall time for this process

        A SIGALARM will be sent to the handler once `wall_time` amount
        of seconds has elapsed since the invocation of `signal.alarm(wall_time)`.

        Parameters
        ----------
        wall_time : int
            The amount of time to limit to in seconds
        """
        signal.signal(signal.SIGALRM, LimiterDarwin._handler)
        signal.alarm(wall_time)

    def _debug_memory(self) -> str:
        """Prints the memory used by the process

        Returns
        -------
        (usage: str)
            Returns the usage as a string, not sure if always KB but
            leaving type as str until known.
        """
        # https://stackoverflow.com/a/39765583/5332072
        with open('/proc/self/status') as f:
            status = f.readlines()

        vmpeak = next(s for s in status if s.startswith("VmPeak:"))
        return vmpeak
