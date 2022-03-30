from __future__ import annotations

from typing import Any, Callable, TypeVar

import multiprocessing
from contextlib import ContextDecorator
from functools import wraps

from pynisher.limiters import Limiter


class Pynisher(ContextDecorator):
    """TODO add some documentation on class"""

    def __init__(
        self,
        func: Callable,
        *,
        name: str | None = None,
        memory: int | None = None,
        cpu_time: int | None = None,
        wall_time: int | None = None,
        grace_period: int = 0,
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

        memory : int | None = None
            The amount of memory in bytes to limit by
            TODO: Could optionally accept a tuple (4, "MB") and infer single int as Bytes

        cpu_time : int | None = None
            The amount of cpu time in second to limit to

        wall_time : int | None = None
            The amount of total wall time to limit to

        grace_period : int = 0
            Buffer time to give to a process to end when given a signal to end.

        context : str = "fork" | "spawn" | "forkserver" | None
            The context to use with multiprocessing.get_context()
            * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

        raises : bool = True
            Whether any error from the subprocess should filter up and be raised.
        """
        self.func = func
        self.name = name
        self.memory = memory
        self.cpu_time = cpu_time
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
        send_pipe, recieve_pipe = self.context.Pipe(duplex=False)

        # The limiter's __call__ will be what's run inside the subprocess, therefor it
        # needs access to vital information, namely:
        # * The function, it's arguments and its kwarguments
        # * The `recieve_pipe` through which it it should `output` it's results to
        limiter = Limiter.create(
            func=self.func,
            output=recieve_pipe,
            memory=self.memory,
            cpu_time=self.cpu_time,
            wall_time=self.wall_time,
            grace_period=self.grace_period,
        )

        # We now create the subprocess and let it know that it should call the limiter's __call__
        subprocess = self.context.Process(
            target=limiter.__call__,
            args=args,
            kwargs=kwargs,
            daemon=False,
            name=self.name,
        )

        try:
            process_error = None

            subprocess.start()

            # Will block here until a result is given back
            result, process_error = recieve_pipe.recv()

            # If we are allowed to raise, we raise a new exception here to get a traceback
            # from this master process
            if process_error is not None and self.raises:
                raise process_error

        except Exception as e:
            # If raising, we get the error from this process and append the traceback from
            # the error in the subprocess, if it's available. There could also be an issue
            # from just subprocess.start(), in which case `process_error` will be None
            if process_error is not None:
                raise e.with_traceback(process_error.__traceback__)
            else:
                raise e

        finally:
            send_pipe.close()
            recieve_pipe.close()

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
    memory: int | None = None,
    cpu_time: int | None = None,
    wall_time: int | None = None,
    grace_period: int = 0,
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
        A name to give the process that gets created, defaults to whatever multiprocessing.Process
        defaults to.

    memory : int | None = None
        The amount of memory in bytes to limit by
        TODO: Could optionally accept a tuple (4, "MB") and infer single int as Bytes

    cpu_time : int | None = None
        The amount of cpu time in second to limit to

    wall_time : int | None = None
        The amount of total wall time to limit to

    grace_period : int = 0
        Buffer time to give to a process to end when given a signal to end.

    context : str = "fork" | "spawn" | "forkserver" | None
        The context to use with multiprocessing.get_context()
        * https://docs.python.org/3/library/multiprocessing.html#multiprocessing.get_context

    raises : bool = True
        Whether any error from the subprocess should filter up and be raised.
    """

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


def func(number: int) -> int:
    """Test function."""
    return number


@limit(memory=1000)
def f(x: int) -> int:
    """Test function."""
    return x * 2


if __name__ == "__main__":
    with Pynisher(func, memory=1024, wall_time=120) as restricted_func:
        result = restricted_func(number=3)

    restricted_func = Pynisher(func, memory=1024)
    result = restricted_func.run(number=4)
