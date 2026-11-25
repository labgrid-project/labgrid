from unittest.mock import MagicMock

import pytest

from labgrid.resource.suggest import Suggester


@pytest.fixture
def fake_udev(monkeypatch, isolated_resource_managers):
    """Replace pyudev with a mock so Suggester can be constructed on any host."""
    monkeypatch.setattr('labgrid.resource.udev.import_module', lambda name: MagicMock())


def test_suggester_create(fake_udev):
    """All resources created by labgrid-suggest must pass attrs validation,
    including those with mandatory arguments such as SiSPMPowerPort.index."""
    suggester = Suggester(None)

    classes = {type(r).__name__ for r in suggester.resources}
    assert 'SiSPMPowerPort' in classes
    assert 'USBPowerPort' in classes
