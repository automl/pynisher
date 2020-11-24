#! /bin/python
import resource
import signal
import multiprocessing
import os
import sys
import time
import tempfile

import psutil


class CpuTimeoutException(Exception):
    """Pynisher exception object returned on a CPU time limit."""
    pass


class TimeoutException(Exception):
    """Pynisher exception object returned when hitting the time limit."""
    pass


class MemorylimitException(Exception):
    """Pynisher exception object returned when hitting the memory limit."""
    pass


class SubprocessException(Exception):
    """Pynisher exception object returned when receiving an OSError while
    executing the subprocess."""
    pass


class PynisherError(Exception):
    """Pynisher exception object returned in case of an internal error.

    This should not happen, please open an issue at github.com/automl/pynisher
    if you run into this."""
    pass


class SignalException(Exception):
    """Pynisher exception object returned in case of a signal being handled by
    the pynisher"""
    pass


class AnythingException(Exception):
    """Pynisher exception object returned if the function call closed
    prematurely and no cause can be determined.

    In this case, the stdout and stderr can contain helpful debug information.
    """
    pass


# create the function the subprocess can execute
def subprocess_func(func, pipe, logger, mem_in_mb, cpu_time_limit_in_s, wall_time_limit_in_s, num_procs,
                    grace_period_in_s, tmp_dir, *args, **kwargs):
    # simple signal handler to catch the signals for time limits
    def handler(signum, frame):
        # logs message with level debug on this logger
        logger.debug("signal handler: %i" % signum)
        if (signum == signal.SIGXCPU):
            # when process reaches soft limit --> a SIGXCPU signal is sent (it normally terminats the process)
            raise (CpuTimeoutException)
        elif (signum == signal.SIGALRM):
            # SIGALRM is sent to process when the specified time limit to an alarm function elapses (when real or clock time elapses)
            logger.debug("timeout")
            raise (TimeoutException)
        else:
            logger.debug("other: %d", signum)
            raise SignalException

    # temporary directory to store stdout and stderr
    if tmp_dir is not None:
        logger.debug(
            'Redirecting output of the function to files. Access them via the stdout and stderr attributes of the wrapped function.')

        stdout = open(os.path.join(tmp_dir, 'std.out'), 'a', buffering=1)
        sys.stdout = stdout

        stderr = open(os.path.join(tmp_dir, 'std.err'), 'a', buffering=1)
        sys.stderr = stderr

    # catching all signals at this point turned out to interfer with the subprocess (e.g. using ROS)
    signal.signal(signal.SIGALRM, handler)
    signal.signal(signal.SIGXCPU, handler)
    signal.signal(signal.SIGQUIT, handler)

    # code to catch EVERY catchable signal (even X11 related ones ... )
    # only use for debugging/testing as this seems to be too intrusive.
    """
    for i in [x for x in dir(signal) if x.startswith("SIG")]:
        try:
            signum = getattr(signal,i)
            print("register {}, {}".format(signum, i))
            signal.signal(signum, handler)
        except:
            print("Skipping %s"%i)
    """

    # set the memory limit
    if mem_in_mb is not None:
        # byte --> megabyte
        mem_in_b = mem_in_mb * 1024 * 1024
        # the maximum area (in bytes) of address space which may be taken by the process.
        resource.setrlimit(resource.RLIMIT_AS, (mem_in_b, mem_in_b))

    # for now: don't allow the function to spawn subprocesses itself.
    # resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
    # Turns out, this is quite restrictive, so we don't use this option by default
    if num_procs is not None:
        resource.setrlimit(resource.RLIMIT_NPROC, (num_procs, num_procs))

    # schedule an alarm in specified number of seconds
    if wall_time_limit_in_s is not None:
        signal.alarm(wall_time_limit_in_s)

    if cpu_time_limit_in_s is not None:
        # From the Linux man page:
        # When the process reaches the soft limit, it is sent a SIGXCPU signal.
        # The default action for this signal is to terminate the process.
        # However, the signal can be caught, and the handler can return control
        # to the main program. If the process continues to consume CPU time,
        # it will be sent SIGXCPU once per second until the hard limit is reached,
        # at which time it is sent SIGKILL.
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_time_limit_in_s, cpu_time_limit_in_s + grace_period_in_s))

    # the actual function call
    try:
        logger.debug("call function")
        return_value = ((func(*args, **kwargs), 0))
        logger.debug("function returned properly: {}".format(return_value))
    except MemoryError:
        return_value = (None, MemorylimitException)

    except OSError as e:
        return_value = (None, SubprocessException, e.errno)

    except CpuTimeoutException:
        return_value = (None, CpuTimeoutException)

    except TimeoutException:
        return_value = (None, TimeoutException)

    except SignalException:
        return_value = (None, SignalException)

    finally:
        try:
            logger.debug("return value: {}".format(return_value))

            pipe.send(return_value)
            pipe.close()

        except: # noqa
            # this part should only fail if the parent process is alread dead, so there is not much to do anymore :)
            pass
        finally:
            # recursively kill all children
            p = psutil.Process()
            for child in p.children(recursive=True):
                child.kill()


