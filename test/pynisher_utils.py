from unittest.mock import MagicMock


class PickableMock(MagicMock):
    def __reduce__(self):
        return (MagicMock, ())
