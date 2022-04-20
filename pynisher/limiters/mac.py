"""
For documentation on `setrlimit` and how to limit resources for MAC
** `setrlimit` **
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/setrlimit.2.html

For documentation on MAC specific signal alarms:
** `signals` **
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/sigaction.2.html

This module and the Linux limiter share almost identical code but we keep them seperate
incase of specific modules or changes needed
"""
from __future__ import annotations

from typing import Any

import resource
import signal
import warnings

from pynisher.exceptions import CpuTimeoutException, SignalException, TimeoutException
from pynisher.limiters.limiter import Limiter


class LimiterMac(Limiter):
    @staticmethod
    def _handler(signum: int, frame: signal.FrameType | None) -> Any:
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

        We can't limit using resource.setrlimit as it seems that None of the
        RLIMIT_X's are available. This we debugged by using 
        `import psutil; print(dir(psutil))` in which a MAC system did not have
        any `RLIMIT_X` attributes while a Linux system did.

        Parameters
        ----------
        memory : int
            The memory limit in bytes
        """
        warnings.warn("Limiting memory is not supported on Darwin.")

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
        signal.signal(signal.SIGXCPU, LimiterDarwin._handler)

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


class LimiterDarwin(LimiterMac):
    """Incase we need something specific for DARWIN"""

    pass
