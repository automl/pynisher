from __future__ import annotations

from typing import Callable, Type

from itertools import product

from sklearn.datasets import make_classification, make_regression
from sklearn.svm import SVC, SVR

from pynisher import (
    CpuTimeoutException,
    MemoryLimitException,
    PynisherException,
    WallTimeoutException,
    limit,
)
from pynisher.support import contexts

import pytest


def train_svr(n_samples: int, n_features: int) -> None:
    """Trains an svr model"""
    X, y = make_regression(n_samples=n_samples, n_features=n_features)
    SVR().fit(X, y)


def train_svc(n_samples: int, n_features: int) -> None:
    """Trains an svm model"""
    X, y = make_classification(n_samples=n_samples, n_features=n_features)
    SVC().fit(X, y)


constraints_with_exceptions = [
    (CpuTimeoutException, {"cpu_time": (1, "s")}),
    (MemoryLimitException, {"memory": (1, "B")}),
    (WallTimeoutException, {"wall_time": (1, "s")}),
]


@pytest.mark.parametrize(
    "constraints, model_trainer, context",
    list(product(constraints_with_exceptions, [train_svc, train_svr], contexts)),
)
def test_train_svm(
    constraints: tuple[Type[PynisherException], dict],
    model_trainer: Callable[[int, int], None],
    context: str,
) -> None:
    """
    Expects
    -------
    * Should raise the expected exception with the given limits
    """
    exception, limits = constraints
    lf = limit(model_trainer, **limits)

    with pytest.raises(exception):
        lf(n_samples=16384, n_features=128)
