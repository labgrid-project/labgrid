import pytest

from labgrid.driver import FileDigitalOutputDriver

def test_filedigital_instance(target, mocker):
    m_isfile = mocker.patch('os.path.isfile', return_value=True)
    d = FileDigitalOutputDriver(target, name=None, filepath='/dev/null')
    target.activate(d)
    assert isinstance(d, FileDigitalOutputDriver)
    m_isfile.assert_called_once_with('/dev/null')

def test_filedigital_set(target, mocker):
    m_isfile = mocker.patch('os.path.isfile', return_value=True)
    m_open = mocker.patch('builtins.open', mocker.mock_open())
    d = FileDigitalOutputDriver(target, name=None, filepath='/dev/null')
    target.activate(d)
    d.set(True)
    m_isfile.assert_called_once_with('/dev/null')
    m_open.assert_called_once_with('/dev/null', 'w')
    m_open.return_value.write.assert_called_once_with('1\n')

def test_filedigital_get(target, mocker):
    m_isfile = mocker.patch('os.path.isfile', return_value=True)
    m_open = mocker.patch('builtins.open', mocker.mock_open(read_data='1\n'))
    d = FileDigitalOutputDriver(target, name=None, filepath='/dev/null')
    target.activate(d)
    assert d.get() is True
    m_isfile.assert_called_once_with('/dev/null')
    m_open.assert_called_once_with('/dev/null')
    m_open.return_value.read.assert_called_once()
