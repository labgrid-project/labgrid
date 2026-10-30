import argparse

import pytest

from labgrid import Target
from labgrid.driver.openocddriver import OpenOCDDriver
from labgrid.remote.client import ClientSession, UserError
from labgrid.resource.remote import NetworkUSBDebugger


def test_parse_driver_args():
    session = object.__new__(ClientSession)

    args = session._parse_driver_args([
        'search=["path"]',
        'load_commands=["init", "shutdown"]',
        'board_config=board.cfg',
    ])

    assert args == {
        "search": ["path"],
        "load_commands": ["init", "shutdown"],
        "board_config": "board.cfg",
    }


def test_parse_driver_args_invalid():
    session = object.__new__(ClientSession)

    with pytest.raises(UserError, match="expected key=value"):
        session._parse_driver_args(["load_commands"])

    with pytest.raises(UserError, match="invalid value for bootstrap argument 'search'"):
        session._parse_driver_args(['search=["path"'])


def test_bootstrap_network_usb_debugger(monkeypatch):
    target = Target("test")
    debugger = NetworkUSBDebugger(
        target,
        name=None,
        host="host",
        busnum=1,
        devnum=2,
        path="1-2",
        vendor_id=1,
        model_id=2,
    )
    monkeypatch.setattr(debugger.manager, "poll", lambda: None)
    debugger.avail = True

    session = object.__new__(ClientSession)
    session.args = argparse.Namespace(
        wait=12.5,
        name=None,
        filename="dummy",
        bootstrap_args=[
            'search=["path"]',
            'load_commands=["init", "shutdown"]',
            'interface_config=interface.cfg',
        ],
    )
    session.get_acquired_place = lambda: argparse.Namespace(name="test")
    session._get_target = lambda place: target

    load_calls = []

    def fake_load(self, filename=None):
        load_calls.append((self, filename))

    monkeypatch.setattr(OpenOCDDriver, "load", fake_load)

    session.bootstrap()

    driver = target.get_driver(OpenOCDDriver, activate=False)
    assert driver.interface is debugger
    assert driver.interface.timeout == 12.5
    assert driver.search == ["path"]
    assert driver.load_commands == ["init", "shutdown"]
    assert driver.interface_config == "interface.cfg"
    assert load_calls == [(driver, "dummy")]
