Pynisher is a library to limit resources of a function call in a synchronous manner.
You can use this to ensure that your function doesn't use up more resources than it
should.

## Usage

Limit the time a process can take
```python
import pynisher


def sleepy(x: int) -> int:
    time.sleep(x)
    return x

# You can also use `cpu_time` instead
with pynisher.limit(sleepy, wall_time=7) as limited_sleep:
    x = limited_sleep(10)  # Will raise a TimeoutException
```

Limit the memory usage in a sequential manner
```python
from pynisher import limit, MemoryLimitException, WallTimeoutException


def train_memory_hungry_model(X, y) -> Model:
    # ... do some thing
    return model

model_trainer = limit(
    train_memory_hungry_model,
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

```python
from pynisher import limit, EMPTY

def f():
    raise ValueError()

limited_f = limit(f, wall_time=(2, "m"), raises=False)
result = limited_f()

if result is not EMPTY:
    # ...
```


You can even use the decorator, in which case it will always be limited.
Please note in [Details](#details) that support for this is limited and mostly
for Linux.
```python
from pynisher import restricted

@restricted(wall_time=1, raises=False)
def notify_remote_server() -> Response:
    """We don't care that this fails, just give it a second to try"""
    server = block_until_access(...)
    response = server.notify()

notify_remote_server()
# ... continue on even if it failed
```

You can safely raise errors from inside your function and the same kind of error will be reraised
with a traceback.
```python
from pynisher import limit


def f():
    raise ValueError()

limited_f = limit(f)

try:
    limited_f()
except ValueError as e:
    ... # do what you need
```

If returning very large items, prefer to save them to file first and then read the result as
sending large objects through pipes can be very slow.

```python
from pathlib import Path
import pickle

from pynisher import limit

def train_gpt3(save_path: Path) -> bool:
    gpt3 = ...
    gpt3.train()
    with save_path.open('wb') as f:
        pickle.dump(gpt3, f)

    return True

path = Path('gpt3.model')
trainer = limit(train_gpt3, memory=(1_000_000, "gb")):

try:
    trainer(save_path=path)

    with path.open("rb") as f:
        gpt3 = pickle.load(f)

except MemoryLimitException as e:
    ...
```


## Details
Pynisher works by running your function inside of a subprocess.
Once in the subprocess, the resources will be limited for that process before running your
function. The methods for limiting specific resources can be found within the respective
`pynisher/limiters/<platform>.py`.

#### Features
To check if a feature is supported on your system:
```python
from pynisher import limit


for limit in ["cpu_time", "wall_time", "memory", "decorator"]:
    print(f"Supports {limit} - {supports(limit)}")


limited_f = limit(f, ...)
if not limited_f.supports("memory"):
    ...
```

Currently we mainly support Linux with partial support for Mac and Windows:

| OS      | `wall_time`        | `cpu_time`              | `memory`                | `@restricted`      |
| --      | -----------        | ----------              | --------                | -------------      |
| Linux   | :heavy_check_mark: | :heavy_check_mark:      | :heavy_check_mark:      | :heavy_check_mark: |
| Windows | :heavy_check_mark: | :heavy_check_mark: (1.) | :heavy_check_mark: (1.) | :x:  (3.)          |
| Mac     | :heavy_check_mark: | :heavy_check_mark: (4.) | :x: (2.)                | :x:  (3.)          |

1. Limiting memory and cputime on Windows is done with the library `pywin32`. There seem
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
even raise an error. If you are aware of a solution, please let us know.

3. This is something due to how multiprocessing pickling protocols work, hence `@restricted(...)` does
not work for your Mac/Windows. Please use the `limit` method of limiting resources in this case.
(Technically this is supported for Mac Python 3.7 though). This is likely due to the default
`spawn` context for Windows and Mac but using other available methods on Mac also seems to not work.
For Linux, the `fork` and `forkserver` context seems to work.

4. For unknown reasons, using `time.process_time()` to query the cpu time usage within a pynished function
will cause the `cpu_time` limits to be ignored on Mac, leading to a function that will hang indefinitly
unless using some other limit. Please let us know if this is some known issue or any workarounds are
available.


#### Parameters
The full list of options available with both `limit` and `@restricted` are:
```python
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


