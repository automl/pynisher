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

all_tests = 1
logger = multiprocessing.log_to_stderr()
logger.setLevel(logging.WARNING)


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
                                       grace_period_in_s=grace_period)(nested_pynisher)
        func(level - 1, None, walltime + increment, memlimit, increment)


class test_limit_resources_module(unittest.TestCase):

    @unittest.skipIf(not all_tests, "skipping successful tests")
    def test_success(self):

        print("Testing unbounded function call which have to run through!")
        local_mem_in_mb = None
        local_wall_time_in_s = None
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   cpu_time_in_s=local_cpu_time_in_s,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for mem in [1, 2, 4, 8, 16]:
            self.assertEqual((mem, 0, 0), wrapped_function(mem, 0, 0))
            self.assertEqual(wrapped_function.exit_status, 0)

    @unittest.skipIf(not all_tests, "skipping out_of_memory test")
    def test_out_of_memory(self):
        print("Testing memory constraint.")
        local_mem_in_mb = 32
        local_wall_time_in_s = None
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   cpu_time_in_s=local_cpu_time_in_s,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for mem in [1024, 2048, 4096]:
            self.assertIsNone(wrapped_function(mem, 0, 0))
            self.assertEqual(wrapped_function.exit_status, pynisher.MemorylimitException)

    @unittest.skipIf(not all_tests, "skipping time_out test")
    def test_time_out(self):
        print("Testing wall clock time constraint.")
        local_mem_in_mb = None
        local_wall_time_in_s = 1
        local_cpu_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   cpu_time_in_s=local_cpu_time_in_s,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for mem in range(1, 10):
            self.assertIsNone(wrapped_function(mem, 10, 0))
            self.assertEqual(wrapped_function.exit_status, pynisher.TimeoutException, str(wrapped_function.result))

    @unittest.skipIf(not all_tests, "skipping too many processes test")
    def test_num_processes(self):
        print("Testing number of processes constraint.")
        local_mem_in_mb = None
        local_num_processes = 1
        local_wall_time_in_s = None
        local_grace_period = None

        wrapped_function = pynisher.enforce_limits(mem_in_mb=local_mem_in_mb, wall_time_in_s=local_wall_time_in_s,
                                                   num_processes=local_num_processes,
                                                   grace_period_in_s=local_grace_period)(simulate_work)

        for processes in [2, 15, 50, 100, 250]:
            self.assertIsNone(wrapped_function(0, 0, processes))
            self.assertEqual(wrapped_function.exit_status, pynisher.SubprocessException)

    @unittest.skipIf(not all_tests, "skipping unexpected signal test")
    def test_crash_unexpectedly(self):
        print("Testing an unexpected signal simulating a crash.")
        wrapped_function = pynisher.enforce_limits()(crash_unexpectedly)
        self.assertIsNone(wrapped_function(signal.SIGQUIT))
        self.assertEqual(wrapped_function.exit_status, pynisher.SignalException)

    @unittest.skipIf(not all_tests, "skipping unexpected signal test")
    def test_high_cpu_percentage(self):
        print("Testing cpu time constraint.")
        cpu_time_in_s = 2
        grace_period = 1
        wrapped_function = pynisher.enforce_limits(cpu_time_in_s=cpu_time_in_s, grace_period_in_s=grace_period)(
            cpu_usage)

        self.assertEqual(None, wrapped_function())
        self.assertEqual(wrapped_function.exit_status, pynisher.CpuTimeoutException)

    @unittest.skipIf(not all_tests, "skipping big data test")
    def test_big_return_data(self):
        print("Testing big return values")
        wrapped_function = pynisher.enforce_limits()(return_big_array)

        for num_elements in [4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144]:
            bla = wrapped_function(num_elements)
            self.assertEqual(len(bla), num_elements)

    @unittest.skipIf(not all_tests, "skipping subprocess changing process group")
    def test_kill_subprocesses(self):
        wrapped_function = pynisher.enforce_limits(wall_time_in_s=1)(spawn_rogue_subprocess)
        wrapped_function(5)

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), 0)

    @unittest.skipIf(not is_sklearn_available, "test requires scikit learn")
    @unittest.skipIf(not all_tests, "skipping fitting an SVM to see how C libraries are handles")
    def test_busy_in_C_library(self):

        global logger

        wrapped_function = pynisher.enforce_limits(wall_time_in_s=2)(svm_example)

        start = time.time()
        wrapped_function(16384, 128)
        duration = time.time() - start

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), 0)
        self.assertTrue(duration < 2.1)

    @unittest.skipIf(not is_sklearn_available, "test requires scikit learn")
    @unittest.skipIf(not all_tests, "skipping fitting an SVM to see how C libraries are handles")
    def test_liblinear_svc(self):

        global logger

        time_limit = 2
        grace_period = 1
        mock = unittest.mock.Mock()

        wrapped_function = pynisher.enforce_limits(cpu_time_in_s=time_limit, mem_in_mb=None,
                                                   grace_period_in_s=grace_period, logger=logger)
        wrapped_function.logger = mock
        wrapped_function = wrapped_function(svc_example)
        start = time.time()
        wrapped_function(16384, 10000)
        duration = time.time() - start

        time.sleep(1)
        p = psutil.Process()
        self.assertEqual(len(p.children(recursive=True)), 0)
        self.assertEqual(mock.debug.call_count, 2)
        self.assertEqual(mock.debug.call_args_list[0][0][0],
                         'Function called with argument: (16384, 10000), {}')
        self.assertEqual(mock.debug.call_args_list[1][0][0],
                         'Your function call closed the pipe prematurely -> '
                         'Subprocess probably got an uncatchable signal.')
        # self.assertEqual(wrapped_function.exit_status, pynisher.CpuTimeoutException)
        self.assertGreater(duration, time_limit - 0.1)
        self.assertLess(duration, time_limit + grace_period + 0.1)

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
        self.assertEqual(len(p.children(recursive=True)), 0)
        self.assertTrue(duration > tl - 0.1)
        self.assertTrue(duration < tl + gp + 0.1)

    @unittest.skipIf(not all_tests, "skipping capture stdout test")
    def test_capture_output(self):
        print("Testing capturing of output.")
        global logger

        time_limit = 2
        grace_period = 1

        def print_and_sleep(t):
            for i in range(t):
                print(i)
                time.sleep(1)

        wrapped_function = pynisher.enforce_limits(wall_time_in_s=time_limit, mem_in_mb=None,
                                                   grace_period_in_s=grace_period, logger=logger, capture_output=True)(
            print_and_sleep)

        wrapped_function(5)

        self.assertTrue('0' in wrapped_function.stdout)
        self.assertTrue(wrapped_function.stderr == '')

        def print_and_fail():
            print(0)
            raise RuntimeError()

        wrapped_function = pynisher.enforce_limits(wall_time_in_s=time_limit, mem_in_mb=None,
                                                   grace_period_in_s=grace_period, logger=logger, capture_output=True)(
            print_and_fail)

        wrapped_function()

        self.assertTrue('0' in wrapped_function.stdout)
        self.assertTrue('RuntimeError' in wrapped_function.stderr)

    def test_too_little_memory(self):

        # 2048 MB
        dummy_content = [42.] * ((1024 * 2048) // 8) # noqa

        wrapped_function = pynisher.enforce_limits(mem_in_mb=50)(simulate_work)
        wrapped_function.logger = unittest.mock.Mock()

        wrapped_function(size_in_mb=1000, wall_time_in_s=10, num_processes=1,
                         dummy_content=dummy_content)

        self.assertIsNone(wrapped_function.result)
        self.assertIs(wrapped_function.exit_status, pynisher.SubprocessException)
        self.assertEqual(wrapped_function.os_errno, 12)


if __name__ == '__main__':
    unittest.main()
