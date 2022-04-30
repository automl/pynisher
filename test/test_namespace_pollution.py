import sys

from pynisher import PynisherException, contexts, limit

import pytest


def import_sklearn() -> None:
    """Imports sklearn into a local namespace and has an sklearn object in its args"""
    from sklearn.exceptions import NotFittedError
    from sklearn.svm import SVR

    raise NotFittedError(SVR())


@pytest.mark.parametrize("context", contexts)
def test_not_in_namespace(context: str) -> None:
    """
    Expects
    -------
    * If wrapping exceptions from a locally imported namespace,
      the error should leak no namespaces into the master process
    """
    with limit(import_sklearn, context=context, wrap_errors=True) as lf:

        try:
            lf()
        except PynisherException as e:
            print(e.args)

    assert "sklearn" not in sys.modules.keys()
