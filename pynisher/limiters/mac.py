"""
Useful info for invesetigating memory:
* MacOS uses Darwin-XNU as it's underlying operating system. This is easier to find as
just XNU.
* XNU uses a special memory manager called Mach-VM in its interface to which we have no
control
* Darwin-xnu: https://github.com/apple/darwin-xnu
* resource.h: https://github.com/apple/darwin-xnu/blob/main/bsd/sys/resource.h
* kern_resource.c
    https://github.com/apple/darwin-xnu/blob/main/bsd/kern/kern_resource.c

For documentation on `setrlimit` and how to limit resources for MAC
** `setrlimit` **
* https://github.com/apple/darwin-xnu/blob/main/bsd/man/man2/getrlimit.2

For documentation on MAC specific signal alarms:
** `signals` **
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/sigaction.2.html

Can't seem to limit memory, the only accepted rlimit towards memory is RLIMIT_DATA and
that seems to not work.
# https://github.com/apple/darwin-xnu/blob/2ff845c2e033bd0ff64b5b6aa6063a1f8f65aa32/bsd/kern/kern_resource.c#L987

This module and the Linux limiter share almost identical code but we keep them seperate
incase of specific modules or changes needed
"""
from __future__ import annotations

from typing import Any

import resource

from pynisher.exceptions import CpuTimeoutException
from pynisher.limiters.limiter import Limiter


def raise_on_cpu_limit(signum: Any, frame: Any) -> None:
    """Raise a `RuntimeError` when the CPU limit is reached.

    This is a signal handler for `SIGXCPU` which is sent when the CPU time limit
    is reached. This is a signal that is sent to the process, not the thread, so
    we need to make sure that we only raise the exception in the main thread.

    Parameters
    ----------
    signum : int
        The signal number
    frame : FrameType
        The current stack frame
    """
    raise CpuTimeoutException("CPU time limit exceeded")


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
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)

            self.old_limits = (soft, hard)
            new_limits = (memory, hard)

            resource.setrlimit(resource.RLIMIT_AS, new_limits)
        except Exception:
            import sys

            raise RuntimeError(
                f"Limiting memory is not supported on your {sys.platform}"
            )

    def limit_cpu_time(self, cpu_time: int, interval: int = 5) -> None:
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

        interval: int = 5
            The time between the initial SIGXCPU sent before a SIGKILL will be
            sent if the process is still running. This SIGXCPU is sent every
            second during this interval. See documentation linked in module
        """
        limit = (cpu_time, cpu_time + interval)
        resource.setrlimit(resource.RLIMIT_CPU, limit)
