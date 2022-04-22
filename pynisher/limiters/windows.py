from __future__ import annotations

from typing import Any

import signal
import sys
from threading import Timer

from pynisher.exceptions import WallTimeoutException
from pynisher.limiters.limiter import Limiter

# `signal.raise_signal` is only available in  >= 3.8
if sys.version_info <= (3, 8):
    import os

    def emit_sigterm() -> None:
        """Emit a SIGTERM using os.kill as `raise_signal` in 3.8"""
        os.kill(os.getpid(), signal.SIGTERM)

else:

    def emit_sigterm() -> None:
        """Emit a SIGTERM"""
        signal.raise_signal(signal.SIGTERM)


class LimiterWindows(Limiter):
    @staticmethod
    def _handler(signum: int, frame: Any | None) -> Any:
        # SIGTERM: wall time
        #
        #   For windows, we don't have access to any specific signals.
        #   The only signal we explicitly can handle is SIGTERM which
        #   is a generic signal to terminate a process
        if signum == signal.SIGTERM:
            raise WallTimeoutException

        # UNKNOWN
        #
        #   We have caught some unknown signal. This means we are too restrictive
        #   with the signals we are catching.
        else:
            raise NotImplementedError(f"Does not currently handle signal id {signum}")

    def limit_memory(self, memory: int) -> None:
        """Limit's the memory of this process."""
        self._raise_warning("Currently `limit_memory` not implemented on Windows")

    def limit_cpu_time(self, cpu_time: int, grace_period: int = 1) -> None:
        """Limit's the cpu time of this process."""
        self._raise_warning("Currently `limit_cpu_time` not implemented on Windows")

    def limit_wall_time(self, wall_time: int) -> None:
        """Limit's the wall time of this process."""
        try:
            signal.signal(signal.SIGTERM, LimiterWindows._handler)
            timer = Timer(wall_time, emit_sigterm)
            timer.start()

            # Setting this attribute is hacky and specific to Windows
            # but we need to stop the timer if the function returned
            # in time. This is done in Limiter
            self.timer = timer

        except Exception as e:
            self._raise_warning(f"Couldn't limit `wall_time` on Windows due to {e}")

    def _try_remove_memory_limit(self) -> bool:
        """Remove memory limit if it can"""
        return False
