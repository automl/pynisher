import platform
import sys


def supports(limit: str) -> bool:
    """Check if pynisher supports a given feature

    Parameters
    ----------
    limit: "walltime" | "cputime" | "memory" | "decorator"
        The kind of feature to check support for

    Returns
    -------
    bool
        Whether it is supported or not
    """
    mapping = {
        "walltime": supports_walltime,
        "cputime": supports_cputime,
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

    * Linux - Yes
    * Darwin - Yes
    * Windows - Yes

    Check respective "pynisher/limiters/<platform>.py"

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
        # Yay, they all work
        return True
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")


def supports_cputime() -> bool:
    """Check if cpu time is supported on this system

    * Linux - Yes
    * Darwin - Yes
    * Windows - No

    Check respective "pynisher/limiters/<platform>.py"

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

    Check respective "pynisher/limiters/<platform>.py"

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


def supports_limit_decorator() -> bool:
    """Whether using the decorator @limit is supported

    * Linx - Yes
    * Mac - Only with Python 3.7
    * Windows - No

    Check `pynisher::limit` for why

    Returns
    -------
    bool
        Whether using @limit is supported
    """
    plat = sys.platform.lower()
    if plat.startswith("linux"):
        return True
    elif plat.startswith("darwin"):
        return sys.version_info < (3, 8)
    elif plat.startswith("win"):
        return False
    else:
        raise NotImplementedError(f"Unknown system {platform.platform()}")
