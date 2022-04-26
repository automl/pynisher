"""Limiters are what define how resources should be limited as well as handle."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

import platform
import sys
import traceback
from multiprocessing.connection import Connection

from pynisher.util import Monitor


class Limiter(ABC):
    """Defines how to limit resources for a given system."""

    def __init__(
        self,
        func: Callable,
        output: Connection,
        memory: int | None = None,
        cpu_time: int | None = None,
        grace_period: int = 1,
        warnings: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        func : Callable
            The function to be limited

        output : Connection
            The output multiprocessing.Connection object to pass the results back

        memory : int | None = None
            The memory in bytes to allocate

        cpu_time : int | None = None
            The cpu time in seconds to allocate

        grace_period : int = 1
            The grace period in seconds to give for a process to shutdown once signalled

        warnings : bool = True
            Whether to emit pynisher warnings or not.
        """
        self.func = func
        self.output = output
        self.memory = memory
        self.cpu_time = cpu_time
        self.grace_period = grace_period
        self.warnings = warnings

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Set process limits and then call the function with the given arguments.

        Note
        ----
        This should usually not be called by the end user, it's main use is in
        Pynisher::run().

        Parameters
        ----------
        *args, **kwargs
            Arguments to the function

        Returns
        -------
        None
        """
        try:

            if self.cpu_time is not None:
                self.limit_cpu_time(self.cpu_time, grace_period=self.grace_period)

            if self.memory is not None:
                # We should probably warn if we exceed the memory usage before
                # any limitation is set
                memusage = Monitor().memory("B")
                if self.memory <= memusage:
                    self._raise_warning(
                        f"Current memory usage in new process is {memusage}B but "
                        f" setting limit to {self.memory}B. Likely to fail, try"
                        f" increasing the memory limit"
                    )
                self.limit_memory(self.memory)

            # Call our function
            result = self.func(*args, **kwargs)
            error = None
            tb = None

        except Exception as e:
            result = None
            error = e
            tb = "".join(traceback.format_exception(*sys.exc_info()))

        # Now let's try to send the result back
        response = (result, error, tb)
        try:
            self.output.send(response)
            self.output.close()
            return
        except Exception as e:
            failed_send_tb = "".join(traceback.format_exception(*sys.exc_info()))
            failed_send_response = (None, e, failed_send_tb)

        # Maybe we can remove memory limit and try again
        if self._try_remove_memory_limit():
            try:
                self.output.send(response)
                self.output.close()
                return
            except Exception as e:
                failed_send_tb = "".join(traceback.format_exception(*sys.exc_info()))
                failed_send_response = (None, e, failed_send_tb)

        # At this point, lets just try to send the errors we got from the attempts
        # at sending the original response
        try:
            self.output.send(failed_send_response)
            self.output.close()
            return
        except Exception:
            pass

        # One last effot to send the smallest None through
        last_response_attempt = None
        try:
            self.output.send(last_response_attempt)
        finally:
            self.output.close()
            return

    @staticmethod
    def create(
        func: Callable,
        output: Connection,
        memory: int | None = None,
        cpu_time: int | None = None,
        grace_period: int = 1,
        warnings: bool = True,
    ) -> Limiter:
        """For full documentation, see __init__."""
        # NOTE: __init__ param duplication
        #
        #   I'm not delighted by the duplication of the __init__ params but this keeps
        #   things typesafe and referencable in case we need to validate
        arguments = {
            "func": func,
            "output": output,
            "memory": memory,
            "cpu_time": cpu_time,
            "grace_period": grace_period,
            "warnings": warnings,
        }

        # There is probably a lot more identifiers but for now this covers our use case
        system_name = platform.system().lower()

        # NOTE: Imports inside if statements
        #
        #   This servers two purposes, one is to prevent cyclical imports, as they need
        #   to inherit Limiter from this file, while this file needs to import them too,
        #   creating a circular dependancy... unless they're imported later.
        #
        #   Secondly, different systems will have different modules available.
        #   For example, the `resources` module is not avialable on Windows and so
        #   importing that would cause issues.
        #
        if system_name == "linux":
            from pynisher.limiters.linux import LimiterLinux

            return LimiterLinux(**arguments)  # type: ignore

        elif system_name == "darwin":
            from pynisher.limiters.mac import LimiterMac

            return LimiterMac(**arguments)  # type: ignore

        elif system_name == "windows":
            from pynisher.limiters.windows import LimiterWindows

            return LimiterWindows(**arguments)  # type: ignore

        else:
            raise NotImplementedError(
                f"We currently don't support your system: {platform}"
            )

    @abstractmethod
    def limit_memory(self, memory: int) -> None:
        """Limit's the memory of this process."""
        ...

    @abstractmethod
    def limit_cpu_time(self, cpu_time: int, grace_period: int = 1) -> None:
        """Limit's the cpu time of this process."""
        ...

    @abstractmethod
    def _try_remove_memory_limit(self) -> bool:
        """Remove the memory limit if it can

        Returns
        -------
        success: bool
            Whether it was successful or not
        """
        ...

    def _raise_warning(self, msg: str) -> None:
        if self.warnings is True:
            print(msg, file=sys.stderr)
