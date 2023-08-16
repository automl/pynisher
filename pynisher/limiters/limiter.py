"""Limiters are what define how resources should be limited as well as handle."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Type

import os
import platform
import signal
import sys
import traceback
import warnings
from multiprocessing.connection import Connection

from pynisher.exceptions import (
    CpuTimeoutException,
    MemoryLimitException,
    PynisherException,
    WallTimeoutException,
)
from pynisher.util import Monitor, callstring, terminate_process
from pynisher.win_errcodes import WIN_ERROR_COMMITMENT_LIMIT


def is_err(err: Exception, err_type: str | Type[Exception]) -> bool:
    """Return if err is of a given type"""
    # Check name of class matches
    a = isinstance(err_type, str) and type(err).__name__ == err_type

    # Explicitly check for just class, not subclass
    # We do this because many library specific errors may inherit from base errors
    # and we don't want to accidentally wrap to many errors.
    # i.e. sklearn.exceptions.NotFittedError inherits form ValueError
    b = isinstance(err_type, type) and type(err) == err_type

    return a or b


class Limiter(ABC):
    """Defines how to limit resources for a given system."""

    def __init__(
        self,
        func: Callable,
        output: Connection,
        memory: int | None = None,
        cpu_time: int | None = None,
        wall_time: int | None = None,
        warnings: bool = True,
        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False,
        terminate_child_processes: bool = True,
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

        wall_time : int | None = None
            The amount of total wall time in seconds to limit to

        warnings : bool = True
            Whether to emit pynisher warnings or not.

        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False
            Whether to wrap exceptions or not

            Please see `pynisher.__init__` for details

        terminate_child_processes: bool = True
            Whether to clean up all child processes upon completion
        """
        self.func = func
        self.output = output
        self.memory = memory
        self.cpu_time = cpu_time
        self.wall_time = wall_time
        self.warnings = warnings
        self.wrap_errors = wrap_errors
        self.terminate_child_processes = terminate_child_processes

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
        # Make sure that if this process is killed, make any connections are closed
        # and the subprocess is killed
        _default_sigterm_handler: signal._HANDLER = signal.getsignal(signal.SIGTERM)
        if _default_sigterm_handler is signal.Handlers.SIG_IGN:
            warnings.warn(
                f"SIGTERM is ignored by this process for this function {self.func}, "
                " ignoring this as the output connection must be closed "
            )

        def _closing_handler(sig: int, frame: Any) -> None:
            self.output.close()

            # Let the default handler run
            if sig is signal.SIGTERM and callable(_default_sigterm_handler):
                _default_sigterm_handler(sig, frame)

        signal.signal(signal.SIGTERM, _closing_handler)

        try:
            if self.cpu_time is not None:
                self.limit_cpu_time(self.cpu_time)

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

        except BaseException as e:
            result = None
            error = e
            tb = "".join(traceback.format_exception(*sys.exc_info()))

        if error is not None:
            error = self._wrap_error(error, *args, **kwargs)  # type: ignore

        # Now let's try to send the result back
        response = (result, error, tb)
        try:
            self.output.send(response)
            self.output.close()
            if self.terminate_child_processes is True:
                terminate_process(timeout=2, children=True, parent=False)
            return
        except Exception as e:
            failed_send_tb = "".join(traceback.format_exception(*sys.exc_info()))
            failed_send_response = (None, e, failed_send_tb)

        # We failed to send the result back, lets try to send the errors we got from
        # doing so
        try:
            self.output.send(failed_send_response)
            self.output.close()
            if self.terminate_child_processes is True:
                terminate_process(timeout=2, children=True, parent=False)
            return
        except Exception:
            pass

        # One last effot to send the smallest None through
        last_response_attempt = None
        try:
            self.output.send(last_response_attempt)
            self.output.close()
            if self.terminate_child_processes is True:
                terminate_process(timeout=2, children=True, parent=False)
            return
        except Exception:
            pass

        # Look, everything failed, try kill any child processes and just kill this
        # process is we can't for memory reasons
        self.output.close()
        try:
            if self.terminate_child_processes is True:
                terminate_process(timeout=2, children=True, parent=False)
        except MemoryError:
            os.kill(os.getpid(), signal.SIGSEGV)
        finally:
            return

    @staticmethod
    def create(
        func: Callable,
        output: Connection,
        memory: int | None = None,
        cpu_time: int | None = None,
        wall_time: int | None = None,
        warnings: bool = True,
        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False,
        terminate_child_processes: bool = True,
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
            "warnings": warnings,
            "wrap_errors": wrap_errors,
            "terminate_child_processes": terminate_child_processes,
        }

        # There is probably a lot more identifiers but for now this covers our use case
        system_name = platform.system().lower()

        # NOTE: Imports inside if statements
        #
        #   This serves two purposes, one is to prevent cyclical imports, as they need
        #   to inherit Limiter from this file, while this file needs to import them too,
        #   creating a circular dependancy... unless they're imported later.
        #
        #   Secondly, different systems will have different modules available.
        #   For example, the `resources` module is not avialable on Windows and so
        #   importing that would cause issues.
        #
        if system_name.startswith("linux"):
            from pynisher.limiters.linux import LimiterLinux

            return LimiterLinux(**arguments)  # type: ignore

        elif system_name.startswith("darwin"):
            from pynisher.limiters.mac import LimiterMac

            return LimiterMac(**arguments)  # type: ignore

        elif system_name.startswith("win"):
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
    def limit_cpu_time(self, cpu_time: int) -> None:
        """Limit's the cpu time of this process."""
        ...

    def _raise_warning(self, msg: str) -> None:
        if self.warnings is True:
            print(msg, file=sys.stderr)

    def _wrap_error(self, err: Exception, *args: Any, **kwargs: Any) -> Exception:
        _wrap_message = f"Wrapped Exception {type(err).__name__} - {err}"

        # Catch memory errors first, these don't count as `wrap_errors=False`
        # as we need to catch memory errors that occur due to limits
        if self.memory and (
            isinstance(err, MemoryError)
            or (
                sys.platform.lower().startswith("win")
                and isinstance(err, OSError)
                and getattr(err, "winerr", None) == WIN_ERROR_COMMITMENT_LIMIT
            )
        ):
            err = MemoryLimitException(
                f"Not enough memory to run function ({self.memory}B)."
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        if self.cpu_time and isinstance(err, CpuTimeoutException):
            err = CpuTimeoutException(
                f"Did not finish in cpu time ({self.cpu_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        if self.wrap_errors is False:
            return err

        if self.wrap_errors is True:
            return PynisherException(_wrap_message)

        if isinstance(self.wrap_errors, (list, set, tuple)):
            mapping = {"pynisher": self.wrap_errors}
        elif isinstance(self.wrap_errors, dict):
            mapping = self.wrap_errors
        else:
            raise ValueError(f"Arg `wrap_errors` is ill formatted {self.wrap_errors}")

        if self.cpu_time is not None and "cpu_time" in mapping:
            if any(is_err(err, err_type) for err_type in mapping["cpu_time"]):
                return CpuTimeoutException(_wrap_message)

        if self.wall_time is not None and "wall_time" in mapping:
            if any(is_err(err, err_type) for err_type in mapping["wall_time"]):
                return WallTimeoutException(_wrap_message)

        if self.memory is not None and "memory" in mapping:
            for t in mapping["memory"]:
                # Windows specific errors
                if isinstance(t, tuple) and len(t) == 3:
                    errT, errno, winerr = t

                    is_type = is_err(err, errT)
                    has_errno = getattr(err, "errno", None) == errno
                    has_winerr = getattr(err, "winerr", None) == winerr

                    if is_type and has_errno and has_winerr:
                        return MemoryLimitException(_wrap_message)

                # OSError with codes
                elif isinstance(t, tuple) and len(t) == 2:
                    errT, errno, winerr = t

                    is_type = is_err(err, errT)
                    has_errno = getattr(err, "errno", None) == errno

                    if is_type and has_errno:
                        return MemoryLimitException(_wrap_message)

                # `t` is just a straight Exception
                elif is_err(err, t):  # type: ignore
                    return MemoryLimitException(_wrap_message)

        if "pynisher" in mapping:
            if any(is_err(err, err_type) for err_type in mapping["pynisher"]):
                return PynisherException(_wrap_message)

        return err
