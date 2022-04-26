Pynisher is a library to limit resources during the running of synchronous functions.

## Quick Overview

Limit the time a process can take
```python
from pynisher import Pynisher


def sleepy(x: int) -> int:
    time.sleep(x)
    return x

# You can also use `cpu_time` instead
with Pynisher(sleepy, wall_time=7) as restricted_sleep:
    x = restricted_sleep(10)  # Will raise a TimeoutException
```

Limit the memory usage in a sequential manner
```python
from pynisher import Pynisher, MemoryLimitException


def train_memory_hungry_model(X, y) -> Model:
    # ... do some thing
    return Model

model_trainer = Pynisher(
    train_memory_hungry_model,
    name="Name for the process",
    memory=(500, "MB"),
    wall_time=(1.5, "h")  # 1h30m
)

try:
    model = model_trainer(X, y)
except (WallTimeoutException, MemoryLimitException):
    model = None
```

Passing `raises=False` means it will hide all errors and will return `EMPTY` if
there is no result to give back.

```
def f():
    raise ValueError()

rf = Pynisher(f, wall_time=(2, "m"), raises=False)
result = rf()

if result is not EMPTY:
    # ...
```


You can even use the decorator, in which case it will always be limited.
Please note in [Details](#details) that support for this is limited and mostly
for Linux.
```python
from pynisher import limit, EMPTY


@limit(wall_time=1, raises=False)
def notify_remote_server() -> Response:
    """We don't care that this fails, just give it a second to try"""
    server = block_until_access(...)
    response = server.notify()
    return response

if (response := notify_remote_server()) is not EMPTY:
    # ... do something
```

You can safely raise errors from inside your function and the same kind of error will be reraised
with a traceback.
```python
from pynisher import Pynisher


def f():
    raise MyCustomException()

rf = Pynisher(f)

try:
    rf()
except MyCustomException as e:
    ... # do what you need
```

## Details
Pynisher works by running your function inside of a subprocess.
Once in the subprocess, the resources will be limited for that process before running your
function. The methods for limiting specific resources can be found within the respective
`pynisher/limiters/<platform>.py`.

#### Features
To check what if a feature is supported on your system:
```python
from pynisher import supports


for limit in ["cputime", "walltime", "memory", "decorator"]:
    print(f"Supports {limit} - {supports(limit)}")
```

You can also do using `Pynisher`
```python
from pynisher import Pynisher

print(Pynisher.supports("walltime"))


restricted_func = Pynisher(f, ...)
if not restricted_func.supports("memory"):
    ...
```

Currently we mainly support Linux with partial support for Mac and Windows:

| OS      | `wall_time`        | `cpu_time`              | `memory`                | `@limit`           |
| --      | -----------        | ----------              | --------                | --------           |
| Linux   | :heavy_check_mark: | :heavy_check_mark:      | :heavy_check_mark:      | :heavy_check_mark: |
| Windows | :heavy_check_mark: | :heavy_check_mark: (1.) | :heavy_check_mark: (1.) | :x:  (3.)          |
| Mac     | :heavy_check_mark: | :heavy_check_mark:      | :x: (2.)                | :x:  (3.)          |

1. Limiting memory and cputime on Windows is done with the library `pywin32`. There seems
to be installation issues when instead of using `conda install <x>`, you use `pip install <x>`
inside a conda environment, specifically only with `Python 3.8` and `Python 3.9`.
The workaround is to instead install `pywin32` with conda, which can be done with
`pip uninstall pywin32; conda install pywin32`.
Please see this [issue](https://github.com/mhammond/pywin32/issues/1865) for updates.

2. Mac doesn't seem to allow for limiting a processes memory. No workaround has been found
including trying `launchctl` which seems global and ignores memory limiting. Possibly `ulimit`
could work but needs to be tested. Using `setrlimit(RLIMIT_AS, (soft, hard))` does nothing
and will either fail explicitly or silently, hence we advertise it is not supported.
However, passing a memory limit on mac is still possible but may not do anything useful or
even raise an error.

3. This is something due to how multiprocessing pickling protocols work, hence `@limit(...)` does
not work for your Mac/Windows. Please use the `Pynisher` method of limiting resources in this case.
(Technically this is supported for Mac Python 3.7 though). This is likely due to the default
`spawn` context for Windows and Mac but using other available methods on Mac also seems to not work.
For Linux, the `fork` and `forkserver` context seems to work.


#### Parameters
The full list of options available with both `Pynisher` and `@limit` are:
```python
def __init__(
    name: str | None = None,
    memory: int | tuple[int, str] | None = None,
    cpu_time: int | tuple[float, str] | None = None,
    wall_time: int | |tuple[float, str] | None = None,
    grace_period: int = 1,
    context: str | None = None,
    raises: bool = True,
    warnings: bool = True,
)

# The name given to the multiprocessing.Process
name: str | None = None

# The memory limit to place. Specify the amount of bytes or (int, unit) where unit
# can be "B", "KB", "MB" or "GB"
memory: int | tuple[int, str] | None = None

# The cpu time in seconds to limit the process to. This time is only counted while the
# process is active.
# Can provide in (time, units) such as (1.5, "h") to indicate one and a half hours.
# Units available are "s", "m", "h"
cpu_time: int | tuple[float, str] | None = None

# The wall time in seconds to limit the process to
# Can provide in (time, units) such as (1.5, "h") to indicate one and a half hours.
# Units available are "s", "m", "h"
wall_time: int | tuple[float, str] | None = None

# Whether to throw any errors that occured in the subprocess to silently
# throw them away. If `True` and an Error was raised, `None` will be returned.
# The errors raised in the subprocess will be the same type that are raised in
# the controlling process. The exception to this are MemoryErrors which occur
# in the subprocess, we convert these to MemoryLimitException.
raises: bool = True

# This is some extra time added to the CPU time limit to enable proper cleanup
# This has no effect on Windows as there is no graceful cleanup possible
grace_period: int = 1

# This is the multiprocess context used, please refer to their documentation
# https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
context: "fork" | "spawn" | "forkserver" | None = None


# Whether to emit warnings form Pynisher or not. The current warnings:
# * When the memory limit is lower than the starting memory of a process
# * When trying to remove the memory limit for sending back information
#   from the subprocess to the main process
warnings: bool = True
```

#### Exceptions
Pynisher will let all subprocess `Exceptions` buble up to the controlling process.
If a subprocess exceeds a limit one of `CpuTimeoutException`, `WallTimeoutException` or `MemoryLimitException` are raised, but you can use their base classes to cover them more generally.

```python
class PynisherException(Exception): ...
    """When a subprocess exceeds a limit"""

class TimeoutException(PynisherException): ...
    """When a subprocess exceeds a time limit (walltime or cputime)"""

class CpuTimeoutException(TimeoutException): ...
    """When a subprocess exceeds its cpu time limit"""

class WallTimeoutException(TimeoutException):
    """When a subprocess exceeds its wall time limit"""

class MemoryLimitException(PynisherException, MemoryError):
    """When a subprocess tries to allocate memory that would take it over the limit

    This also inherits from MemoryError as it is technically a MemoryError that we
    catch and convert.
    """
```

## Changes from v0.6.0
For simplicity, pynisher will no longer try to control `stdout`, `stderr`, instead
users can use the builtins `redirect_stdout` and `redirect_stderr` of Python to
send things as needed.

Pynisher issues warnings through `stderr`. Depending on how you set up the `context`
to spawn a new process, using objects may now work as intended. The safest option
is to write to a file if needed.

```python
from contextlib import redirect_stderr

# You can always disable warnings from Pynisher
restricted_func = Pynisher(func, warnings=False)

# Capture warnings in a file
# Only seems to work properly on Linux
with open("stderr.txt", "w") as stderr, redirect_stderr(stderr):
    restricted_func()

with open("stderr.txt", "r") as stderr:
    print(stderr.readlines())
```

The support for passing a `logger` to `Pynisher` has also been removed. The only diagnostics
information that would have been sent to the logger is not communicated with prints to `stderr`.
These diagnostic messages only occur when an attempt to limit resources failed
This can be captured or disabled as above.

Any other kind of issue will raise an exception with relevant information.

The support for checking `exit_status` was removed and the success of a pynisher process can
be handled in the usual Python manner of checking for errors, with a `try: except:`. If you
don't care for the `exit_status` then use `f = Pynisher(func, raises=False)` and you can
check for output `output = f(...)`. This will be `None` if an error was raised and was `raises=False`.

Pynisher no longer times your function for you with `self.wall_clock_time`. If you need to measure
the duration it ran, please do so outside of `Pynisher`.

The exceptions were also changed, please see [Exceptions][#Exceptions]

## Pynisher and Multithreading
When Pynisher is used together with the Python Threading library, it is possible to run into
a deadlock when using the standard ``fork`` method to start new processes as described in

* https://github.com/Delgan/loguru/issues/231
* https://gist.github.com/mfm24/e62ec5d50c672524107ca00a391e6104
* https://github.com/dask/dask/issues/3759

One way of solving this would be to change the forking behavior as described
`here <https://github.com/google/python-atfork/blob/main/atfork/stdlib_fixer.py>`_, but this is
also makes very strong assumptions on how the code is executed. An alternative is passing a
`Context <https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods>`_
which uses either ``spawn`` or ``forkserver`` as the process startup method.

## Project origin
This repository is based on Stefan Falkner's https://github.com/sfalkner/pynisher.
