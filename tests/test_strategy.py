import pytest

from labgrid.strategy import BareboxStrategy, UBootStrategy
from labgrid.exceptions import NoDriverFoundError


def test_create_barebox(target):
    # we currently don't have the necessary mocks
    with pytest.raises(NoDriverFoundError):
        s = BareboxStrategy(target)

def test_create_uboot(target):
    # we currently don't have the necessary mocks
    with pytest.raises(NoDriverFoundError):
        s = UBootStrategy(target)
