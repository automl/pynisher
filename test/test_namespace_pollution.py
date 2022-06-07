from typing import Any

import sys

from pynisher import PynisherException, contexts, limit

import pytest


def import_sklearn() -> None:
    """Imports sklearn into a local namespace and has an sklearn object in its args"""
    from sklearn.exceptions import NotFittedError
    from sklearn.svm import SVR

    raise NotFittedError(SVR())


@pytest.mark.parametrize("context", contexts)
@pytest.mark.parametrize(
    "wrap_errors", [True, ["NotFittedError"], {"pynisher": ["NotFittedError"]}]
)
def test_not_in_namespace(context: str, wrap_errors: Any) -> None:
    """
    Expects
    -------
    * If wrapping exceptions from a locally imported namespace,
      the error should leak no namespaces into the master process
    """
    with limit(import_sklearn, context=context, wrap_errors=wrap_errors) as lf:

        try:
            lf()
        except PynisherException:
            pass

    assert "sklearn" not in sys.modules.keys()


""" This test causes the tests for `import_sklearn` to fail as it is already in the
namespace. It is here for reference but it does pass

@pytest.mark.parametrize("context", contexts)
def test_namespace_polluted_if_not_wrapped(context: str) -> None:
    Expects
    -------
    * If not wrapping errors then the exception returned can pollute the
      namespace of the master process
    with limit(import_sklearn, context=context) as lf:

        try:
            lf()
        except Exception:
            assert "sklearn" in sys.modules.keys()
"""
