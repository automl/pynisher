from __future__ import annotations

from typing import Any

import sys

from pynisher.limiters.limiter import Limiter

_win32_import_error_msg = """
Couldn't limit `memory` as `pywin32` failed to import.

If using a Conda environment with Python 3.8 or 3.9 and you installed `pynisher`
or a package relying on `pynisher` with `pip` you must install `pywin32`
with `conda` manually:

* `conda install pywin32`.

Please see this issue for more:
* https://github.com/mhammond/pywin32/issues/1865

pywin32
* https://github.com/mhammond/pywin32
"""

# Not sure it's actual type
WIN32JOB = Any


class LimiterWindows(Limiter):
    def job(self) -> WIN32JOB:
        """Get the job associated with this process.

        Caches between calls for safety.

        Returns
        -------
        WIN32JOB
            A Windows job which consists of one or more processes. In this case
            we just have the one process
        """
        if not hasattr(self, "_job"):
            # First try to import stuff, an easy exception to catch and give good
            # information about
            try:
                import win32api
                import win32job
                import winerror
            except ModuleNotFoundError as e:
                raise ModuleNotFoundError(_win32_import_error_msg) from e

            # Here, we assign it to a windows "Job", whatever that is
            # If the process is already assigned to a job, then we have
            # to check if it's less than Windows 8 because apparently
            # nested jobs aren't supported there
            try:
                job = win32job.CreateJobObject(None, "")

                process = win32api.GetCurrentProcess()
                win32job.AssignProcessToJobObject(job, process)

                self._job = job

            except win32job.error as e:
                if (
                    e.winerror != winerror.ERROR_ACCESS_DENIED
                    or sys.getwindowsversion() >= (6, 2)  # type: ignore
                    or not win32job.IsProcessInJob(process, None)
                ):
                    raise e

                msg = (
                    "The process is already in a job."
                    " Nested jobs are not supported prior to Windows 8."
                )
                raise RuntimeError(msg) from e

        return self._job

    def limit_memory(self, memory: int) -> None:
        """Limit's the memory of this process."""
        # https://stackoverflow.com/a/54958772/5332072

        # First try to import stuff, an easy exception to catch and give good
        # information about
        try:
            import win32job
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(_win32_import_error_msg) from e

        job = self.job()

        # Get the information for the job object we created
        enum_for_info = win32job.JobObjectExtendedLimitInformation
        info = win32job.QueryInformationJobObject(job, enum_for_info)

        # This appears to by bytes by looking for "JOB_OBJECT_LIMIT_JOB_MEMORY"
        # on github, specifically Python code
        info["ProcessMemoryLimit"] = memory

        # Mask of which limit flag to set
        mask_limit_memory = win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info["BasicLimitInformation"]["LimitFlags"] |= mask_limit_memory

        # Finally set the new information
        win32job.SetInformationJobObject(job, enum_for_info, info)

    def limit_cpu_time(self, cpu_time: int) -> None:
        """Limit's the cpu time of this process.

        Note
        ----
        Unfortunatly, when windows terminates a process, it doesn't use signaling
        methods like unix based systems, it just kills it and gives no chance for clean
        up. Pynisher detects this in the parent process by looking for an empty response
        from the pipe, checking that the process was killed non-gracefully, and then
        seeing if cpu_time was set.

        Parameters
        ----------
        cpu_time: int
            How many seconds to limit the process for
        """
        # First try to import stuff, an easy exception to catch and give good
        # information about
        try:
            import win32job
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(_win32_import_error_msg) from e

        job = self.job()

        # Get the information for the job object we created
        enum_for_info = win32job.JobObjectBasicLimitInformation
        info = win32job.QueryInformationJobObject(job, enum_for_info)

        # Set the time limit
        time = round(cpu_time * 10_000_000)  # In 100ns units (1e+9 / 100)
        info["PerProcessUserTimeLimit"] = time

        # Activate the flag to turn on the limiting of cput time
        flag = win32job.JOB_OBJECT_LIMIT_PROCESS_TIME
        info["LimitFlags"] |= flag

        # Finally set the new information
        win32job.SetInformationJobObject(job, enum_for_info, info)
