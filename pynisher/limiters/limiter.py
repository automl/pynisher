"""Limiters are what define how resources should be limited as well as handle."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

import platform
from multiprocessing import Connection


class Limiter(ABC):
    """Defines how to limit resources for a given system."""

    def __init__(
        self,
        func: Callable,
        output: Connection,
        memory: int | None = None,
        cpu_time: int | None = None,
        wall_time: int | None = None,
        grace_period: int = 0,
    ) -> None:
        """
        Parameters
        ----------
        func : Callable
            The function to be limited

        output : Connection
            The output multiprocessing.Connection object to pass the results back through

        memory : int | None = None
            The memory to allocate

        cpu_time : int | None = None
            The cput time to allocate

        wall_time : int | None = None
            The wall time to allocate

        grace_period : int = 0
            The grace period to give for a process to shutdown once signalled
        """
        self.func = func
        self.output = output
        self.memory = memory
        self.cpu_time = cpu_time
        self.wall_time = wall_time
        self.grace_period = grace_period

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Set process limits and then call the function with the given arguments.

        Will send it's output to `self.output(result: Any | None, exception: Exception | None)`.

        Note
        ----
        This should usually not be called by the end user, it's main use is in Pynisher::run().

        Parameters
        ----------
        *args, **kwargs
            Arguments to the function

        Returns
        -------
        None
        """
        try:
            # Go through each limitation we can apply, relying
            if self.memory is not None:
                self.limit_memory()

            if self.cpu_time is not None:
                self.limit_cpu_time()

            if self.wall_time is not None:
                self.limit_wall_time()

            # Call our function and if there are no exceptions raised, default to
            # no error or trace
            result = self.func(*args, **kwargs)
            error = None

            package = (result, error)

            self.output.send(package)

        except Exception as e:
            # If for whatever reason, we can't send something or the sending fails, we catch
            # the error and try to send that. If that also fails, there's not much we can do.
            result = None
            error = e

            package = (result, error)

            self.output.send(package)

        finally:
            # We are done
            self.output.close()

        return

    @staticmethod
    def create(
        func: Callable,
        output: Connection,
        memory: int | None = None,
        cpu_time: int | None = None,
        wall_time: int | None = None,
        grace_period: int | None = None,
    ) -> Limiter:
        """For full documentation, see __init__."""
        # NOTE: __init__ param duplication
        #
        #   I'm not delighted by the duplication of the __init__ params but this keeps things
        #   typesafe and referencable in case we need to validate

        # There is probably a lot more things to check but for now this covers our use case
        system_name = platform.system()

        # NOTE: Imports inside if statements
        #
        #   This servers two purposes, one is to prevent cyclical imports, as they need
        #   to inherit Limiter from this file, while this file needs to import them too,
        #   creating a circular dependancy... unless they're imported later.
        #
        #   Secondly, different systems will have different modules available. For example,
        #   the `resources` module is not avialable on Windows and so importing that would
        #   cause issues.
        #
        if system_name == "Linux":
            from pynisher.limiters.linux import LimiterLinux

            return LimiterLinux(
                func=func,
                output=output,
                memory=memory,
                cpu_time=cpu_time,
                wall_time=wall_time,
                grace_period=grace_period,
            )

        elif system_name == "Darwin":
            return LimiterDarwin(
                func=func,
                output=output,
                memory=memory,
                cpu_time=cpu_time,
                wall_time=wall_time,
                grace_period=grace_period,
            )

        else:
            raise NotImplementedError(
                f"We currently don't support your system: {platform}"
            )

    @abstractmethod
    def limit_memory(self) -> None:
        """Limit's the memory of this process."""
        ...

    @abstractmethod
    def limit_cpu_time(self) -> None:
        """Limit's the cpu time of this process."""
        ...

    @abstractmethod
    def limit_wall_time(self) -> None:
        """Limit's the wall time of this process."""
        ...
