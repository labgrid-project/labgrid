from labgrid.resource.pyvisa import PyVISADevice
from labgrid.driver.pyvisadriver import PyVISADriver

import pytest

pytest.importorskip("pyvisa")

def test_pyvisa_resource(target):
    PyVISADevice(target, name=None, type='TCPIP', url='127.0.0.1')


def test_resource_driver(target, mocker):
    PyVISADevice(target, name=None, type='TCPIP', url='127.0.0.1')
    driver = PyVISADriver(target, name=None)

    mocker.patch('pyvisa.ResourceManager.open_resource', return_value=None)
    target.activate(driver)
