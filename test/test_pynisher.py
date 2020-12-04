#! /bin/python
import logging
import multiprocessing
import os
import pytest
import signal
import time
import unittest
import unittest.mock

import psutil

import pynisher

logger = multiprocessing.log_to_stderr()
logger.setLevel(logging.WARNING)


# TODO: add tests with large return value to test for deadlock!

# Functions below have to be at the top of the file to be pick-able
# for multiprocessing

def rogue_subprocess():
    pid = os.getpid()
    oldgrp = os.getpgrp()
    os.setpgrp()
    logger.debug("{}: Changed group id from {} to {}".format(pid, oldgrp, os.getpgrp()))
    time.sleep(60)


def spawn_rogue_subprocess(num_procs=5):
    for i in range(num_procs):
        p = multiprocessing.Process(target=rogue_subprocess, daemon=False)
        p.start()
    p = psutil.Process()
    time.sleep(10)


def simulate_work(size_in_mb, wall_time_in_s, num_processes, **kwargs):
    # allocate memory (size_in_mb) with an array
    # note the actual size in memory of this process is a little bit larger
    A = [42.] * ((1024 * size_in_mb) // 8) # noqa

    # try to spawn new processes
    if (num_processes > 0):
        # data parallelism
        multiprocessing.Pool(num_processes)

    # sleep for specified duration
    time.sleep(wall_time_in_s + 1)
    return (size_in_mb, wall_time_in_s, num_processes)


def svm_example(n_samples=10000, n_features=100):
    from sklearn.svm import SVR
    from sklearn.datasets import make_regression

    X, Y = make_regression(n_samples, n_features)
    m = SVR()

    m.fit(X, Y)


def svc_example(n_samples=10000, n_features=4):
    from sklearn.svm import SVC
    from sklearn.datasets import make_classification

    X, Y = make_classification(n_samples, n_features)
    # pp = PolynomialFeatures(degree=3)

    # X = pp.fit_transform(X)
    m = SVC()
    m.fit(X, Y)


def crash_unexpectedly(signum):
    print("going to receive signal {}.".format(signum))
    pid = os.getpid()
    time.sleep(1)
    os.kill(pid, signum)
    time.sleep(1)


def crash_with_exception(exception):
    print("going to raise {}.".format(exception))
    raise exception


def crash_while_read_file():
    with open('some_non_existing_files_to_cause_crash'):
        pass


def return_big_array(num_elements):
    return ([1] * num_elements)


def cpu_usage():
    i = 1
    while True:
        i += 1


def print_and_sleep(t):
    for i in range(t):
        print(i)
        time.sleep(1)


def print_and_fail():
    print(0)
    raise RuntimeError()


def nested_pynisher(level=2, cputime=5, walltime=5, memlimit=10e24,
                    increment=-1, grace_period=1, context=None):
    print("this is level {}".format(level))
    if level == 0:
        spawn_rogue_subprocess(10)
    else:
        func = pynisher.enforce_limits(
            mem_in_mb=memlimit, cpu_time_in_s=cputime,
            wall_time_in_s=walltime,
            grace_period_in_s=grace_period,
            context=context,
        )(nested_pynisher)
        func(level=level - 1,
             cputime=None,
             walltime=walltime + increment,
             memlimit=memlimit,
             increment=increment,
             context=context,
             )


@pytest.mark.parametrize("context", ['fork', 'spawn', 'forkserver'])
class TestLimitResources:
    @pytest.mark.parametrize("memory", [1, 2, 4, 8, 16])
    def test_success(self, context, memory):

        print("Testing unbounded function call which have to run through!")
        local_mem_in_mb = None
        local_wall_time_in_s = None
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=local_mem_in_mb,
            wall_time_in_s=local_wall_time_in_s,
            cpu_time_in_s=local_cpu_time_in_s,
            grace_period_in_s=local_grace_period,
            context=multiprocessing.get_context(context),
        )(simulate_work)

        assert (memory, 0, 0) == wrapped_function(memory, 0, 0)
        assert wrapped_function.exit_status == 0
        assert wrapped_function.exitcode == 0

    @pytest.mark.parametrize("memory", [1024, 2048, 4096])
    def test_out_of_memory(self, context, memory):
        print("Testing memory constraint.")
        local_mem_in_mb = 32
        local_wall_time_in_s = None
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=local_mem_in_mb,
            wall_time_in_s=local_wall_time_in_s,
            cpu_time_in_s=local_cpu_time_in_s,
            grace_period_in_s=local_grace_period,
            context=multiprocessing.get_context(context),
        )(simulate_work)

        assert wrapped_function(memory, 0, 0) is None, "{}/{}".format(wrapped_function.result,
                                                                   wrapped_function.exit_status)
        assert wrapped_function.exit_status == pynisher.MemorylimitException
        assert wrapped_function.exitcode == 0

    @pytest.mark.parametrize("memory", [1, 10])
    def test_time_out(self, context, memory):
        print("Testing wall clock time constraint.")
        local_mem_in_mb = None
        local_wall_time_in_s = 1
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=local_mem_in_mb,
            wall_time_in_s=local_wall_time_in_s,
            cpu_time_in_s=local_cpu_time_in_s,
            grace_period_in_s=local_grace_period,
            context=multiprocessing.get_context(context),
        )(simulate_work)

        assert wrapped_function(memory, 10, 0) is None
        assert wrapped_function.exit_status == pynisher.TimeoutException, str(
            wrapped_function.result)
        # Apparently, the exit code here is not deterministic (so far only PYthon 3.6)
        assert wrapped_function.exitcode in (-15, 0)

    @pytest.mark.parametrize("processes", [2, 15, 50, 100, 250])
    def test_num_processes(self, context, processes):
        print("Testing number of processes constraint.")
        local_mem_in_mb = None
        local_num_processes = 1
        local_wall_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
            num_processes=local_num_processes,
            grace_period_in_s=local_grace_period,
            context=multiprocessing.get_context(context),
        )(simulate_work)

        assert wrapped_function(0, 0, processes) is None
        assert wrapped_function.exit_status == pynisher.SubprocessException
        assert wrapped_function.exitcode == 0

    def test_crash_unexpectedly(self, context):
        print("Testing an unexpected signal simulating a crash.")
        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
        )(crash_unexpectedly)
        assert wrapped_function(signal.SIGQUIT) is None
        assert wrapped_function.exit_status == pynisher.SignalException
        assert wrapped_function.exitcode == 0

    def test_high_cpu_percentage(self, context):
        print("Testing cpu time constraint.")
        # From the multiprocessing documentation:
        # Starting a process using this method ('spawn') is rather slow
        # compared to using fork or forkserver.
        # Increasing cpu_time_in_s from 2 to 4 seconds
        cpu_time_in_s = 4
        grace_period = 1
        wrapped_function = pynisher.enforce_limits(
            cpu_time_in_s=cpu_time_in_s, grace_period_in_s=grace_period,
            context=multiprocessing.get_context(context),
        )(cpu_usage)

        assert wrapped_function() is None
        assert wrapped_function.exit_status == pynisher.CpuTimeoutException
        assert wrapped_function.exitcode == 0

    @pytest.mark.parametrize("num_elements", [4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144])
    def test_big_return_data(self, context, num_elements):
        print("Testing big return values")
        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
        )(return_big_array)

        bla = wrapped_function(num_elements)
        assert len(bla) == num_elements
        assert wrapped_function.exitcode == 0

    def test_kill_subprocesses(self, context):

        # Work around to address the fact that the main process had left children
        # when running all test in pytest
        initial_recursive_children = len(psutil.Process().children(recursive=True))
        wrapped_function = pynisher.enforce_limits(
            wall_time_in_s=1,
            context=multiprocessing.get_context(context),
        )(spawn_rogue_subprocess)
        wrapped_function(5)

        time.sleep(1)
        p = psutil.Process()
        if context == 'spawn':
            # The parent process starts a fresh python interpreter process.
            assert len(p.children(recursive=True)) - initial_recursive_children == 1, "current={} child={} parent={} initial={}".format(
                p,
                p.children(recursive=True),
                os.getppid(),
                initial_recursive_children
            )
        elif context == 'forkserver':
            # When the program starts and selects the forkserver start method,
            # a server process is started. From then on, whenever a new process
            # is needed, the parent process connects to the server and requests
            # that it fork a new process.
            assert len(p.children(recursive=True)) - initial_recursive_children == 2, "current={} child={} parent={} initial={}".format(
                p,
                p.children(recursive=True),
                os.getppid(),
                initial_recursive_children
            )
        else:
            assert len(p.children(recursive=True)) - initial_recursive_children == 0, "current={} child={} parent={} initial={}".format(
                p,
                p.children(recursive=True),
                os.getppid(),
                initial_recursive_children
            )
        assert wrapped_function.exitcode == -15

    def test_busy_in_C_library(self, context):

        global logger

        wrapped_function = pynisher.enforce_limits(
            wall_time_in_s=2,
            context=multiprocessing.get_context(context),
        )(svm_example)

        start = time.time()
        wrapped_function(16384, 128)
        duration = time.time() - start

        time.sleep(1)
        p = psutil.Process()
        if context == 'spawn':
            # The parent process starts a fresh python interpreter process.
            assert len(p.children(recursive=True)) == 1
        elif context == 'forkserver':
            # When the program starts and selects the forkserver start method,
            # a server process is started. From then on, whenever a new process
            # is needed, the parent process connects to the server and requests
            # that it fork a new process.
            assert len(p.children(recursive=True)) == 2
        else:
            assert len(p.children(recursive=True)) == 0
        # In github actions, I have seen up to 2.2 due to delay
        # relaxing time a bit from 2.1->2.3
        assert duration <= 2.3
        assert wrapped_function.exitcode == -15

    def test_liblinear_svc(self, context, logger_mock):
        # Fitting an SVM to see how C libraries are handles

        global logger

        time_limit = 2
        grace_period = 1

        wrapped_function = pynisher.enforce_limits(
            cpu_time_in_s=time_limit, mem_in_mb=None,
            grace_period_in_s=grace_period, logger=logger,
            context=multiprocessing.get_context(context),
        )
        wrapped_function.logger = logger_mock
        wrapped_function = wrapped_function(svc_example)
        start = time.time()
        wrapped_function(16384, 10000)
        duration = time.time() - start

        # Need more time for spawn processes -- the doc
        # say they are slow!
        time.sleep(5)
        p = psutil.Process()

        assert logger_mock.debug.call_count == 2
        assert logger_mock.debug.call_args_list[0][0][0] == 'Function called with argument: (16384, 10000), {}'
        assert logger_mock.debug.call_args_list[1][0][0] == 'Your function call closed the pipe prematurely -> Subprocess probably got an uncatchable signal.'
        # In the case of spawn/forkserver
        if context == 'spawn':
            # The parent process starts a fresh python interpreter process.
            assert len(p.children(recursive=True)) == 1
        elif context == 'forkserver':
            # When the program starts and selects the forkserver start method,
            # a server process is started. From then on, whenever a new process
            # is needed, the parent process connects to the server and requests
            # that it fork a new process.
            assert len(p.children(recursive=True)) == 2
        else:
            assert len(p.children(recursive=True)) == 0
            # self.assertEqual(wrapped_function.exit_status, pynisher.CpuTimeoutException)
            assert duration > (time_limit - 0.1)
            assert duration < (time_limit + grace_period + 0.1)
        assert wrapped_function.exitcode == -9

    def test_nesting(self, context):

        if context in ['spawn', 'forkserver']:
            pytest.skip("Cannot perform nested functions under spawn/forserved due to EOFError")

        tl = 2  # time limit
        gp = 1  # grace period

        start = time.time()
        nested_pynisher(
            level=2, cputime=2, walltime=2, memlimit=None, increment=1, grace_period=gp,
            context=multiprocessing.get_context(context),
        )
        duration = time.time() - start
        print(duration)

        time.sleep(1)
        p = psutil.Process()
        assert len(p.children(recursive=True)) == 0
        assert duration > tl - 0.1
        assert duration < tl + gp + 0.1

    def test_capture_output(self, context):
        print("Testing capturing of output.")
        global logger

        time_limit = 2
        grace_period = 1

        wrapped_function = pynisher.enforce_limits(
            wall_time_in_s=time_limit, mem_in_mb=None,
            grace_period_in_s=grace_period, logger=logger, capture_output=True,
            context=multiprocessing.get_context(context),
        )(print_and_sleep)

        wrapped_function(5)

        assert '0' in wrapped_function.stdout
        assert wrapped_function.stderr == ''
        assert wrapped_function.exitcode == 0

        wrapped_function = pynisher.enforce_limits(
            wall_time_in_s=time_limit, mem_in_mb=None,
            grace_period_in_s=grace_period, logger=logger, capture_output=True,
            context=multiprocessing.get_context(context),
        )(print_and_fail)

        wrapped_function()

        assert '0' in wrapped_function.stdout
        assert 'RuntimeError' in wrapped_function.stderr
        assert wrapped_function.exitcode == 1

    def test_too_little_memory(self, context):
        # Test what happens if the target process does not have a
        # sufficiently high memory limit

        # 2048 MB
        dummy_content = [42.] * ((1024 * 2048) // 8) # noqa

        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=10,
            context=multiprocessing.get_context(context),
        )(simulate_work)

        wrapped_function(size_in_mb=1000, wall_time_in_s=10, num_processes=1,
                         dummy_content=dummy_content)

        assert wrapped_function.result is None
        # The following is a bit weird, on my local machine I get a SubprocessException,
        # but on travis-ci I get a MemoryLimitException
        assert wrapped_function.exit_status in (pynisher.SubprocessException,
                                                pynisher.MemorylimitException)
        # This is triggered on my local machine, but not on travis-ci
        if wrapped_function.exit_status == pynisher.SubprocessException:
            assert wrapped_function.os_errno == 12
        assert wrapped_function.exitcode == 0

    def test_raise(self, context):
        # As above test does not reliably work on travis-ci,
        # this test checks whether an OSError's error code is properly read out
        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=1000,
            context=multiprocessing.get_context(context),
        )(crash_while_read_file)
        wrapped_function.logger = unittest.mock.Mock()

        # Emulate OS error via file access, as OSError object is reconstructed
        # depending on the context (so we get a None instead of a set code)
        # With file error access we get a consistent 2:
        # 2 - Misuse of shell builtins (according to Bash documentation)
        wrapped_function()

        assert wrapped_function.result is None
        assert wrapped_function.exit_status == pynisher.SubprocessException
        if wrapped_function.exit_status == pynisher.SubprocessException:
            assert wrapped_function.os_errno == 2
        assert wrapped_function.exitcode == 0
