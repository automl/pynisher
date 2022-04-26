from __future__ import annotations

from typing import Any, Callable, Type, TypeVar

import multiprocessing
import sys
from contextlib import ContextDecorator
from functools import wraps

from pynisher.exceptions import (
    CpuTimeoutException,
    MemoryLimitException,
    PynisherException,
    WallTimeoutException,
)
from pynisher.limiters import Limiter
from pynisher.support import supports
from pynisher.util import callstring, memconvert, timeconvert


class _EMPTY:
    """An indicator of no result, followings `inspect._empty` pattern"""

    pass


EMPTY = _EMPTY()


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
        grace_period: int = 1,
        context: str | None = None,
        raises: bool = True,
        warnings: bool = True,
        join_time: int | None = None,
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

        grace_period : int = 1
            Buffer time in seconds while limiting CPU time.

        context : "fork" | "forkserver" | "spawn" | None = None
            The context to use with multiprocessing.get_context()
            * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

        raises : bool = True
            Whether any error from the subprocess should filter up and be raised.

        warnings : bool
            Whether to emit pynisher warnings or not.
        """  # noqa
        if wall_time is not None and cpu_time is not None:
            raise ValueError("You may only set either `wall_time` or `cpu_time`")

        if isinstance(cpu_time, tuple):
            x, unit = cpu_time
            cpu_time = int(timeconvert(x, frm=unit))

        if isinstance(wall_time, tuple):
            x, unit = wall_time
            wall_time = int(timeconvert(x, frm=unit))

        if isinstance(memory, tuple):
            x, unit = memory
            memory = int(memconvert(x, frm=unit))

        if not callable(func):
            raise ValueError(f"`func` ({func}) must be callable")

        if cpu_time is not None and not cpu_time >= 1:
            raise ValueError(f"`cpu_time` ({cpu_time}) must be >= 1 seconds")

        if wall_time is not None and not wall_time >= 1:
            raise ValueError(f"`wall_time` ({wall_time}) must be >= 1 second")

        if memory is not None and not memory >= 1:
            raise ValueError(f"`memory` ({memory}) must be >= 1 Byte")

        if not grace_period >= 1:
            raise ValueError(f"`grace_period` ({grace_period}) must be >= 1 second")

        valid_contexts = ["fork", "spawn", "forkserver", None]
        if context not in valid_contexts:
            raise ValueError(f"`context` ({context}) must be in {valid_contexts}")

        self.func = func
        self.name = name
        self.cpu_time = cpu_time
        self.memory = memory
        self.wall_time = wall_time
        self.grace_period = grace_period
        self.raises = raises
        self.context = multiprocessing.get_context(context)
        self.warnings = warnings

    def __enter__(self) -> Callable:
        """Doesn't do anything to useful at the moment.

        Returns
        -------
        (*args, **kwargs) -> Any
            Call your function and get back the result
        """
        return self.run

    def __exit__(self, *exc: Any) -> None:
        """Doesn't do anything to useful at the moment.

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
        # We can safely ignore the input pipe as we do not feed data through
        # to the pipe. The output pipe will be used by the subprocess to communicate
        # the result back.
        receive_pipe, send_pipe = self.context.Pipe(duplex=False)

        # The limiter is in charge of limiting resources once inside the subprocess
        # It gets the `receive_pipe` through which it it should `output` it's results to
        limiter = Limiter.create(
            func=self.func,
            output=send_pipe,
            memory=self.memory,
            cpu_time=self.cpu_time,
            grace_period=self.grace_period,
            warnings=self.warnings,
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
        #                               => MemoryError during sending of above error
        # * EMPTY                   | failed, nothing received from pipe
        #                               => Walltime, CPUTimeout windows, Unknown
        result = EMPTY
        err: Exception | None = None
        tb: str | None = None

        # Let loose
        subprocess.start()

        # Will block here until wall time elapsed or the subprocess was ended
        subprocess.join(self.wall_time)

        # exitcode here can only take on 3 values
        #
        # * None        | the subprocess is still running (walltime elapsed)
        # * 0           | Ended gracefully, pipe is closed or response in the pipe
        # * >0          | Process was terminated non-gracefully, nothing in the pipe
        #               | and it may not be closed
        exitcode = subprocess.exitcode
        print("exitcode", exitcode)

        # Wall time expired
        if exitcode is None:
            subprocess.terminate()

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
                    print("poll", response)
                    if response is None:
                        result = EMPTY
                        err = MemoryLimitException(
                            "Ended gracefully but only `None` could be sent back"
                            " from the process. This is a MemoryException as"
                            " previous errors could not be sent previously."
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
                    " code if possible"
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

        # We shouldn't get here
        else:
            print("nope")
            result = EMPTY
            err = PynisherException(
                f"Unknown reason for exitcode {exitcode} and killed process"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        # Cleanup
        receive_pipe.close()
        send_pipe.close()

        # We got a non empty result, hurray
        if result is not EMPTY:
            return result

        # We have an error
        assert isinstance(err, Exception)

        if not self.raises:
            return EMPTY

        # Wrap MemoryErrors
        errcls: Type[Exception]
        if isinstance(err, MemoryError):
            errcls = MemoryLimitException
        else:
            errcls = err.__class__

        if tb is not None:
            raise errcls(tb) from err
        else:
            raise err

    @staticmethod
    def supports(limit: str) -> bool:
        """Check if pynisher supports a given feature

        Parameters
        ----------
        limit: "walltime" | "cputime" | "memory" | "decorator"
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
#   There might be a simpler solution then redfining a function, e.g. `limit = Pynisher`
#   but it gets complicated as we need something like `@limit(memory=...)` but that
#   won't work as the first arg to `Pynisher.__init__` should be the function itself.
#   For now this should work
#
def limit(
    name: str | None = None,
    *,
    memory: int | tuple[int, str] | None = None,
    cpu_time: int | None = None,
    wall_time: int | None = None,
    grace_period: int = 1,
    context: str | None = None,
    raises: bool = True,
    warnings: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:  # Lol ((...) -> T) -> ((...) -> T)
    """Limit a function by using subprocesses

    ..code:: python

        @limit(memory=1000, wall_time=14)
        def f(x: int) -> int:
            return x * 2

        f()

    Note
    ----
    Due to how multiprocessing pickling works, `@limit(...)` does not
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

    grace_period : int = 1
        Buffer time in seconds to give to a process to end when given a signal to end.

    context : "fork" | "forkserver" | "spawn" | None = None
        The context to use with multiprocessing.get_context()
        * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

    raises : bool = True
        Whether any error from the subprocess should filter up and be raised.

    warnings : bool = True
        Whether to emit pynisher warnings or not.
    """  # noqa
    ctx = multiprocessing.get_start_method() if context is None else context

    if ctx == "spawn":
        raise ValueError(
            "Due to how multiprocessing pickling works, `@limit(...)` does not"
            " for Mac or Windows, specifically with the `spawn` context."
            " Please use the `Pynisher` method of limiting."
        )

    # Incase the first argument is a function, we assume it was missued
    #
    # @limit
    # def f(): ...
    #
    # In this case, the function f will be passed as the first arg, `name`
    if callable(name):
        raise ValueError("Please pass arguments to decorator `limit`")

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            pynisher = Pynisher(
                func,
                name=name,
                memory=memory,
                cpu_time=cpu_time,
                wall_time=wall_time,
                grace_period=grace_period,
                raises=raises,
            )
            return pynisher.run(*args, **kwargs)

        return wrapper

    return decorator
