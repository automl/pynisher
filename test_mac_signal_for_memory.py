from __future__ import annotations

import resource
import signal
import time

from pynisher import limit
from pynisher.util import memconvert


def usememory(x: int | tuple[int, str]) -> int:
    """Use a certain amount of memory in B"""
    if isinstance(x, tuple):
        amount, unit = x
        x = round(memconvert(amount, frm=unit))

    bytearray(int(x))
    time.sleep(10)
    return x


def handler(signal, frame) -> None:
    print(signal, frame)


def limit_memory(memory: int) -> None:
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
        try:
            signum = getattr(signal, i)
            print("register {}, {}".format(signum, i))
            signal.signal(signum, handler)
        except:
            print("Skipping %s" % i)

    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (memory, hard))

    soft, hard = resource.getrlimit(resource.RLIMIT_DATA)
    resource.setrlimit(resource.RLIMIT_DATA, (memory, hard))

    soft, hard = resource.getrlimit(resource.RLIMIT_RSS)
    resource.setrlimit(resource.RLIMIT_RSS, (memory, hard))


def subfunc(limit, usemem) -> None:
    limit_memory(limit)
    usememory(usemem)


if __name__ == "__main__":
    memlimit = int(memconvert(100, frm="MB"))
    usemem = (300, "MB")

    with limit(subfunc, memory=memlimit) as f:
        subfunc(memlimit, usemem)
