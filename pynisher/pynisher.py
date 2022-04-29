from __future__ import annotations

from typing import Any, Callable, Type, TypeVar

import multiprocessing
import signal
import sys
from contextlib import ContextDecorator
from functools import wraps

import psutil

from pynisher.exceptions import (
    CpuTimeoutException,
    MemoryLimitException,
    PynisherException,
    WallTimeoutException,
)
from pynisher.limiters import Limiter
from pynisher.support import contexts as valid_contexts
from pynisher.support import supports
from pynisher.util import callstring, memconvert, terminate_process, timeconvert

EMPTY = object()


class Pynisher(ContextDecorator):
    """Restrict a function's resources"""

    def __init__(
        self,
        func: Callable,
        *,
        name: str | None = None,
        memory: int | tuple[int, str] | None = None,
        cpu_time: int | tuple[float, str] | None = None,
        wall_time: int | tuple[float, str] | None = None,
        context: str | None = None,
        raises: bool = True,
        warnings: bool = True,
        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False,
        terminate_child_processes: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        func : Callable
            The function to limit and call

        name : str | None
            A name to give the process that gets created, defaults to whatever
            multiprocessing.Process defaults to.

        memory : int | tuple[int, str] | None = None
            The amount of memory to limit by. If `tuple`, specify units with (4, "MB").
            Possible units are "B", "KB", "MB", "GB".

            Processes take up some space before any limitation can take place.
            These will run fine until a new allocation takes place.
            This means a process can technically run in a limit of 1 Byte, up until the
            point it tries to allocate anything.

        cpu_time : int | tuple[float, str] | None = None
            The cpu time in seconds to limit the process to. This time is only counted while the
            process is active.
            Can provide in (time, units) such as (1.5, "h") to indicate one and a half hours.
            Units available are "s", "m", "h".

        wall_time : int | tuple[float, str] | None = None
            The amount of total wall time in seconds to limit to
            Can provide in (time, units) such as (1.5, "h") to indicate one and a half hours.
            Units available are "s", "m", "h"

        context : "fork" | "forkserver" | "spawn" | None = None
            The context to use with multiprocessing.get_context()
            * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

        raises : bool = True
            Whether any error from the subprocess should filter up and be raised.

        warnings : bool = True
            Whether to emit pynisher warnings or not.

        wrap_errors: bool | list[str | Type[Exception]] | dict = False
            Whether exceptions raised due to none resource related issues should be
            wrapped in a PynisherException.

            * If True, all exceptions will be wrapped

            * If False, no exceptions will be wrapped

            * If list, you can provide your own list of exceptions to wrap, using a
                string to prevent explicit imports outside the limited function.

            * If dict, you can specify a mapping to which kind of pynisher errors map
                to which kind of Exceptions. Again, you can specify a str if needed.
                Please see below.

            For advanced users, this can let you control whether module information will
            get sent back from the limited function.

            .. code:: python

                def f():
                    import sklearn
                    raise sklearn.exceptions.NotFittedError()

                lf = limit(f, wrap_errors=True):
                lf = limit(f, wrap_errors=["NotFittedError"])  # More specific

                try:
                    lf()
                except PynisherException as e:
                    # The error `e` has no context related to sklearn so it's not
                    # imported here

            The dict arg lets you indicated how particular errors should be identified.
            These will only be active if the corresponding limit is set.

            This can be useful in cases where a known error is caused due to memory
            constraints but does not raise a Python MemoryError.

            Keys: "cpu_time", "wall_time", "memory", "pynisher"

            Values: str, ExceptionType, (OSError, code), (OSError, code, winerr)

            .. code:: Python

                wrap_errors = {
                    "memory": [ImportError, (OSError, 22, 1455)]
                    "cpu_time": ["MyCustomException"]
                }

            For example, importing sklearn with a small enough memory limit can trigger
            an `ImportError` on linux or a `(OSError, 22, 1455)` on windows. Here the
            `22` stands for the Python OSError codes and the `1455` is the winerror code.

            In general, you should not have to interface with this but it can allow you
            some extra control.

        terminate_child_processes: bool = True
            Whether to clean up all child processes upon completion
        """  # noqa
        _cpu_time: int | None
        if isinstance(cpu_time, tuple):
            x, unit = cpu_time
            _cpu_time = round(timeconvert(x, frm=unit))
        else:
            _cpu_time = cpu_time

        _wall_time: int | None
        if isinstance(wall_time, tuple):
            x, unit = wall_time
            _wall_time = round(timeconvert(x, frm=unit))
        else:
            _wall_time = wall_time

        _memory: int | None
        if isinstance(memory, tuple):
            x, unit = memory
            _memory = round(memconvert(x, frm=unit))
        else:
            _memory = memory

        if not callable(func):
            raise ValueError(f"`func` ({func}) must be callable")

        if _cpu_time is not None and not _cpu_time >= 1:
            raise ValueError(f"`cpu_time` {cpu_time} must be >= 1 seconds")

        if _wall_time is not None and not _wall_time >= 1:
            raise ValueError(f"`wall_time` {wall_time} must be >= 1 second")

        if _memory is not None and not _memory >= 1:
            raise ValueError(f"`memory` {memory} must be >= 1 Byte")

        if context is not None and context not in valid_contexts:
            raise ValueError(f"`context` {context} must be in {valid_contexts}")

        if isinstance(wrap_errors, dict):
            valid_keys = {"memory", "wall_time", "cpu_time", "all"}
            keys = list(wrap_errors.keys())
            if not all(key in valid_keys for key in keys):
                raise ValueError(
                    f"`wrap_errors` has unknown key in {keys},"
                    f" each must be in {valid_keys} "
                )

        self.func = func
        self.name = name
        self.cpu_time = _cpu_time
        self.memory = _memory
        self.wall_time = _wall_time
        self.raises = raises
        self.context = multiprocessing.get_context(context)
        self.warnings = warnings
        self.wrap_errors = wrap_errors
        self.terminate_child_processes = terminate_child_processes

        # Set once the function is running
        self._process: psutil.Process | None = None

    def __enter__(self) -> Callable:
        """Doesn't do anything too useful at the moment.

        Returns
        -------
        (*args, **kwargs) -> Any
            Call your function and get back the result
        """
        return self.run

    def __exit__(self, *exc: Any) -> None:
        """Doesn't do anything too useful at the moment.

        Returns
        -------
        (*args, **kwargs) -> Any
            Call your function and get back the result
        """
        # Note: Not sure if we have to handle this
        # *https://docs.python.org/3/reference/datamodel.html#object.__exit__
        return

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Run the function with the given set of arguments and block until result.

        Parameters
        ----------
        *args, **kwargs
            Parameters to pass to the function being limited

        Returns
        -------
        Any
            The result of calling the function that is being limited
        """
        return self.run(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the function with the given set of arguments and block until result.

        Parameters
        ----------
        *args, **kwargs
            Parameters to pass to the function being limited

        Returns
        -------
        Any
            The result of calling the function that is being limited
        """
        # The send pipe will be passed to the subprocess to send the result back
        # while the receive pipe will be used to recieve it in this master process
        receive_pipe, send_pipe = self.context.Pipe(duplex=False)

        # The limiter is in charge of limiting resources once inside the subprocess
        # It gets the `send_pipe` through which it it should `output` it's results to
        limiter = Limiter.create(
            func=self.func,
            output=send_pipe,
            memory=self.memory,
            cpu_time=self.cpu_time,
            wall_time=self.wall_time,
            warnings=self.warnings,
            wrap_errors=self.wrap_errors,
            terminate_child_processes=self.terminate_child_processes,
        )

        # We now create the subprocess and let it know that it should call the limiter's
        # __call__ with the args and kwargs for the function being limited
        subprocess = self.context.Process(
            target=limiter.__call__,
            args=args,
            kwargs=kwargs,
            daemon=False,
            name=self.name,
        )

        # 4 kinds of `response` we expect
        #
        # * (result, None, None)    | success
        #                               => No error, we got a result
        # * (None, error, traceback)| failed
        #                               =>  Error, CPUtimeout linux/mac, MemoryError
        # * None                    | failed
        #                               => MemoryError during sending of real error
        # * EMPTY                   | failed, nothing received from pipe
        #                               => Walltime, CPUTimeout windows, Unknown
        result = EMPTY
        err: Exception | None = None
        tb: str | None = None

        # Let loose
        subprocess.start()

        try:
            self._process = psutil.Process(subprocess.pid)
        except psutil.NoSuchProcess:
            # Likely only to occur when subprocess already finished
            pass

        # If self.wall time is None, block until the subprocess finishes or terminates
        # Otherwise, will return after wall_time and the process will still be running
        subprocess.join(self.wall_time)

        # exitcode here can only take on 3 values
        #
        # * None        | the subprocess is still running (walltime elapsed)
        # * 0           | Ended gracefully, pipe is closed or response in the pipe
        # * != 0        | Process was terminated non-gracefully, nothing in the pipe
        #               | and it may not be closed
        exitcode = subprocess.exitcode

        if self._process is not None:
            terminate_process(
                self._process, children=self.terminate_child_processes, parent=True
            )

        # Wall time expired
        if exitcode is None:
            result = EMPTY
            err = WallTimeoutException(
                f"Did not finish in time ({self.wall_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        # Completed gracefully
        elif exitcode == 0:

            # Pipe has data in it or has been closed properly
            if receive_pipe.poll():

                # If there is data, it will be read
                try:
                    response = receive_pipe.recv()
                    if response is None:
                        result = EMPTY
                        err = MemoryLimitException(
                            "While returning the result from your function,"
                            " we could not retrieve the result or any error"
                            " about why."
                            f"\n{callstring(self.func, *args, **kwargs)}"
                        )
                    else:
                        result, err, tb = response
                        # If we have an err, that excludes possible results
                        if err is not None:
                            result = EMPTY

                # Otherwise, there was nothing to read
                except EOFError:
                    result = EMPTY
                    err = MemoryLimitException(
                        "Ended gracefully but could not a send response back."
                        " This is likely a MemoryError."
                        f"\n{callstring(self.func, *args, **kwargs)}"
                    )

            else:
                raise PynisherException(
                    "The process exited with exitcode 0, signifying it ended gracefully"
                    " but the subprocess pipe is still open and there is no data to"
                    " recieve. This should not happen. Please raise an issue with your"
                    " code that caused this expcetion, if possible"
                )

        # If did not exit gracefully but cpu time was set and it's windows
        elif (
            exitcode != 0
            and self.cpu_time is not None
            and sys.platform.lower().startswith("win")
        ):
            result = EMPTY
            err = CpuTimeoutException(
                f"Did not finish in cpu time ({self.cpu_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        elif exitcode == -signal.SIGSEGV and self.memory is not None:
            result = EMPTY
            err = MemoryLimitException(
                "The function exited with a segmentation error (SIGSEGV) and a memory"
                " limit was set. We presume this is due to the memory limit set."
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        elif hasattr(signal, "SIGXCPU") and exitcode == -signal.SIGXCPU:
            result = EMPTY
            err = CpuTimeoutException(
                f"Did not finish in cpu time ({self.cpu_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        # We shouldn't get here
        else:
            result = EMPTY
            err = PynisherException(
                f"Unknown reason for exitcode {exitcode} and killed process"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        receive_pipe.close()
        send_pipe.close()

        # We got a non empty result, hurray
        if result is not EMPTY:
            return result

        # We have an error
        assert isinstance(err, Exception)

        if not self.raises:
            return EMPTY

        if tb is not None:
            # Just so we can insert the traceback
            raise err from err.__class__(tb)
        else:
            raise err

    @staticmethod
    def supports(limit: str) -> bool:
        """Check if pynisher supports a given feature

        Parameters
        ----------
        limit: "wall_time" | "cpu_time" | "memory" | "decorator"
            The feature to check support for

        Returns
        -------
        bool
            Whether it is supported or not
        """
        return supports(limit)


# NOTE: Can only use typevar on decorator
#
#   Since the typevar only exist in the indentation context, we can use it here for
#   the full function scope to annotate the return type. To do so for Pynisher,
#   we would have to make it generic, probably not worth the extra complexity
#
T = TypeVar("T")


# NOTE: Simpler solution?
#
#   There might be a simpler solution then redfining a function, e.g. `restricted =
#   Pynisher` but it gets complicated as we need something like
#   `@restricted(memory=...)` but that won't work as the first arg to
#   `Pynisher.__init__` should be the function itself. For now this should work
#
def restricted(
    name: str | None = None,
    *,
    memory: int | tuple[int, str] | None = None,
    cpu_time: int | None = None,
    wall_time: int | None = None,
    context: str | None = None,
    raises: bool = True,
    warnings: bool = True,
    wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False,
    terminate_child_processes: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:  # Lol ((...) -> T) -> ((...) -> T)
    """Limit a function's resource consumption on each call

    ..code:: python

        @restricted(memory=1000, wall_time=14)
        def f(x: int) -> int:
            return x * 2

        f()

    Note
    ----
    Due to how multiprocessing pickling works, `@restricted(...)` does not
    work for Mac/Windows with Python >= 3.8. Please use the `Pynisher`"
    method of limiting resources in this case.

    Parameters
    ----------
    name : str | None
        A name to give the process that gets created, defaults to whatever
        multiprocessing.Process defaults to.

    memory : int | tuple[int, str] | None = None
        The amount of memory to limit by. If `tuple`, specify with units like (4, "MB").
        Possible units are "B", "KB", "MB", "GB".

        Processes are given some dedicated size before any limitation can take place.
        These will run fine until a new allocation takes place.
        This means a process can technically run in a limit of 1 Byte, up until the
        point it tries to allocate anything.

    cpu_time : int | tuple[float, str] | None = None
        The cpu time in seconds to limit the process to. This time is only counted while the
        process is active.
        Can provide in (time, units) such as (1.5, "h") to indicate one and a half hours.
        Units available are "s", "m", "h".

    wall_time : int | tuple[float, str] | None = None
        The amount of total wall time in seconds to limit to
        Can provide in (time, units) such as (1.5, "h") to indicate one and a half hours.
        Units available are "s", "m", "h"

    context : "fork" | "forkserver" | "spawn" | None = None
        The context to use with multiprocessing.get_context()
        * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

    raises : bool = True
        Whether any error from the subprocess should filter up and be raised.

    warnings : bool = True
        Whether to emit pynisher warnings or not.

    wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False
        Please see `Pynisher.__init__`

    terminate_child_processes: bool = True
        Whether to clean up all child processes upon completion
    """  # noqa
    if not supports("decorator") or context == "spawn":
        raise ValueError(
            "Due to how multiprocessing pickling works, `@restricted(...)` does not"
            " for Mac or Windows, specifically with the `spawn` context."
            " Please use the `limit` method of limiting."
        )

    # Incase the first argument is a function, we assume it was missued
    #
    # @restricted
    # def f(): ...
    #
    # In this case, the function f will be passed as the first arg, `name`
    if callable(name):
        raise ValueError("Please pass arguments to decorator `@restricted`")

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            pynisher = Pynisher(
                func,
                name=name,
                memory=memory,
                cpu_time=cpu_time,
                wall_time=wall_time,
                raises=raises,
                wrap_errors=wrap_errors,
            )
            return pynisher.run(*args, **kwargs)

        return wrapper

    return decorator


limit = Pynisher
