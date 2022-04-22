import platform
import sys


def supports(limit: str) -> bool:
    """Check if pynisher can enforce limits on processes

    Parameters
    ----------
    limit: "walltime" | "cputime" | "memory"
        The kind of limit to check support for

    Returns
    -------
    bool
        Whether it is supported or not
    """
    mapping = {
        "walltime": supports_walltime,
        "cputime": supports_cputime,
        "memory": supports_memory,
    }
    func = mapping.get(limit.lower(), None)
    if func is not None:
        return func()
    else:
        raise ValueError(f"Not a know limit, must be one of {list(mapping.keys())}")


def supports_walltime() -> bool:
    """Check if wall time is supported on this system

    * Linux - Yes
    * Darwin - Yes
    * Windows - Yes if Python version > 3.7
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        # Sure, should work
        return True
    elif plat.startswith("darwin"):
        # Yup, also works
        return True
    elif plat.startswith("win"):
        # We don't have a way to do this yet for Python 3.7
        # Weird boolean syntax is because equality of version for >= seems to not work
        return not sys.version_info < (3, 8)
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")
        raise NotImplementedError(f"Unknown system {platform.platform()}")


def supports_cputime() -> bool:
    """Check if cpu time is supported on this system

    * Linux - Yes
    * Darwin - Yes
    * Windows - No

    Returns
    -------
    bool
        Whether it's supported or not
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        # Sure, should work
        return True
    elif plat.startswith("darwin"):
        # Yup, also works
        return True
    elif plat.startswith("win"):
        # We don't have a way to do this yet
        return False
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")


def supports_memory() -> bool:
    """Check if memory limit is supported on this system

    * Linux - Yes
    * Darwin - No
    * Windows - If `pywin32` installed correctly

    Returns
    -------
    bool
        Whether it's supported or not
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        # Sure, should work
        return True

    elif plat.startswith("darwin"):
        # Can't limit memory on Mac
        return False

    elif plat.startswith("win"):
        # Only supported if we can successfuly import `pywin32` modules
        try:
            import win32api  # noqa

            return True
        except Exception:
            return False
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")
