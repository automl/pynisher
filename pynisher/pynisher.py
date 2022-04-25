from __future__ import annotations

from typing import Any, Callable, TypeVar

import multiprocessing
import platform
from contextlib import ContextDecorator
from functools import wraps

from pynisher.exceptions import (
    CpuTimeoutException,
    MemoryLimitException,
    WallTimeoutException,
)
from pynisher.limiters import Limiter
from pynisher.support import supports
from pynisher.util import callstring, memconvert


class EMPTY:
    """An indicator of no result, followings `inspect._empty` pattern"""


_empty = EMPTY()


# After a process has return a result or has been terminated, we
# give it `SAFE_JOIN_TIME` seconds to try clean up if it hasn't already
# returned
SAFE_JOIN_TIME = 5


class Pynisher(ContextDecorator):
    """Restrict a function's resources"""

    def __init__(
        self,
        func: Callable,
        *,
        name: str | None = None,
        memory: int | tuple[int, str] | None = None,
        cpu_time: int | None = None,
        wall_time: int | None = None,
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

        cpu_time : int | None = None
            The amount of cpu time in seconds to limit to

        wall_time : int | None = None
            The amount of total wall time in seconds to limit to

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
        if not callable(func):
            raise ValueError(f"`func` ({func}) must be callable")

        if cpu_time is not None and not cpu_time >= 1:
            raise ValueError(f"`cpu_time` ({cpu_time}) must be int >= 1")

        if wall_time is not None and not wall_time >= 1:
            raise ValueError(f"`wall_time` ({wall_time}) must be int >= 1")

        if not grace_period >= 1:
            raise ValueError(f"`grace_period` ({grace_period}) must be int >= 1")

        valid_contexts = ["fork", "spawn", "forkserver", None]
        if context not in valid_contexts:
            raise ValueError(f"`context` ({context}) must be in {valid_contexts}")

        if isinstance(memory, tuple):
            x, unit = memory
            memory = int(memconvert(x, frm=unit, to="B"))

        if memory is not None and not memory >= 1:
            raise ValueError(f"`memory` ({memory}) must be int >= 1")

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
            wall_time=self.wall_time,
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

        # 4 kinds of `response`
        #
        # * (result, None)          | success
        # * None, (err, traceback)  | failed, error raised (cputime, mem, any error)
        # * None                    | failed, MemoryError during sending of above error
        # * _empty                  | failed, nothing received from pipe (walltime)
        response = _empty

        # Let loose
        subprocess.start()

        try:

            if self.wall_time is None:
                # Block here until we get a response
                response = receive_pipe.recv()
            elif receive_pipe.poll(self.wall_time):
                # `wall_time`
                #   We can block with `poll` with a timeout of `wall_time` seconds
                #   This gives us a platform independant implementation for wall_time
                response = receive_pipe.recv()
            else:
                response = _empty

                # Wall time elapsed, terminate the process
                subprocess.terminate()

        except EOFError:
            # This is raised when there is nothing left in the pipe to receive
            # and the other end was closed. Probably not needed but good to have incase
            # See:
            # * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.connection.Connection.recv  # noqa
            response = _empty

        finally:
            # Join up the subprocess if it's still alive somehow
            subprocess.join(timeout=SAFE_JOIN_TIME)
            receive_pipe.close()
            send_pipe.close()

        # If we never got a response, it was a WallTimeoutException
        if isinstance(response, EMPTY):

            if not self.raises:
                return _empty

            raise WallTimeoutException(
                f"Did not finish in time ({self.wall_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        # We got a response from the subprocess but it had no memory to do a send
        if response is None:

            if not self.raises:
                return _empty

            raise MemoryLimitException(
                "Sending the results/err from the subprocess caused a memory error."
                f" Could not retrieve a traceback or cause from subprocess."
                f"\n{callstring(self.func, *args, **kwargs)}"
            )

        # We got something back through the pipe, lets see what it is
        result, error = response

        # We got a result, yay, return it
        # We can't check for `result is not None` as `None` is a valid thing
        # that a restricted function could return, hence we check for the precense
        # of an error
        if error is None:
            return result

        # There was some sort of error, but we shouldn't raise, give EMPTY
        if not self.raises:
            return EMPTY

        # Handle the error
        err, tb = error

        # It was a cpu timeout triggered
        if self.cpu_time is not None and isinstance(err, CpuTimeoutException):
            msg = (
                f"Did not finish in cpu time ({self.cpu_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            raise CpuTimeoutException(msg) from err

        # It was a memory error
        if self.memory is not None and isinstance(err, MemoryError):
            msg = (
                f"Exceeded memory limit ({self.memory}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            raise MemoryLimitException(msg) from err

        # We don't know what it is, could be an issue in the function call
        msg = f"Process failed with the below traceback\n\n{tb}\n\n"
        raise err.__class__(msg) from err

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

    cpu_time : int | None = None
        The amount of cpu time in seconds to limit to

    wall_time : int | None = None
        The amount of total wall time in seconds to limit to

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
    if not Pynisher.supports("decorator"):
        version = platform.python_version_tuple()
        plat = platform.platform()
        raise RuntimeError(
            "Due to how multiprocessing pickling works, `@limit(...)` does not"
            f" work for {plat} with Python {version}."
            " Please use the `Pynisher` method of limiting resources."
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
