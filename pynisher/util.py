from __future__ import annotations

from typing import Any, Callable

import os
import signal
from functools import partial

import psutil
from psutil import Process

_mem_unit_table = {
    "B": 1,
    "KB": 2**10,
    "MB": 2**20,
    "GB": 2**30,
}

_time_unit_table = {"s": 1, "m": 60, "h": 60 * 60}


def memconvert(x: float, *, frm: str = "B", to: str = "B") -> float:
    """Convert between memory units

    Parameters
    ----------
    x : float
        The memory amount

    frm : "B" | "KB" | "MB" | "GB" = "B"
        What unit it is in

    to :  "B" | "KB" | "MB" | "GB" = "B"
        What unit to convert to

    Returns
    -------
    float
        The memory amount
    """
    u_from = _mem_unit_table[frm.upper()]
    u_to = _mem_unit_table[to.upper()]

    as_bytes = x * u_from
    as_target = as_bytes / u_to

    # We can't see a use case for float Bytes
    if to.upper() == "B":
        return round(as_target)
    else:
        return as_target


def timeconvert(x: float, *, frm: str = "s", to: str = "s") -> float:
    """Convert between time units

    Parameters
    ----------
    x: float
        The time amount

    frm: "s" | "m" | "h" = "s"
        What unit it is in

    to: "s" | "m" | "h" = "s"
        What unit to convert to

    Returns
    -------
    float
        The time amount
    """
    u_from = _time_unit_table[frm.lower()]
    u_to = _time_unit_table[to.lower()]

    as_seconds = x * u_from
    as_target = as_seconds / u_to

    return as_target


def callstring(f: Callable, *args: Any, **kwargs: Any) -> str:
    """Get a string of the function being called with the args and kwargs

    Parameters
    ----------
    f: Callable
        The function

    *args, **kwargs

    Returns
    -------
    str
        The function call as a str
    """
    parts = list(map(str, args)) + [f"{k}={v}" for k, v in kwargs.items()]
    param_str = ", ".join(parts)
    if isinstance(f, partial):
        name = f.func.__name__
    elif hasattr(f, "__qualname__"):
        name = f.__qualname__
    elif hasattr(f, "__class__"):
        name = f.__class__.__name__
    else:
        name = str(f)

    return f"{name}({param_str})"


def terminate_process(
    pid: int | None | psutil.Process = None,
    sig: int = signal.SIGTERM,
    timeout: int = 5,
    children: bool = True,
    parent: bool = False,
    on_terminate: Callable[[psutil.Process], Any] | None = None,
) -> tuple[list[psutil.Process], list[psutil.Process]]:
    """Attemps to terminate a process

    * https://psutil.readthedocs.io/en/latest/#kill-process-tree
    """
    if children is True:
        return terminate_process_tree(
            pid=pid,
            include_parent=parent,
            sig=sig,
            timeout=timeout,
        )
    else:
        if isinstance(pid, psutil.Process):
            process = pid
        else:
            try:
                process = psutil.Process(pid)
            except psutil.NoSuchProcess:
                return ([], [])

        process.send_signal(sig)
        gone, alive = psutil.wait_procs(
            [process], timeout=timeout, callback=on_terminate
        )

        for p in alive:
            p.kill()

        gone, alive = psutil.wait_procs(
            [process], timeout=timeout, callback=on_terminate
        )
        return (gone, alive)


def terminate_process_tree(
    pid: int | None | psutil.Process = None,
    sig: int = signal.SIGTERM,
    timeout: int = 5,
    include_parent: bool = True,
    on_terminate: Callable[[psutil.Process], Any] | None = None,
) -> tuple[list[psutil.Process], list[psutil.Process]]:
    """Attemps to get all the children of the process and then terminate them

    * https://psutil.readthedocs.io/en/latest/#kill-process-tree
    """
    parent = None

    if isinstance(pid, psutil.Process):
        parent = pid
        _pid = parent.pid
    elif isinstance(pid, int):
        _pid = pid
    else:
        _pid = os.getpid()

    if _pid == os.getpid() and include_parent:
        raise RuntimeError(f"Can't kill this process ({pid}) from within itself")

    # Get the parent and its children
    try:
        if parent is None:
            parent = psutil.Process(pid=_pid)

        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []

    if include_parent and parent is not None:
        children.append(parent)

    for child in children:
        try:
            child.send_signal(sig)
        except psutil.NoSuchProcess:
            pass

    gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)

    # If any are still alive, SIGKILL
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass

    gone, alive = psutil.wait_procs(children, timeout=None, callback=on_terminate)
    return (gone, alive)


class Monitor:
    def __init__(self, pid: int | None = None):
        """
        Parameters
        ----------
        pid : int | None = None
            The process id to monitor, defaults to current process
        """
        self.process = Process(pid)

    def memory(self, units: str = "B", *, kind: str = "vms") -> float:
        """Get the memory consumption

        Parameters
        ----------
        units : "B" | "KB" | "MB" | "GB" = "B"
            Units to measure in

        kind : "vms" | "rss" = "vms"
            The kind of memory to measure.
            https://psutil.readthedocs.io/en/latest/#psutil.Process.memory_info

        Returns
        -------
        float
            The memory used
        """
        mem = self.process.memory_info()
        if not hasattr(mem, kind):
            raise ValueError(f"No memory kind {kind}, use one from {mem}")

        usage = getattr(mem, kind)
        return memconvert(usage, frm="B", to=units)

    def memlimit(self, units: str = "B") -> tuple[float, float] | None:
        """

        We can't limit using resource.setrlimit as it seems that None of the
        RLIMIT_X's are available. This we debugged by using
        `import psutil; print(dir(psutil))` in which a MAC system did not have
        any `RLIMIT_X` attributes while a Linux system did.

        Parameters
        ----------
        units : "B" | "KB" | "MB" | "GB" = "B"
            Units to measure in

        Returns
        -------
        float | None
            The memory limit.
            Returns None if it can't be gotten
        """
        if hasattr(psutil, "RLIMIT_AS"):
            limits = self.process.rlimit(psutil.RLIMIT_AS)
            if units != "B":
                limits = tuple(memconvert(x, frm="B", to=units) for x in limits)
            return limits
        else:
            return None
