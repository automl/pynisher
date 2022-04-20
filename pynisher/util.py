from __future__ import annotations

from psutil import Process

_unit_table = {
    "B": 1,
    "KB": 2**10,
    "MB": 2**20,
    "GB": 2**30,
}


def memconvert(x: float, *, frm: str = "B", to: str = "B") -> float:
    """Convert between units, assumes input is in bytes and assumes output is bytes

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
    u_from = _unit_table[frm.upper()]
    u_to = _unit_table[to.upper()]

    as_bytes = x * u_from
    as_target = as_bytes / u_to

    # We can't see a use case for float Bytes
    if to.upper() == "B":
        return int(as_target)
    else:
        return as_target


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
