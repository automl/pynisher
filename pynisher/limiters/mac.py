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

import resource

from pynisher.limiters.limiter import Limiter


class LimiterMac(Limiter):
    def limit_memory(self, memory: int) -> None:
        """Limit the addressable memory

        It seems that each of RLIMIT_AS, RLIMIT_DATA and RLIMIT_RSS do nothing.
        While they do set, nothing is done when those boundaries are exceeded.

        * Tried catching all available signals but non triggered

        We still however try this but it's unlikely to work

        Parameters
        ----------
        memory : int
            The memory limit in bytes
        """
        # This will likely do nothing on newer mac, however users can check for support
        # before hand to prevent issues.
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)

        self.old_limits = (soft, hard)
        new_limits = (memory, hard)

        resource.setrlimit(resource.RLIMIT_AS, new_limits)

    def limit_cpu_time(self, cpu_time: int, interval: int = 1) -> None:
        """Limit the cpu time for this process.

        The process will be killed with -signal.SIGXCPU status.

        Attempts to handle the sigxcpu with `signal.signal(signal.SIGXCPU, handler)`
        did not work as intended in cases where the process spawn subprocesses

        Using `setitimer(ITIMER_PROF)` is not a good idea as it only measure the time
        of the current process, non of it's children.


        Parameters
        ----------
        cpu_time : int
            The amount of time in seconds

        interval: int = 1
            How often the itimer should ping the process once the time
            has elapsed.
        """
        limit = (cpu_time, cpu_time + 2)
        resource.setrlimit(resource.RLIMIT_CPU, limit)
