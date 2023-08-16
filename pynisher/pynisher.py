from __future__ import annotations

from typing import Any, Callable, Generic, Type, TypeVar, overload

import multiprocessing
import signal
import sys
import time
import warnings
from functools import wraps
from multiprocessing.context import BaseContext

import psutil
from typing_extensions import Literal, ParamSpec

from pynisher.exceptions import (
    CpuTimeoutException,
    MemoryLimitException,
    PynisherException,
    TimeoutException,
    WallTimeoutException,
)
from pynisher.limiters import Limiter
from pynisher.support import contexts as valid_contexts
from pynisher.support import supports
from pynisher.util import callstring, memconvert, terminate_process, timeconvert
from pynisher.win_errcodes import WIN_CPUTIMEOUT_EXITCODES, WIN_MEMORY_EXITCODES


class _EMPTY:
    pass


EMPTY = _EMPTY()

# For typing the pynished function
T = TypeVar("T")
P = ParamSpec("P")

# For returning the same type as itself, see __enter__
Self = TypeVar("Self")


class Pynisher(Generic[P, T]):
    """Restrict a function's resources"""

    WallTimeoutException = WallTimeoutException
    CpuTimeoutException = CpuTimeoutException
    MemoryLimitException = MemoryLimitException
    PynisherException = PynisherException
    TimeoutException = TimeoutException

    # If `raises=True` or left as default, the return type when calling is just T
    @overload
    def __init__(
        self: Pynisher[P, T],
        func: Callable[P, T],
        *,
        raises: Literal[True] = ...,
        name: str | None = ...,
        memory: int | tuple[int, str] | None = ...,
        cpu_time: int | tuple[float, str] | None = ...,
        wall_time: int | tuple[float, str] | None = ...,
        context: str | BaseContext | None = ...,
        warnings: bool = ...,
        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = ...,
        terminate_child_processes: bool = ...,
        forceful_keyboard_interrupt: bool = ...,
    ) -> None:
        ...

    # If `raises=False` or just some unknown bool value,
    # the return type when calling is T | _EMPTY
    @overload
    def __init__(
        self: Pynisher[P, T | _EMPTY],
        func: Callable[P, T],
        *,
        raises: bool,
        name: str | None = ...,
        memory: int | tuple[int, str] | None = ...,
        cpu_time: int | tuple[float, str] | None = ...,
        wall_time: int | tuple[float, str] | None = ...,
        context: str | BaseContext | None = ...,
        warnings: bool = ...,
        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = ...,
        terminate_child_processes: bool = ...,
        forceful_keyboard_interrupt: bool = ...,
    ) -> None:
        ...

    def __init__(
        self,
        func: Callable[P, T],
        *,
        name: str | None = None,
        memory: int | tuple[int, str] | None = None,
        cpu_time: int | tuple[float, str] | None = None,
        wall_time: int | tuple[float, str] | None = None,
        context: str | BaseContext | None = None,
        raises: bool = True,
        warnings: bool = True,
        wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False,
        terminate_child_processes: bool = True,
        forceful_keyboard_interrupt: bool = True,
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

        context : "fork" | "forkserver" | "spawn"  | BaseContext | None = None
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

        forceful_keyboard_interrupt: bool = True
            Whether keyboard interrupts should forceably kill any subprocess or the
            pynished function. If True, it will temrinate the process tree of
            the pynished function and then reraise the KeyboardInterrupt.
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

        if isinstance(context, str) and context not in valid_contexts:
            raise ValueError(f"`context` {context} must be in {valid_contexts}")

        if isinstance(wrap_errors, dict):
            valid_keys = {"memory", "wall_time", "cpu_time", "pynisher"}
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
        self.context = (
            multiprocessing.get_context(context)
            if isinstance(context, str) or context is None
            else context
        )
        self.warnings = warnings
        self.wrap_errors = wrap_errors
        self.terminate_child_processes = terminate_child_processes
        self.forceful_keyboard_interrupt = forceful_keyboard_interrupt

        # Set once the function is running
        self._process: psutil.Process | None = None

    def __enter__(self: Self) -> Self:
        """Doesn't do anything too useful at the moment.

        Returns
        -------
        (*args, **kwargs) -> Any
            Call your function and get back the result
        """
        return self

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

    # Call with `raises=True`
    @overload
    def __call__(
        self: Pynisher[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    # Call with `raises=False`
    @overload
    def __call__(
        self: Pynisher[P, T | _EMPTY],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T | _EMPTY:
        ...

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T | _EMPTY:
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
        subprocess = self.context.Process(  # type: ignore
            target=limiter.__call__,
            args=args,  # type: ignore
            kwargs=kwargs,  # type: ignore
            daemon=False,
            name=self.name,
        )

        # Make sure that if this process is killed, make any connections are closed
        # and the subprocess is killed
        _default_sigterm_handler: signal._HANDLER = signal.getsignal(signal.SIGTERM)
        if _default_sigterm_handler is signal.Handlers.SIG_IGN:
            warnings.warn(
                f"SIGTERM is ignored by this process for this function {self.func}, "
                " ignoring this as the output connection must be closed "
            )

        def _closing_handler(sig: int, frame: Any) -> None:
            if subprocess.is_alive():
                subprocess.kill()

            receive_pipe.close()
            subprocess.join(0.1)

            # Let the default handler run
            if sig is signal.SIGTERM and callable(_default_sigterm_handler):
                _default_sigterm_handler(sig, frame)

        signal.signal(signal.SIGTERM, _closing_handler)

        # Let loose
        subprocess.start()

        # Get a psutil handle to the process
        try:
            self._process = psutil.Process(subprocess.pid)
        except psutil.NoSuchProcess:
            # Likely only to occur when subprocess already finished
            pass

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
        result: _EMPTY | T = EMPTY
        err: Exception | None = None
        tb: str | None = None

        # Retrieve a result if we can. We have to manually loop this because if the
        # subprocess abruptly crashes in such a way that the pipe never closes, we will
        # hang forever
        start = time.time()
        interval = 0.01
        try:
            while True:
                if (
                    self.wall_time is not None
                    and (time.time() - start) > self.wall_time
                ):
                    result = EMPTY
                    tb = None
                    err = WallTimeoutException(
                        f"Your function took longer than {self.wall_time} seconds to"
                        f" run.\n{callstring(self.func, *args, **kwargs)}",
                    )
                    break
                elif receive_pipe.poll(interval):
                    response = receive_pipe.recv()
                    if response is not None:
                        result, err, tb = response
                    else:
                        result = EMPTY
                        tb = None
                        err = MemoryLimitException(
                            "While returning the result from your function,"
                            " we could not retrieve the result or any error"
                            " about why."
                            f"\n{callstring(self.func, *args, **kwargs)}",
                        )
                    break
                elif not subprocess.is_alive():
                    result = EMPTY
                    tb = None
                    err = None
                    break

        # Otherwise, there was nothing to read
        except EOFError:
            result = EMPTY
            tb = None
            err = MemoryLimitException(
                "There but could not a send response back."
                " This is likely a MemoryError."
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
        except KeyboardInterrupt as e:
            # The keyboard interrupt will be send to all processes simultaneuously
            # and handled by each of them. The default behaviour is to terminate
            # but this can be caught by a subprocess and ignored. To circumvent
            # this, we convert this keyboard interrupt into a SIGTERM and propgate it
            try:
                # We assume this will return if all subprocess have terminated
                # due to the keyboard interrupt
                subprocess.join(timeout=1)
            except TimeoutError:
                # If not, we will escalate the keyboard interrupt to a SIGTERM
                # and give the subprocesses a chance to terminate
                if self.forceful_keyboard_interrupt:
                    terminate_process(
                        subprocess.pid,
                        children=self.terminate_child_processes,
                        parent=True,
                    )
                    subprocess.join(timeout=1)
            finally:
                # We now ensure all subprocesses are sent a SIGTERM if still existing
                terminate_process(
                    subprocess.pid,
                    children=self.terminate_child_processes,
                    parent=True,
                )

                # If the subprocesses are still alive, we will send a SIGKILL
                try:
                    subprocess.join(0.1)
                except TimeoutError:
                    terminate_process(
                        subprocess.pid,
                        children=self.terminate_child_processes,
                        parent=True,
                        sig=signal.SIGKILL,
                    )
                finally:
                    # At this point, we have tried to terminate the subprocesses
                    # as gracefully as possible. We now wait for them to terminate
                    # and close the pipes
                    try:
                        subprocess.join(1)
                    except TimeoutError:
                        pass

                    receive_pipe.close()
                    send_pipe.close()

            raise KeyboardInterrupt from e
        finally:
            # Close the pipes
            receive_pipe.close()
            send_pipe.close()

            # Tell the subprocess to terminate with SIGTERM
            terminate_process(
                subprocess.pid,
                children=self.terminate_child_processes,
                parent=True,
            )

        # exitcode here can only take on 3 values
        #
        # * None        | the subprocess is still running (walltime elapsed)
        # * 0           | Ended gracefully, pipe is closed or response in the pipe
        # * != 0        | Process was terminated non-gracefully, nothing in the pipe
        #               | and it may not be closed
        exitcode = subprocess.exitcode

        # We got a result or an error
        if result is not EMPTY or err is not None:
            # If an error, the result must be empty
            if err is not None:
                result = EMPTY

            return self._handle_return(result=result, err=err, tb=tb)

        # Process ended gracefully but no result?
        if exitcode == 0:
            err = PynisherException(
                f"Function ended properly but no result was recieved."
                f" Got exitcode 0 from subprocess that ran:"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            return self._handle_return(err=err)

        # Wall time expired
        if exitcode is None:
            err = WallTimeoutException(
                f"Did not finish in time ({self.wall_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            return self._handle_return(err=err)

        # Cputime expired on windows
        if (
            sys.platform.lower().startswith("win")
            and self.cpu_time is not None
            and exitcode in WIN_CPUTIMEOUT_EXITCODES
        ):
            err = CpuTimeoutException(
                f"Did not finish in cpu time ({self.cpu_time}s)."
                f" Specific exitcode is {exitcode}"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            return self._handle_return(err=err)

        # Memory reasons to kill process on windows
        if (
            sys.platform.lower().startswith("win")
            and self.memory is not None
            and exitcode in WIN_MEMORY_EXITCODES
        ):
            # We can't be certain it was caused by a cputimeout but the exist status
            # in this case is non-consisten and I do not know a way to identify the
            # object timed out properly
            err = MemoryLimitException(
                f"Not enough memory to run function ({self.memory}B)."
                f" Specific exitcode is {exitcode}"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            return self._handle_return(err=err)

        # We got a segmentation fault, if memomory was set, we assume it's a memory
        # related issue
        if exitcode == -signal.SIGSEGV and self.memory is not None:
            err = MemoryLimitException(
                "The function exited with a segmentation error (SIGSEGV) and a memory"
                " limit was set. We presume this is due to the memory limit. This may"
                " not be the case but is quite likely if your function works without a"
                " memory constraint."
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            return self._handle_return(err=err)

        # We got a SIGXCPU and cputime was set
        if (
            self.cpu_time is not None
            and hasattr(signal, "SIGXCPU")
            and exitcode == -signal.SIGXCPU
        ):
            err = CpuTimeoutException(
                f"Did not finish in cpu time ({self.cpu_time}s)"
                f"\n{callstring(self.func, *args, **kwargs)}"
            )
            return self._handle_return(err=err)

        # We didn't get a result and the pipe closed in some way we weren't expecting
        err = PynisherException(
            f"Unknown reason for exitcode {exitcode}, no result or error recieved and "
            f" killed process \n{callstring(self.func, *args, **kwargs)}"
        )
        return self._handle_return(err=err)

    def _handle_return(
        self,
        result: T | _EMPTY = EMPTY,
        err: Exception | None = None,
        tb: str | None = None,
    ) -> T | _EMPTY:
        # We need at least an error or a result, not both
        assert (result is EMPTY) ^ (err is None)

        # We got a non empty result, hurray
        if result is not EMPTY:
            return result

        # Otherwise, we have some error
        assert err is not None

        # Don't raise?
        if not self.raises:
            return EMPTY

        if (
            isinstance(err, MemoryError)
            and self.memory is not None
            and not isinstance(err, MemoryLimitException)
        ):
            err = MemoryLimitException(f"MemoryError raised with limit {self.memory}B")

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


@overload
def restricted(
    name: str | None = ...,
    *,
    raises: Literal[True] = ...,
    memory: int | tuple[int, str] | None = ...,
    cpu_time: int | None = ...,
    wall_time: int | None = ...,
    context: str | BaseContext | None = ...,
    warnings: bool = ...,
    wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = ...,
    terminate_child_processes: bool = ...,
    forceful_keyboard_interrupt: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    ...


@overload
def restricted(
    name: str | None = ...,
    *,
    raises: bool,
    memory: int | tuple[int, str] | None = ...,
    cpu_time: int | None = ...,
    wall_time: int | None = ...,
    context: str | BaseContext | None = ...,
    warnings: bool = ...,
    wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = ...,
    terminate_child_processes: bool = ...,
    forceful_keyboard_interrupt: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T | _EMPTY]]:
    ...


# NOTE: Simpler solution?
#
#   There might be a simpler solution then redfining a function, e.g. `restricted =
#   Pynisher` but it gets complicated as we need something like
#   `@restricted(memory=...)` but that won't work as the first arg to
#   `Pynisher.__init__` should be the function itself. For now this should work
#
# Note: Having one positional argument
#
#   This just lets us catch the cases where someone incorrectly uses the decorator as
#   the first argument would be the function. Otherwise with only keyord arguments,
#   you would get a python exception that just says function doesn't except positinal
#   arguments
#
#   @restricted   # <- Should raise helpful error
#   def f(): ...
#
def restricted(
    name: str | None = None,
    *,
    memory: int | tuple[int, str] | None = None,
    cpu_time: int | None = None,
    wall_time: int | None = None,
    context: str | BaseContext | None = None,
    raises: bool = True,
    warnings: bool = True,
    wrap_errors: bool | list[str | Type[Exception]] | dict[str, Any] = False,
    terminate_child_processes: bool = True,
    forceful_keyboard_interrupt: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T | _EMPTY]]:
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

    context : "fork" | "forkserver" | "spawn" | BaseContext | None = None
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

    forceful_keyboard_interrupt: bool = True
        Whether keyboard interrupts should forceably kill any subprocess or the
        pynished function. If True, it will temrinate the process tree of
        the pynished function and then reraise the KeyboardInterrupt.
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

    def decorator(func: Callable[P, T]) -> Callable[P, T | _EMPTY]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | _EMPTY:
            pynisher = Pynisher(
                func,
                name=name,
                memory=memory,
                cpu_time=cpu_time,
                wall_time=wall_time,
                raises=raises,
                warnings=True,
                wrap_errors=False,
                terminate_child_processes=True,
                forceful_keyboard_interrupt=True,
            )
            return pynisher(*args, **kwargs)

        return wrapper

    return decorator


limit = Pynisher
