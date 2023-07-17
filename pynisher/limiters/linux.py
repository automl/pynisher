"""Set limits for Linux.

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

import resource

from pynisher.limiters.limiter import Limiter


class LimiterLinux(Limiter):
    def limit_memory(self, memory: int) -> None:
        """Limit the addressable memory.

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

    def limit_cpu_time(self, cpu_time: int, interval: int = 5) -> None:
        """Limit the cpu time for this process.

        The process will be killed with -signal.SIGXCPU status

        Attempts to handle the sigxcpu with `signal.signal(signal.SIGXCPU, handler)`
        did not work as intended in cases where the process spawn subprocesses

        Using `setitimer(ITIMER_PROF)` is not a good idea as it only measure the time
        of the current process, non of it's children.

        Parameters
        ----------
        cpu_time : int
            The amount of time in seconds

        interval: int = 5
            The time between the initial SIGXCPU sent before a SIGKILL will be
            sent if the process is still running. This SIGXCPU is sent every
            second during this interval. See documentation linked in module
        """
        limit = (cpu_time, cpu_time + interval)
        resource.setrlimit(resource.RLIMIT_CPU, limit)

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
