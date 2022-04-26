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
import traceback

from pynisher.exceptions import CpuTimeoutException
from pynisher.limiters.limiter import Limiter


class LimiterMac(Limiter):
    @staticmethod
    def _handler(signum: int, frame: Any | None) -> Any:
        # SIGPROF: cpu_time `setitimer(ITIMER_PRF)`
        #
        #   This signal is raised when `setitimer(time)` elapses.
        #   It measures the sys + user time used while the process is executing
        #   * https://docs.python.org/3/library/signal.html#signal.setitimer
        if signum == signal.SIGPROF:
            raise CpuTimeoutException

        # UNKNOWN
        #
        #   We have caught some unknown signal. This means we are too restrictive
        #   with the signals we are catching.
        else:
            raise NotImplementedError(f"Does not handle signal with id {signum}")

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

    def limit_cpu_time(self, cpu_time: int, grace_period: int = 1) -> None:
        """Limit the cpu time for this process.

        A SIGXCPU will be sent to the `_handler` once the `soft` limit
        is reached, once per second until `hard` is reached and then
        finally a SIGKILL.

        Parameters
        ----------
        cpu_time : int
            The amount of time in seconds

        grace_period : int = 1
            The amount of extra time given to the process before a SIGKILL
            is sent.
        """
        signal.signal(signal.SIGPROF, LimiterMac._handler)
        signal.setitimer(signal.ITIMER_PROF, cpu_time, grace_period)

    def _try_remove_memory_limit(self) -> bool:
        """Remove memory limit if it can"""
        try:
            unlimited_resources = (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
            restored_limits = getattr(self, "old_limits", unlimited_resources)

            resource.setrlimit(resource.RLIMIT_DATA, restored_limits)
            return True
        except Exception as e:
            self._raise_warning(
                f"Couldn't remove limit `memory` on Mac due to Error: {e}"
                f"\n{traceback.format_exc()} "
            )
            return False
