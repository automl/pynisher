Pynisher is a library to limit resources during the running of synchronous functions.

## Quick Overview

Limit the time a process can take
```python
from pynisher import Pynisher, limit, TimeoutException, MemoryLimitException

def sleepy(x: int) -> int:
    time.sleep(x)
    return x

# You can also use `cpu_time` instead
with Pynisher(sleepy, wall_time=7) as restricted_sleep:
    x = restricted_sleep(10)  # Will raise a TimeoutException
```

Limit the memory usage in a sequential manner
```python
def train_memory_hungry_model(X, y) -> Model:
    # ... do some thing
    return Model

model_trainer = Pynisher(
    train_memory_hungry_model,
    name="Name for the process",
    memory=(500, "MB"),
    wall_time=60*60  # 1hr
)

try:
    model = model_trainer(X, y)
except MemoryLimitException:
    model = None
```

You can even use the decorator, in which case it will always be done.
Passing `raises=False` means it will hide all errors and just return `None`.
```python
@limit(wall_time=1, raises=False)
def notify_remote_server() -> Response:
    """We don't care that this fails, just give it a second to try"""
    server = block_until_access(...)
    response = server.notify()
    return response

# ... do something
if (response := notify_remote_server()):
    log(response)

# ... something else
if (response := notify_remote_server()):
   log(response)
# ...
```

## Details
Pynisher works by running your function inside of a subprocess.
Once in the subprocess, the resources will be limited and the function ran!

Currently we mainly support Linux with partial support for Mac:

| OS      | `wall_time`        | `cpu_time`         | `memory`                                       |
| --      | -----------        | ----------         | --------                                       |
| Linux   | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark:                             |
| Mac     | :heavy_check_mark: | :heavy_check_mark: | :grey_question: (New MacOS doesn't support it) |
| Windows | :x:                | :x:                | :x:                                            |


It's important to note that the spawned subprocess will consume some initial amount of memory,
before any limits are placed. When this initial amount is above your `memory` limit, we
will print a warning and likely your function will crash shortly after.

The full list of options available with both `Pynisher` and `@limit` are:
```python

# The name given to the multiprocessing.Process
name: str | None = None

# The memory limit to place. Specify the amount of bytes or (int, unit) where unit
# can be "B", "KB", "MB" or "GB"
memory: int | tuple[int, str] | None = None

# The cpu time in seconds to limit the process to. This time is only counter while the
# process is active
cpu_time: int | None = None

# The wall time in seconds to limit the process to
wall_time: int | None = None

# This is some extra time added to the CPU time limit to enable proper cleanup
grace_period: int = 1

# This is the multiprocess context used, please refer to their documentation
context: "fork" | "spawn" | "forkserver" | None = "fork"
```

## Missing from v0.6.0
For simplicity, pynisher will no longer try to control `stdout`, `stderr`, instead end users
can use the builtins `redirect_stdout` and `redirect_stderr` of Python to send things as needed.

```python
from contextlib import redirect_stdout, redirect_stderr
import os

# Send everything to a files
with open("stdout.txt", "w") as out, open("stdout.txt", "w") as err:
    with redirect_stdout(out), redirect_stderr(err):
        run_restricted_function()

# Just send everything to the void
with open(os.devnull, "w") as devnull:
    with redirect_stdout(devnull), redirect_stderr(devnull):
        run_restricted_function()
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

## Project origin
This repository is based on Stefan Falkner's https://github.com/sfalkner/pynisher.
