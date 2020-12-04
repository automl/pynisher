#! /bin/python
import time
import multiprocessing
import unittest
import unittest.mock
import os
import signal
import logging

import psutil

import pynisher

try:
    import sklearn # noqa

    is_sklearn_available = True
except ImportError:
    print("Scikit Learn was not found!")
    is_sklearn_available = False

# Get the context from the environment, or default to fork
# This can be used as a fixture when pytest environment is
# an stable option
context = os.environ.get('CONTEXT', 'fork')

# Also, the expected recursive children each process should have
# is dependant of the context as follows:
expected_children = {
    # we expect no recursive process on a fork
    'fork': 0,
    # According to the documentation:
    # the parent process starts a fresh python interpreter process.
    # This is treated as a new recursive psutil child
    'spawn': 1,
    # According to the documentation:
    # When the program starts and selects the forkserver start method,
    # a server process is started. From then on, whenever a new process is needed,
    # the parent process connects to the server and requests that it fork a new process.
    # We expect 2 child processes, 1 server dispatching workers and the actual worker
    'forkserver': 2,
}
all_tests = 1
logger = multiprocessing.log_to_stderr()
logger.setLevel(logging.WARNING)


# The functions below are left as globals (at the top of the file)
# as a requirement for the multiple forking processes (a function is pickled
# in the fork server, and the workers/main process function pickle state must match)
# TODO: add tests with large return value to test for deadlock!

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


def return_big_array(num_elements):
    return ([1] * num_elements)


def cpu_usage():
    i = 1
    while True:
        i += 1


def nested_pynisher(level=2, cputime=5, walltime=5, memlimit=10e24, increment=-1, grace_period=1):
    print("this is level {}".format(level))
    if level == 0:
        spawn_rogue_subprocess(10)
    else:
        func = pynisher.enforce_limits(mem_in_mb=memlimit, cpu_time_in_s=cputime, wall_time_in_s=walltime,
                                       context=multiprocessing.get_context(context),
                                       grace_period_in_s=grace_period)(nested_pynisher)
        func(level - 1, None, walltime + increment, memlimit, increment)


def print_and_sleep(t):
    for i in range(t):
        print(i)
        time.sleep(1)


def print_and_fail():
    print(0)
    raise RuntimeError()


def crash_while_read_file():
    with open('some_non_existing_files_to_cause_crash'):
        pass


