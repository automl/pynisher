from __future__ import annotations

from typing import Any

import signal
import sys
import traceback
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
        # https://stackoverflow.com/a/54958772/5332072
        try:

            # First try to import stuff, an easy exception to catch and warn about
            try:
                import win32api
                import win32job
                import winerror
            except ModuleNotFoundError as e:
                self._raise_warning(
                    f"{traceback.format_exc()}\n"
                    f"Couldn't limit `memory` as `pywin32` is needed, try install with"
                    f" `pip install pywin32`."
                    f"\n* https://github.com/mhammond/pywin32"
                    f"\n{e}"
                )
                return

            # Here, we assign it to a windows "Job", whatever that is
            # If the process is already assigned to a job, then we have
            # to check if it's less than Windows 8 because apparently
            # nested jobs aren't supported there
            try:
                job = win32job.CreateJobObject(None, "")
                process = win32api.GetCurrentProcess()

                win32job.AssignProcessToJobObject(job, process)

            except win32job.error as e:
                if (
                    e.winerror != winerror.ERROR_ACCESS_DENIED
                    or sys.getwindowsversion() >= (6, 2)  # type: ignore
                    or not win32job.IsProcessInJob(process, None)
                ):
                    raise e
                else:
                    msg = (
                        "The process is already in a job."
                        " Nested jobs are not supported prior to Windows 8."
                    )
                    raise RuntimeError(msg) from e

            # Now we can try limit memory
            enum_for_info = win32job.JobObjectExtendedLimitInformation
            info = win32job.QueryInformationJobObject(job, enum_for_info)

            # This appears to by bytes by looking for "JOB_OBJECT_LIMIT_JOB_MEMORY"
            # on github, specifically Python code
            info["ProcessMemoryLimit"] = memory

            # I think the is a mask to indicate the the memory should be limited
            mask_limit_memory = win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info["BasicLimitInformation"]["LimitFlags"] |= mask_limit_memory

            # Finally set the new information
            win32job.SetInformationJobObject(job, enum_for_info, info)

        except Exception as e:
            self._raise_warning(
                f"{traceback.format_exc()}\n"
                f"Couldn't limit `memory` on Windows due to Error: {e}"
            )
            return

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
            self._raise_warning(
                f"Couldn't limit `wall_time` on Windows due to Error: {e}"
                f"\n{traceback.format_exc()} "
            )

    def _try_remove_memory_limit(self) -> bool:
        """Remove memory limit if it can"""
        return False
