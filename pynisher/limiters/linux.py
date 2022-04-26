"""
For documentation on `setrlimit` and how to limit resources for Linux
** `setrlimit` **
https://man7.org/linux/man-pages/man2/setrlimit.2.html

For documentation on Linux specific signal alarms:
** `signals` **
https://man7.org/linux/man-pages/man7/signal.7.html

This module and the Mac limiter share almost identical code but we keep them seperate
incase of specific modules or changes needed.
"""
from __future__ import annotations

from typing import Any

import resource
import signal
import traceback

from pynisher.exceptions import CpuTimeoutException
from pynisher.limiters.limiter import Limiter


class LimiterLinux(Limiter):
    @staticmethod
    def _handler(signum: int, frame: Any | None) -> Any:
        # SIGPROF: cpu_time `setitimer(ITIMER_PRF)`
        #
        #   This signal is raised when `setitimer(time)` elapses.
        #   It measures the sys + user time used while the process is executing
        #   * https://docs.python.org/3/library/signal.html#signal.setitimer
        if signum == signal.SIGPROF:
            raise CpuTimeoutException()

        # UNKNOWN
        #
        #   We have caught some unknown signal. This means we are too restrictive
        #   with the signals we are catching.
        else:
            raise NotImplementedError(f"Does not currently handle signal id {signum}")

    def limit_memory(self, memory: int) -> None:
        """Limit the addressable memory

        This could technically raise `SIGSEGV` (segmentation fault) but
        we instead catch a python `MemoryError` as indication that memory
        time was exceeded. This lets us give back the traceback.

        Parameters
        ----------
        memory : int
            The memory limit in bytes
        """
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)

        self.old_limits = (soft, hard)
        new_limits = (memory, hard)

        resource.setrlimit(resource.RLIMIT_AS, new_limits)

    def limit_cpu_time(self, cpu_time: int, interval: int = 1) -> None:
        """Limit the cpu time for this process.

        A SIGPROF will be sent to the `_handler` the `setitimer()` has
        elapsed.

        Parameters
        ----------
        cpu_time : int
            The amount of time in seconds

        interval: int = 1
            How often the itimer should ping the process once the time
            has elapsed.
        """
        signal.signal(signal.SIGPROF, LimiterLinux._handler)
        signal.setitimer(signal.ITIMER_PROF, cpu_time, interval)

    def _try_remove_memory_limit(self) -> bool:
        """Remove memory limit if it can"""
        try:
            unlimited_resources = (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
            restored_limits = getattr(self, "old_limits", unlimited_resources)

            resource.setrlimit(resource.RLIMIT_AS, restored_limits)
            return True
        except Exception as e:
            self._raise_warning(
                f"Couldn't remove limit `memory` on Linux due to Error: {e}"
                f"\n{traceback.format_exc()} "
            )
            return False

    def _debug_memory(self) -> str:
        """Prints the memory used by the process

        Returns
        -------
        (usage: str)
            Returns the usage as a string, not sure if always KB but
            leaving type as str until known.
        """
        # https://stackoverflow.com/a/39765583/5332072
        with open("/proc/self/status") as f:
            status = f.readlines()

        vmpeak = next(s for s in status if s.startswith("VmPeak:"))
        return vmpeak