class test_limit_resources_module(unittest.TestCase):

    @unittest.skipIf(not all_tests, "skipping successful tests")
    def test_success(self):

        print("Testing unbounded function call which have to run through!")
        local_mem_in_mb = None
        local_wall_time_in_s = None
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   context=multiprocessing.get_context(context),
                                                   cpu_time_in_s=local_cpu_time_in_s,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for mem in [1, 2, 4, 8, 16]:
            self.assertEqual((mem, 0, 0), wrapped_function(mem, 0, 0))
            self.assertEqual(wrapped_function.exit_status, 0)
            self.assertEqual(wrapped_function.exitcode, 0)

    @unittest.skipIf(not all_tests, "skipping out_of_memory test")
    def test_out_of_memory(self):
        print("Testing memory constraint.")
        local_mem_in_mb = 32
        local_wall_time_in_s = None
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(
            mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
            context=multiprocessing.get_context(context),
            cpu_time_in_s=local_cpu_time_in_s,
            grace_period_in_s=local_grace_period)(simulate_work)

        for mem in [1024, 2048, 4096]:
            self.assertIsNone(wrapped_function(mem, 0, 0))
            self.assertEqual(wrapped_function.exit_status, pynisher.MemorylimitException)
            self.assertEqual(wrapped_function.exitcode, 0)

    @unittest.skipIf(not all_tests, "skipping time_out test")
    def test_time_out(self):
        print("Testing wall clock time constraint.")
        local_mem_in_mb = None
        local_wall_time_in_s = 1
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   context=multiprocessing.get_context(context),
                                                   cpu_time_in_s=local_cpu_time_in_s,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for mem in range(1, 10):
            self.assertIsNone(wrapped_function(mem, 10, 0))
            self.assertEqual(wrapped_function.exit_status, pynisher.TimeoutException, str(wrapped_function.result))
            # Apparently, the exit code here is not deterministic (so far only PYthon 3.6)
            self.assertIn(wrapped_function.exitcode, (-15, 0))

    @unittest.skipIf(not all_tests, "skipping too many processes test")
    def test_num_processes(self):
        print("Testing number of processes constraint.")
        local_mem_in_mb = None
        local_num_processes = 1
        local_wall_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   context=multiprocessing.get_context(context),
                                                   num_processes=local_num_processes,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for processes in [2, 15, 50, 100, 250]:
            self.assertIsNone(wrapped_function(0, 0, processes))
            self.assertEqual(wrapped_function.exit_status, pynisher.SubprocessException)
            self.assertEqual(wrapped_function.exitcode, 0)

    @unittest.skipIf(not all_tests, "skipping unexpected signal test")
    def test_crash_unexpectedly(self):
        print("Testing an unexpected signal simulating a crash.")
        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
        )(crash_unexpectedly)
        self.assertIsNone(wrapped_function(signal.SIGQUIT))
        self.assertEqual(wrapped_function.exit_status, pynisher.SignalException)
        self.assertEqual(wrapped_function.exitcode, 0)

    @unittest.skipIf(not all_tests, "skipping unexpected signal test")
    def test_high_cpu_percentage(self):
        print("Testing cpu time constraint.")
        cpu_time_in_s = 2
        grace_period = 1
        wrapped_function = pynisher.enforce_limits(cpu_time_in_s=cpu_time_in_s,
                                                   context=multiprocessing.get_context(context),
                                                   grace_period_in_s=grace_period)(
            cpu_usage)

        self.assertIsNone(wrapped_function())
        self.assertEqual(wrapped_function.exit_status, pynisher.CpuTimeoutException)
        self.assertEqual(wrapped_function.exitcode, 0)

    @unittest.skipIf(not all_tests, "skipping big data test")
    def test_big_return_data(self):
        print("Testing big return values")
        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
        )(return_big_array)

        for num_elements in [4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144]:
            bla = wrapped_function(num_elements)
            self.assertEqual(len(bla), num_elements)
            self.assertEqual(wrapped_function.exitcode, 0)

    @unittest.skipIf(not all_tests, "skipping subprocess changing process group")
    def test_kill_subprocesses(self):
        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
            wall_time_in_s=1)(spawn_rogue_subprocess)
        wrapped_function(5)

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), expected_children[context])
        self.assertEqual(wrapped_function.exitcode, -15)

    @unittest.skipIf(not is_sklearn_available, "test requires scikit learn")
    @unittest.skipIf(not all_tests, "skipping fitting an SVM to see how C libraries are handles")
    def test_busy_in_C_library(self):

        global logger

        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
            wall_time_in_s=2)(svm_example)

        start = time.time()
        wrapped_function(16384, 128)
        duration = time.time() - start

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), expected_children[context])
        self.assertTrue(duration <= 2.1)
        self.assertEqual(wrapped_function.exitcode, -15)
        self.assertLess(duration, 2.1)

    @unittest.skipIf(not is_sklearn_available, "test requires scikit learn")
    @unittest.skipIf(not all_tests, "skipping fitting an SVM to see how C libraries are handles")
    @unittest.skipIf(context != 'fork', "I don't think this function works even in fork. It produces a EOFError. But in spawn/forkserver it last less than expected time.")
    def test_liblinear_svc(self):

        global logger

        time_limit = 2
        grace_period = 1
        logger_mock = unittest.mock.Mock()

        wrapped_function = pynisher.enforce_limits(cpu_time_in_s=time_limit, mem_in_mb=None,
                                                   context=multiprocessing.get_context(context),
                                                   grace_period_in_s=grace_period, logger=logger)
        wrapped_function.logger = logger_mock
        wrapped_function = wrapped_function(svc_example)
        start = time.time()
        wrapped_function(16384, 10000)
        duration = time.time() - start

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), expected_children[context])
        self.assertEqual(logger_mock.debug.call_count, 2)
        self.assertEqual(logger_mock.debug.call_args_list[0][0][0],
                         'Function called with argument: (16384, 10000), {}')
        self.assertEqual(logger_mock.debug.call_args_list[1][0][0],
                         'Your function call closed the pipe prematurely -> '
                         'Subprocess probably got an uncatchable signal.')
        # self.assertEqual(wrapped_function.exit_status, pynisher.CpuTimeoutException)
        self.assertGreater(duration, time_limit - 0.1)
        self.assertLess(duration, time_limit + grace_period + 0.1)
        self.assertEqual(wrapped_function.exitcode, -9)

    @unittest.skipIf(not all_tests, "skipping nested pynisher test")
    def test_nesting(self):

        tl = 2  # time limit
        gp = 1  # grace period

        start = time.time()
        nested_pynisher(level=2, cputime=2, walltime=2, memlimit=None, increment=1, grace_period=gp)
        duration = time.time() - start
        print(duration)

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), expected_children[context])
        self.assertGreater(duration, tl - 0.1)
        self.assertLess(duration, tl + gp + 0.1)

    @unittest.skipIf(not all_tests, "skipping capture stdout test")
    def test_capture_output(self):
        print("Testing capturing of output.")
        global logger

        time_limit = 2
        grace_period = 1

        wrapped_function = pynisher.enforce_limits(wall_time_in_s=time_limit, mem_in_mb=None,
                                                   context=multiprocessing.get_context(context),
                                                   grace_period_in_s=grace_period, logger=logger, capture_output=True)(
            print_and_sleep)

        wrapped_function(5)

        self.assertTrue('0' in wrapped_function.stdout)
        self.assertEqual(wrapped_function.stderr, '')
        self.assertEqual(wrapped_function.exitcode, 0)

        wrapped_function = pynisher.enforce_limits(wall_time_in_s=time_limit, mem_in_mb=None,
                                                   context=multiprocessing.get_context(context),
                                                   grace_period_in_s=grace_period, logger=logger, capture_output=True)(
            print_and_fail)

        wrapped_function()

        self.assertIn('0', wrapped_function.stdout)
        self.assertIn('RuntimeError', wrapped_function.stderr)
        self.assertEqual(wrapped_function.exitcode, 1)

    def test_too_little_memory(self):
        # Test what happens if the target process does not have a sufficiently high memory limit

        # 2048 MB
        dummy_content = [42.] * ((1024 * 2048) // 8) # noqa

        wrapped_function = pynisher.enforce_limits(mem_in_mb=1,
                                                   context=multiprocessing.get_context(context),
                                                   )(simulate_work)

        wrapped_function(size_in_mb=1000, wall_time_in_s=10, num_processes=1,
                         dummy_content=dummy_content)

        self.assertIsNone(wrapped_function.result)
        # The following is a bit weird, on my local machine I get a SubprocessException, but on
        # travis-ci I get a MemoryLimitException
        self.assertIn(wrapped_function.exit_status,
                      (pynisher.SubprocessException, pynisher.MemorylimitException))
        # This is triggered on my local machine, but not on travis-ci
        if wrapped_function.exit_status == pynisher.SubprocessException:
            self.assertEqual(wrapped_function.os_errno, 12)
        self.assertEqual(wrapped_function.exitcode, 0)

    def test_raise(self):
        # As above test does not reliably work on travis-ci, this test checks whether an
        # OSError's error code is properly read out
        wrapped_function = pynisher.enforce_limits(
            context=multiprocessing.get_context(context),
            mem_in_mb=1000)(crash_while_read_file)
        wrapped_function.logger = unittest.mock.Mock()

        # Emulate OS error via file access, as OSError object is reconstructed
        # depending on the context (so we get a None instead of a set code)
        # With file error access we get a consistent 2:
        # 2 - Misuse of shell builtins (according to Bash documentation)
        wrapped_function()

        self.assertIsNone(wrapped_function.result)
        self.assertEqual(wrapped_function.exit_status, pynisher.SubprocessException)
        if wrapped_function.exit_status == pynisher.SubprocessException:
            self.assertEqual(wrapped_function.os_errno, 2)
        self.assertEqual(wrapped_function.exitcode, 0)


if __name__ == '__main__':
    unittest.main()
