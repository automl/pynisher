import os
import platform

from pynisher import limit, supports_limit_decorator

import pytest

if not supports_limit_decorator():
    pytest.skip(
        f"Platform {platform.platform()} does not suppport @limit",
        allow_module_level=True,
    )
else:
    # This must be contianed within the gaurd to prevent it being executed
    # if the above conditions fail
    @limit(name="hello")
    def limited_func_with_decorator() -> None:
        """A limit function"""
        pass


def test_limit_gives_helpful_err_message_with_misuse() -> None:
    """
    Expects
    -------
    * Should raise an error if decorator is used without arguments
    """
    with pytest.raises(ValueError, match=r"Please pass arguments to decorator `limit`"):

        @limit  # type: ignore
        def f(x: int) -> int:
            return x


def test_limit_as_runs_as_seperate_process() -> None:
    """
    Expects
    -------
    * Should be able to decorate function
    """
    this_process_id = os.getpid()
    other_process_id = limited_func_with_decorator()
    assert this_process_id != other_process_id
