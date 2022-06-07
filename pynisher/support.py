from __future__ import annotations

import platform
import sys
from functools import lru_cache

if sys.platform.lower().startswith("win"):
    contexts = ["spawn"]
else:
    contexts = ["fork", "spawn", "forkserver"]


@lru_cache(maxsize=None)
def _has_pywin32() -> bool:
    """Check if system has pywin32 accessible"""
    try:
        import win32api  # noqa

        return True
    except Exception:
        return False


def supports(limit: str) -> bool:
    """Check if pynisher supports a given feature

    Parameters
    ----------
    limit: "wall_time" | "cpu_time" | "memory" | "decorator"
        The kind of feature to check support for

    Returns
    -------
    bool
        Whether it is supported or not
    """
    mapping = {
        "wall_time": supports_walltime,
        "cpu_time": supports_cputime,
        "memory": supports_memory,
        "decorator": supports_limit_decorator,
    }
    func = mapping.get(limit.lower(), None)
    if func is not None:
        return func()
    else:
        raise ValueError(f"Not a known feature, must be one of {list(mapping.keys())}")


def supports_walltime() -> bool:
    """Check if wall time is supported on this system

    Check respective "pynisher/limiters/<platform>.py"

    Returns
    -------
    bool
        Whether it's supported or not
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        return True
    elif plat.startswith("darwin"):
        return True
    elif plat.startswith("win"):
        return True
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")


def supports_cputime() -> bool:
    """Check if cpu time is supported on this system

    Returns
    -------
    bool
        Whether it's supported or not
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        return True
    elif plat.startswith("darwin"):
        return True
    elif plat.startswith("win"):
        return _has_pywin32()
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")


def supports_memory() -> bool:
    """Check if memory limit is supported on this system

    * Linux - Yes
    * Darwin - No
    * Windows - If `pywin32` installed correctly

    Check respective "pynisher/limiters/<platform>.py"

    Returns
    -------
    bool
        Whether it's supported or not
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        return True
    elif plat.startswith("darwin"):
        return False
    elif plat.startswith("win"):
        return _has_pywin32()
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")


def supports_limit_decorator() -> bool:
    """Whether using the decorator @restricted is supported

    Check `pynisher::restricted` for why

    Returns
    -------
    bool
        Whether using @restricted is supported
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        return True
    elif plat.startswith("darwin"):
        return False
    elif plat.startswith("win"):
        return False
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")
