from __future__ import annotations

import multiprocessing
import os
import sys
import time

import psutil

from pynisher import contexts, limit

import pytest

# from test.util import walltime_sleep


def walltime_sleep(sleep: float) -> float:
    """Sleeps for `sleep` seconds"""
    time.sleep(sleep)
    return sleep


class CustomException(Exception):
    pass


def spawn_children(
    child_sleeps: list[int] = [10, 10],
    context: str | None = None,
    daemon: bool = True,
) -> bool:
    """Spawns children who sleep before sleeping itself"""
    ctx = multiprocessing.get_context(context)

    subprocesses = [
        ctx.Process(target=walltime_sleep, args=(i,), daemon=daemon, name="sleepy")
        for i in child_sleeps
    ]

    for p in subprocesses:
        p.start()

    ppid = os.getpid()

    raise CustomException([(ppid, p.pid) for p in subprocesses])


@pytest.mark.parametrize("pynisher_context", contexts)
@pytest.mark.parametrize("child_context", contexts)
@pytest.mark.parametrize("daemon", [True, False])
def test_terminate_child_processes_removes_all_children(
    pynisher_context: str, child_context: str, daemon: bool
) -> None:
    """
    Expects
    -------
    * All children processes should be cleaned up when by the time
     the function exits.
    """
    if pynisher_context == "fork" and child_context == "forkserver":
        pytest.skip(
            "Doesn't seem to like when pyisher uses 'fork' while the child uses"
            "'forkserver' to spawn new processes."
        )

    if (
        pynisher_context == "spawn"
        and child_context == "fork"
        and sys.version_info < (3, 8)
    ):
        pytest.skip(
            "Python 3.7 doesn't seem to allow for a 'spawn' process function"
            " to create new subprocesses with 'fork'"
        )

    lf = limit(
        spawn_children,
        wall_time=5,
        terminate_child_processes=True,
        context=pynisher_context,
    )
    with pytest.raises(CustomException) as e:
        lf(child_sleeps=[20, 20], context=child_context, daemon=daemon)

    children_pids = [pid for _, pid in e.value.args[0]]

    assert children_pids is not None and len(children_pids) > 0

    assert lf._process is not None and not lf._process.is_running()

    for pid in children_pids:
        try:
            child = psutil.Process(pid)
            assert not child.is_running()
        except psutil.NoSuchProcess:
            pass

    # Can't retrieve `children()` from dead process so we manually check the entire
    # process id list for children with the given ppid


@pytest.mark.parametrize("pynisher_context", contexts)
@pytest.mark.parametrize("child_context", contexts)
@pytest.mark.parametrize("daemon", [True, False])
def test_terminate_child_processes_false_keeps_children(
    pynisher_context: str,
    child_context: str,
    daemon: bool,
) -> None:
    """
    Expects
    -------
    * Child processes should not be killed if specified
    """
    if pynisher_context == "fork" and child_context == "forkserver":
        pytest.skip(
            "Doesn't seem to like when pyisher uses 'fork' while the child uses"
            "'forkserver' to spawn new processes."
        )

    if (
        pynisher_context == "spawn"
        and child_context == "fork"
        and sys.version_info < (3, 8)
    ):
        pytest.skip(
            "Python 3.7 doesn't seem to allow for a 'spawn' process function"
            " to create new subprocesses with 'fork'"
        )

    if daemon is False:
        pytest.skip(
            "Non-Daemon subprocess need to be terminate or `spawn_children`"
            " will timeout"
        )

    lf = limit(
        spawn_children,
        wall_time=5,
        terminate_child_processes=False,
        context=pynisher_context,
    )

    with pytest.raises(CustomException) as e:
        lf(child_sleeps=[20, 20], context=child_context, daemon=daemon)

    children_pids = [pid for _, pid in e.value.args[0]]

    assert children_pids is not None and len(children_pids) > 0

    assert lf._process is not None and not lf._process.is_running()

    for pid in children_pids:
        try:
            child = psutil.Process(pid)
            assert not child.is_running()
        except psutil.NoSuchProcess:
            pass


if __name__ == "__main__":
    """
    Testing out daemon processes and using htop to identify behaviour

    * Each of these seems to leave no long term hanging process as the
    subprocesses just sleep and exit. The onyl exception is Non-daemon
    subprocesses with no termination, this causes a hang. I guess this
    should be expected and a responsibility of the user.
    """
    print("Host process ", os.getpid())

    # Daemon processes and terminate
    lf = limit(spawn_children, terminate_child_processes=True)
    try:
        lf(daemon=True, child_sleeps=[30])
    except CustomException as e:
        raise e
        print(e.args, "Terminate and Daemon")

    # Daemon processes and no terminate
    lf = limit(spawn_children, terminate_child_processes=False)
    try:
        lf(daemon=True, child_sleeps=[30])
    except CustomException as e:
        print(e.args[0], "No Terminate and Daemon")

    # Non-Daemon processes and terminate
    lf = limit(spawn_children, terminate_child_processes=True)
    try:
        lf(daemon=False, child_sleeps=[30])
    except CustomException as e:
        print(e.args[0], "Terminate and no Daemon")

    # Non-Daemon processes and no terminate
    # This appears to hang as the
    lf = limit(spawn_children, terminate_child_processes=False)
    try:
        lf(daemon=False, child_sleeps=[30])
    except CustomException as e:
        print(e.args[0], "No Terminate and no Daemon")
