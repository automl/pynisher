from __future__ import annotations

from typing import Any, Callable, TypeVar

import multiprocessing
from contextlib import ContextDecorator
from functools import wraps

from pynisher.limiters import Limiter
from pynisher.exceptions import MemorylimitException
from pynisher.util import memconvert


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
        context: str = "fork",
        raises: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        func : Callable
            The function to limit and call

        name : str | None
            A name to give the process that gets created, defaults to whatever multiprocessing.Process
            defaults to.

        memory : int | tuple[int, str] | None = None
            The amount of memory to limit by. If `tuple`, specify with units like (4, "MB").
            Possible units are "B", "KB", "MB", "GB".

            Processes are given some dedicated size before any limitation can take place.
            These will run fine until a new allocation takes place.
            This means a process can technically run in a limit of 1 Byte, up until the
            point it tries to allocate anything.

        cpu_time : int | None = None
            The amount of cpu time in second to limit to

        wall_time : int | None = None
            The amount of total wall time to limit to

        grace_period : int = 1
            Buffer time to give to a process to end when given a signal to end.

        context : str = "fork" | "spawn" | "forkserver" | None
            The context to use with multiprocessing.get_context()
            * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

        raises : bool = True
            Whether any error from the subprocess should filter up and be raised.
        """
        if isinstance(memory, tuple):
            x, unit = memory
            memory = int(memconvert(x, frm=unit, to="B"))

        if memory is not None and memory <= 1:
            raise ValueError(f"`memory` ({memory}) must be int >= 1")

        if cpu_time is not None and cpu_time <= 1:
            raise ValueError(f"`cpu_time` ({cpu_time}) must be int >= 1")

        if wall_time is not None and wall_time <= 1:
            raise ValueError(f"`wall_time` ({wall_time}) must be int >= 1")

        if grace_period <= 1:
            raise ValueError(f"`grace_period` ({grace_period}) must be int >= 1")

        valid_contexts = ["fork", "spawn", "forkserver"]
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
        recieve_pipe, send_pipe = self.context.Pipe(duplex=False)

        # The limiter is what is in charge of limiting resources once inside the subprocess
        # It gets the `recieve_pipe` through which it it should `output` it's results to
        limiter = Limiter.create(
            func=self.func,
            output=send_pipe,
            memory=self.memory,
            cpu_time=self.cpu_time,
            wall_time=self.wall_time,
            grace_period=self.grace_period,
        )

        # We now create the subprocess and let it know that it should call the limiter's __call__
        # with the args and kwargs for the function being limited
        subprocess = self.context.Process(
            target=limiter.__call__,
            args=args,
            kwargs=kwargs,
            daemon=False,
            name=self.name,
        )

        process_error = None
        result = None

        # Let loose and hope it doesn't raise
        subprocess.start()

        try:
            # Will block here until a result is given back from the subprocess
            result, process_error = recieve_pipe.recv()
        except EOFError:
            # This is raised when there is nothing left in the pipe to recieve
            # and the other end was closed. Should be fine without it but it's
            # some good extra backup
            pass

        # Block here until the subprocess has joined back up, this should be almost
        # immediatly after sending back the result through `recv`
        subprocess.join()

        # send_pipe should be closed by the subprocess but just incase, close anyways
        send_pipe.close()
        recieve_pipe.close()

        # If we are allowed to raise, we raise a new exception here to get a traceback
        # from this master process.
        if process_error is not None and self.raises:
            suberr, tb = process_error

            # For backwards
            if isinstance(suberr, MemoryError):
                errcls = MemorylimitException
            else:
                errcls = suberr.__class__

            # We create an error of the same type and append the subporccess traceback
            msg = f"Process failed with the below traceback\n\n{tb}"
            raise errcls(msg) from suberr

        return result


# NOTE: Can only use typevar on decorator
#
#   Since the typevar only exist in the indentation context, we can use it here for
#   the full function scope to annotate the return type. To do so for the class Pynisher,
#   we would have to make it generic, probably not worth the extra complexity
#
T = TypeVar("T")


# NOTE: Simpler solution?
#
#   There might be a simpler solution then redfining a function, e.g. `limit = Pynisher` but
#   it gets complicated as we need something like `@limit(memory=...)` but that won't work
#   as the first arg to `Pynisher.__init__` should be the function itself. For now this should
#   work
#
def limit(
    name: str | None = None,
    memory: int | tuple[int, str] | None = None,
    cpu_time: int | None = None,
    wall_time: int | None = None,
    grace_period: int = 1,
    context: str = "fork",
    raises: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:  # Lol ((...) -> T) -> ((...) -> T)
    """Limit a function by using subprocesses

    ..code:: python

        @limit(memory=1000, wall_time=14)
        def f(x: int) -> int:
            return x * 2

        f()

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
        The amount of cpu time in second to limit to

    wall_time : int | None = None
        The amount of total wall time to limit to

    grace_period : int = 1
        Buffer time to give to a process to end when given a signal to end.

    context : str = "fork" | "spawn" | "forkserver" | None
        The context to use with multiprocessing.get_context()
        * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

    raises : bool = True
        Whether any error from the subprocess should filter up and be raised.
    """
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
