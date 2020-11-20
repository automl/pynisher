=====
Usage
=====

The pynisher is a little module intended to limit a functions resources.
It starts a new process, sets the desired limits, and executes the
function inside it. In the end, it returns the function return value.
If, for any reason, the function call is not successful, None is returned.

Currently, the total memory usage(*), wall and cpu time, and the number of subprocesses can be limited.


(*) As the subprocess also includes the Python interpreter, the actual memory available to your function is less than the specified value.

To show the basic usage, consider the following script

.. code-block:: python

    import pynisher
    import time

    # using it as a decorator for every call to this function
    @pynisher.enforce_limits(wall_time_in_s=2)
    def my_function (t):
        time.sleep(t)
        return(t)

    for t in range(5):
        print(my_function(t))

The full list of argments to enforce_limits reads:

.. code-block:: python

    pynisher.enforce_limits(
        mem_in_mb=None, cpu_time_in_s=None,
        wall_time_in_s=None, num_processes=None,
        grace_period_in_s=None, logger=None,
        capture_output=False, context=None)

The first four are actual constraints on the memory, the CPU time, the wall time, and the
number of subprocesses of the function. All values should be integers or None, which means
no restriction.

The grace period allows the function to properly end. More technically, the subprocess receives
a SIGXCPU/SIGALARM signal if the CPU/wall clock limit is reached. After the grace period a
SIGKILL is send terminating the process immediately. Without a grace period, pynisher might
not be able to correctly determine the cause of the shutdown, as the subprocess might die without
any notice (more on that below).

The logger is used to display additional information about the status of the pynisher module
(mostly debug level). This might come in handy while debugging.

If you need to know what happend to the function call or why it was aborted,
you can use the object returned from pynisher.enforce_limits. Consider this
slight variation of the above example:

.. code-block:: python

    import pynisher
    import time

    def my_function (t):
        print("Going to sleep for %f seconds" % t)
        time.sleep(t)
        return(t)

    for t in range(5):
        obj = pynisher.enforce_limits(wall_time_in_s=2, capture_output=True)(my_function)
        result = obj(t)
        print(
            result, obj.result, obj.exit_status, obj.wall_clock_time,
            obj.stdout, obj.stderr, obj.exitcode,
        )


The object ```obj``` can be used as the original function. After calling it, it contains
the actual result, but also an indicator of what happend. The ```exit_status``` attribute
is either zero (function returned properly) or one of the following exceptions:

.. code-block:: python

    pynisher.CpuTimeoutException	# CPU time limit was reached
    pynisher.TimeoutException	    # Wall clock time limit exceeded
    pynisher.MemorylimitException	# function hit the memory constraint
    pynisher.SubprocessException	# OSError in the subprocess, check the field obj.os_errno
    pynisher.PynisherError          # An internal error - this should not happen
    pynisher.SignalException        # pynisher caught a signal
    pynisher.AnythingException	    # Something else went wrong, e.g., your function received a signal and just died.

Here, the above issue about the grace period becomes interesting. Without it, it is likely that
a AnythingException is returned where a Cpu-/TimeoutException would be appropriate. The ``exitcode``
is the exitcode returned by the subprocess, see `multiprocessing.Process.exitcode <https://docs
.python.org/3/library/multiprocessing.html#multiprocessing.Process.exitcode>`_

Finally, see `Pynisher and Multithreading`_ for the use of the ``context`` argument.

=====
Other
=====

Pynisher and Multithreading
===========================

When the Pynisher is used together with the Python Threading library, it is possible to run into
a deadlock when using the standard ``fork`` method to start new processes as described in

* https://github.com/Delgan/loguru/issues/231
* https://gist.github.com/mfm24/e62ec5d50c672524107ca00a391e6104
* https://github.com/dask/dask/issues/3759

One way of solving this would be to change the forking behavior as described
`here <https://github.com/google/python-atfork/blob/main/atfork/stdlib_fixer.py>`_, but this is
also makes very strong assumptions on how the code is executed. An alternative is passing a
`Context <https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods>`_
which uses either ``spawn`` or ``forkserver`` as the process startup method.

Project origin
==============

This repository is based on Stefan Falkner's https://github.com/sfalkner/pynisher.