# Whether to throw any errors that occured in the subprocess or to silently
# throw them away. If `True` and an Error was raised, `None` will be returned.
# The errors raised in the subprocess will be the same type that are raised in
# the controlling process. The exception to this are MemoryErrors which occur
# in the subprocess, we convert these to MemoryLimitException.
raises: bool = True


# This is the multiprocess context used, please refer to their documentation
# https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
context: "fork" | "spawn" | "forkserver" | BaseContext | None = None


# Whether to emit warnings from  limit or not. The current warnings:
# * When the memory limit is lower than the starting memory of a process
# * When trying to remove the memory limit for sending back information
#   from the subprocess to the main process
warnings: bool = True


# How to handle errors. If `bool` then this decides whether or not to wrap them in
# a pynisher exception. If `list`, you can specify which errors get wrapped in a
# pynisher exception and if `dict`, you can specify what kind of errors get wrapped
# and how. See `pynisher::Pynisher::__init__` for more details on `dict`
#
# * wrap_errors={ "memory": [ImportError, (OSError, 22)], "pynisher": [ValueError] }
#
# We check that the exception is explicitly of the same type and not just a subclass.
# This is to prevent accidentally wrapping to eagerly.
wrap_errors: bool | list[Exception] | dict = False


# Whether to terminate child processes of your limited function.
# By default, pynisher will kill any subprocesses your function may spawn. If this
# is not desired behaviour, please use `daemon=True` with your spawned subprocesses
# and set `terminate_child_processes` to `False`
terminate_child_processes: bool = True

# Whether keyboard interrupts should forceably kill any subprocess or the
# pynished function. If True, it will temrinate the process tree of
# the pynished function and then reraise the KeyboardInterrupt.
forceful_keyboard_interrupt: bool = True
```

#### Exceptions
Pynisher will let all subprocess `Exceptions` buble up to the controlling process.
If a subprocess exceeds a limit, one of `CpuTimeoutException`, `WallTimeoutException` or `MemoryLimitException` are raised, but you can use their base classes to cover them more generally.

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

# You can always disable warnings
limited_f = limit(func, warnings=False)

# Capture warnings in a file
# Only seems to work properly on Linux
with open("stderr.txt", "w") as stderr, redirect_stderr(stderr):
    limited_f()

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
don't care for the `exit_status` then use `f = limit(func, raises=False)` and you can
check for output `output = f(...)`. This will be `None` if an error was raised and was `raises=False`.

Pynisher no longer times your function for you with `self.wall_clock_time`. If you need to measure
the duration it ran, please do so outside of `Pynisher`.

The exceptions were also changed, please see [Exceptions](#Exceptions)

## Controlling namespace pollution
As an advanced use case, sometimes you might want to keep the modules imported for your
limited function to be local only, preventing this from leaking to the main process that
runs created the limited function. You have three ways to control that the locally imported
error does not pollute the main namespace.

```python
import sys
from pynisher import PynisherException, limit

def import_sklearn() -> None:
    """Imports sklearn into a local namespace and has an sklearn object in its args"""
    from sklearn.exceptions import NotFittedError
    from sklearn.svm import SVR

    assert "sklearn" in sys.modules.keys()
    raise NotFittedError(SVR())


if __name__ == "__main__":
    # Wrapping all errors
    lf = limit(import_sklearn, wrap_errors=True)
    try:
        lf()
    except PynisherException:
        assert "sklearn" not in sys.modules.keys()

    # Wrapping only specific errors
    lf = limit(import_sklearn, wrap_errors=["NotFittedError"])
    try:
        lf()
    except PynisherException:
        assert "sklearn" not in sys.modules.keys()

    # Wrapping that error specifically as a PynisherException
    lf = limit(import_sklearn, wrap_errors={"pynisher": ["NotFittedError"]})
    try:
        lf()
    except PynisherException:
        assert "sklearn" not in sys.modules.keys()
```


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


## Nested Pynisher and Multiprocessing contexts
Be careful when using multiple contexts for multiprocessing while using `pynisher`. If your
pynished function spawns subprocess using `"forkserver"` while you set `pynisher` to use
the context `"fork"`, then issues can begin to occur when terminate processes.

## Project origin
This repository is based on Stefan Falkner's https://github.com/sfalkner/pynisher.
