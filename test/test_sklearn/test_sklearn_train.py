"""
Tracking:
* When failinga to import with a low memory limit, an import error is raised
"""
from __future__ import annotations

from typing import Any

import faulthandler
import os
import platform
import time

import numpy as np
import psutil

from pynisher import (
    CpuTimeoutException,
    MemoryLimitException,
    WallTimeoutException,
    contexts,
    limit,
    supports,
)
from pynisher.util import Monitor

import pytest


def train_svr(model: Any, X: np.ndarray, y: np.ndarray, limit: Any) -> bool:
    """Trains an svr model"""
    m = Monitor()
    print("Memory before fit", m.memory("mb"))
    print("Limit ", limit)

    # This will cause a coredump with sigdev
    with open(os.devnull, "rb") as f:
        faulthandler.enable(file=f)
        model.fit(X, y)
    print("Memory after fit", m.memory("mb"))

    return True


@pytest.mark.skipif(
    not supports("memory"),
    reason=f"Can't limit `memory` on {platform.platform()}",
)
@pytest.mark.parametrize("context", contexts)
def test_train_svr_memory(context: str) -> None:
    """
    Expects
    -------
    * Should raise a MemoryError if it ran out of memory during fit

    Note
    ----
    What will actually happen is a segmentation fault, we deal with this
    in `pynisher`
    """
    m = Monitor()
    from sklearn.datasets import make_regression
    from sklearn.svm import SVR

    model = SVR()
    X, y = make_regression(n_samples=30_000, n_features=128)

    # Seem fit will consume about 28mb extra, see __main__
    # Add 1MB
    too_little_mem = round(m.memory("MB") + 1)

    lf = limit(train_svr, memory=(too_little_mem, "MB"))

    completed = False
    with pytest.raises(MemoryLimitException):
        completed = lf(model, X, y, too_little_mem)

    assert completed is not True
    assert lf._process is not None and not lf._process.is_running()

    try:
        children = lf._process.children()
        assert not any(children)
    except psutil.NoSuchProcess:
        pass


@pytest.mark.parametrize("context", contexts)
def test_train_svr_cputime(context: str) -> None:
    """
    Expects
    -------
    * Limiting cputime should result in a CpuTimeoutException
    """
    from sklearn.datasets import make_regression
    from sklearn.svm import SVR

    model = SVR()
    X, y = make_regression(n_samples=30_000, n_features=128)

    cpu_limit = (2, "s")
    lf = limit(train_svr, cpu_time=cpu_limit)

    completed = False
    with pytest.raises(CpuTimeoutException):
        completed = lf(model, X, y, cpu_limit)

    time.sleep(1)
    assert completed is not True
    assert lf._process is not None and not lf._process.is_running()

    try:
        children = lf._process.children()
        assert not any(children)
    except psutil.NoSuchProcess:
        pass


@pytest.mark.parametrize("context", contexts)
def test_train_svr_walltime(context: str) -> None:
    """
    Expects
    -------
    * Limiting cputime should result in a CpuTimeoutException
    """
    from sklearn.datasets import make_regression
    from sklearn.svm import SVR

    model = SVR()
    X, y = make_regression(n_samples=30_000, n_features=128)

    wall_time = (2, "s")
    lf = limit(train_svr, wall_time=wall_time)

    completed = False
    with pytest.raises(WallTimeoutException):
        completed = lf(model, X, y, wall_time)

    assert completed is not True
    assert lf._process is not None and not lf._process.is_running()

    try:
        children = lf._process.children()
        assert not any(children)
    except psutil.NoSuchProcess:
        pass


if __name__ == "__main__":
    """
    For checking memory usage with the SVM

    My machine:
    Before model and data 689.390625
    After model and data 836.6640625
    After fit 864.01953125
    Fitting duration in cputime  89.290726962

    It seems it takes about 28mb extra to fit with (30_000, 128) data
    """
    from sklearn.datasets import make_regression
    from sklearn.svm import SVR

    m = Monitor()

    print("Before model and data", m.memory("mb"))
    X, y = make_regression(n_samples=30_000, n_features=128)
    model = SVR()
    print("After model and data", m.memory("mb"))

    start = time.process_time()
    model.fit(X, y)
    end = time.process_time()
    print("After fit", m.memory("mb"))
    print("Fitting duration in cputime ", end - start)
