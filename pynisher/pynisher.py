import os
from abc import abstractmethod
from typing import Callable
from pynisher.limit_function_call import *  # noqa


class Pynisher:
    def __init__(
        self,
        func: Callable,
        memory: int = None,
        cpu_time: int = None,
        wall_time: int = None,
        grace_period: int = None,
        context=None,
    ) -> None:
        self.func = func
        self.memory = memory
        self.cpu_time = cpu_time
        self.wall_time = wall_time
        self.grace_period = grace_period

        if context is None:
            self.context = os.environ.get("CONTEXT", "fork")
        else:
            self.context = context

    def __enter__(self) -> Callable:
        """

        Returns
        -------
        Callable
            Returns limited function.
        """

        limiter = Limiter(self.memory, self.cpu_time, self.wall_time, self.grace_period)

        def limited_func(*args, **kwargs):

            parent_conn, child_conn = self.context.Pipe(duplex=False)
            subprocess = self.context.Process(
                target=limiter.__call__,
                name="pynisher function call",
                args=(self.func,) + args,
                kwargs=kwargs,
            )

            subprocess.start()

        return self.limit

    def __exit__(self) -> None:
        pass


class Limiter:
    def __init__(
        self,
        memory: int = None,
        cpu_time: int = None,
        wall_time: int = None,
        grace_period: int = None,
    ) -> None:
        self.memory = memory
        self.cpu_time = cpu_time
        self.wall_time = wall_time
        self.grace_period = grace_period

    def __call__(self, func, *args, **kwargs) -> None:

        func(*args, **kwargs)

        if self.memory is not None:
            self.limit_memory()

        if self.cpu_time is not None:
            self.limit_cpu_time()

        pass

    @abstractmethod
    def limit_memory():
        pass


class PynisherMac(Pynisher):
    def limit(self, func, *args, **kwargs) -> None:
        return None


def func(number: int) -> None:
    return number


if __name__ == "__main__":

    with Pynisher(func, memory=1024, time=120) as limitted_func:
        result = limitted_func(number=3)