class enforce_limits(object):
    def __init__(self, mem_in_mb=None, cpu_time_in_s=None, wall_time_in_s=None, num_processes=None,
                 grace_period_in_s=None, logger=None, capture_output=False, context=None):

        if context is None:
            self.context = multiprocessing.get_context()
        else:
            self.context = context

        self.mem_in_mb = mem_in_mb
        self.cpu_time_in_s = cpu_time_in_s
        self.num_processes = num_processes
        self.wall_time_in_s = wall_time_in_s
        self.grace_period_in_s = 0 if grace_period_in_s is None else grace_period_in_s
        self.logger = logger if logger is not None else self.context.get_logger()
        self.capture_output = capture_output

        if self.mem_in_mb is not None:
            self.logger.debug("Restricting your function to {} mb memory.".format(self.mem_in_mb))
        if self.cpu_time_in_s is not None:
            self.logger.debug("Restricting your function to {} seconds cpu time.".format(self.cpu_time_in_s))
        if self.wall_time_in_s is not None:
            self.logger.debug("Restricting your function to {} seconds wall time.".format(self.wall_time_in_s))
        if self.num_processes is not None:
            self.logger.debug("Restricting your function to {} threads/processes.".format(self.num_processes))
        if self.grace_period_in_s is not None:
            self.logger.debug("Allowing a grace period of {} seconds.".format(self.grace_period_in_s))

    def __call__(self, func):

        class function_wrapper(object):
            def __init__(self2, func):
                self2.func = func
                self2._reset_attributes()

            def _reset_attributes(self2):
                self2.result = None
                self2.exit_status = None
                self2.resources_function = None
                self2.resources_pynisher = None
                self2.wall_clock_time = None
                self2.stdout = None
                self2.stderr = None

            def __call__(self2, *args, **kwargs):

                self2._reset_attributes()

                # create a pipe to retrieve the return value
                parent_conn, child_conn = self.context.Pipe(False)
                # import pdb; pdb.set_trace()

                if self.capture_output:
                    tmp_dir = tempfile.TemporaryDirectory()
                    tmp_dir_name = tmp_dir.name

                else:
                    tmp_dir_name = None

                # create and start the process
                subproc = self.context.Process(
                    target=subprocess_func,
                    name="pynisher function call",
                    args=(
                        self2.func,
                        child_conn,
                        self.logger,
                        self.mem_in_mb,
                        self.cpu_time_in_s,
                        self.wall_time_in_s,
                        self.num_processes,
                        self.grace_period_in_s,
                        tmp_dir_name
                    ) + args,
                    kwargs=kwargs,
                )
                self.logger.debug("Function called with argument: {}, {}".format(args, kwargs))

                # start the process

                start = time.time()
                subproc.start()
                child_conn.close()

                try:
                    def read_connection():
                        connection_output = parent_conn.recv()
                        if len(connection_output) == 2:
                            self2.result, self2.exit_status = connection_output
                        elif len(connection_output) == 3:
                            self2.result, self2.exit_status, self2.os_errno = connection_output
                        else:
                            self2.result, self2.exit_status = (None, PynisherError)

                    # read the return value
                    if (self.wall_time_in_s is not None):
                        if parent_conn.poll(self.wall_time_in_s + self.grace_period_in_s):
                            read_connection()
                        else:
                            subproc.terminate()
                            self2.exit_status = TimeoutException

                    else:
                        read_connection()

                except EOFError:  # Don't see that in the unit tests :(
                    self.logger.debug(
                        "Your function call closed the pipe prematurely -> Subprocess probably got an uncatchable signal.")
                    self2.exit_status = AnythingException

                except: # noqa
                    self.logger.debug("Something else went wrong, sorry.")
                finally:
                    self2.resources_function = resource.getrusage(resource.RUSAGE_CHILDREN)
                    self2.resources_pynisher = resource.getrusage(resource.RUSAGE_SELF)
                    self2.wall_clock_time = time.time() - start
                    self2.exit_status = 5 if self2.exit_status is None else self2.exit_status

                    # recover stdout and stderr if requested
                    if self.capture_output:
                        with open(os.path.join(tmp_dir.name, 'std.out'), 'r') as fh:
                            self2.stdout = fh.read()
                        with open(os.path.join(tmp_dir.name, 'std.err'), 'r') as fh:
                            self2.stderr = fh.read()

                        tmp_dir.cleanup()

                    # don't leave zombies behind
                    subproc.join()
                    # exitcode is only available after join
                    self2.exitcode = subproc.exitcode
                return (self2.result)

        return (function_wrapper(func))
