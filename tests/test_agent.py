import pytest
from py.path import local

import labgrid.util.agentwrapper
from labgrid.util.agentwrapper import AgentError, AgentException, AgentWrapper, b2s, s2b

@pytest.fixture(scope='function')
def subprocess_mock(mocker):
    import subprocess

    original = subprocess.Popen

    agent = local(labgrid.util.agentwrapper.__file__).dirpath('agent.py')

    def run(args, **kwargs):
        assert args[0] in ['rsync', 'ssh']
        if args[0] == 'rsync':
            src = local(args[-2])
            assert src == agent
            dst = args[-1]
            assert ':' in dst
            dst = dst.split(':', 1)[1]
            assert '/' not in dst
            assert dst.startswith('.labgrid_agent')
            return original(['true'], **kwargs)
        elif args[0] == 'ssh':
            assert '--' in args
            args = args[args.index('--')+1:]
            assert len(args) == 2
            assert args[0] == 'python3'
            assert args[1].startswith('.labgrid_agent')
            # we need to use the original here to get the coverage right
            return original(['python3', str(agent)], **kwargs)

    mocker.patch('subprocess.Popen', run)

def test_create(subprocess_mock):
    aw = AgentWrapper('localhost')
    aw.close()

def test_call(subprocess_mock):
    aw = AgentWrapper('localhost')
    assert aw.call('test') == []
    assert aw.call('test', 0) == [0]
    assert aw.call('test', 0, 1) == [1, 0]
    assert aw.call('test', 'foo') == ['foo']
    assert aw.call('test', '{') == ['{']

def test_proxy(subprocess_mock):
    aw = AgentWrapper('localhost')
    assert aw.test() == []
    assert aw.test( 0, 1) == [1, 0]

def test_bytes(subprocess_mock):
    aw = AgentWrapper('localhost')
    assert s2b(aw.test(b2s(b'\x00foo'))[0]) == b'\x00foo'

def test_exception(subprocess_mock):
    aw = AgentWrapper('localhost')

    with pytest.raises(AgentException) as excinfo:
        aw.error('foo')
    assert excinfo.value.args == ("ValueError('foo')",)

    with pytest.raises(AgentException) as excinfo:
        aw.error('bar')
    assert excinfo.value.args == ("ValueError('bar')",)

def test_error(subprocess_mock):
    aw = AgentWrapper('localhost')
    aw.agent.stdin.write(b'\x00')
    with pytest.raises(AgentError):
        aw.test()

def test_module(subprocess_mock):
    aw = AgentWrapper('localhost')
    dummy = aw.load('dummy')
    assert dummy.neg(1) == -1

def test_local():
    aw = AgentWrapper(None)

    assert aw.test() == []
    assert aw.test( 0, 1) == [1, 0]

    assert s2b(aw.test(b2s(b'\x00foo'))[0]) == b'\x00foo'

    with pytest.raises(AgentException) as excinfo:
        aw.error('foo')
    assert excinfo.value.args == ("ValueError('foo')",)

    with pytest.raises(AgentException) as excinfo:
        aw.error('bar')
    assert excinfo.value.args == ("ValueError('bar')",)

    dummy = aw.load('dummy')
    assert dummy.neg(1) == -1

def test_all_modules():
    aw = AgentWrapper(None)
    aw.load('deditec_relais8')
    methods = aw.list()
    assert 'deditec_relais8.set' in methods
    assert 'deditec_relais8.get' in methods
    aw.load('sysfsgpio')
    methods = aw.list()
    assert 'sysfsgpio.set' in methods
    assert 'sysfsgpio.get' in methods
    aw.load('usb_hid_relay')
    methods = aw.list()
    assert 'usb_hid_relay.set' in methods
    assert 'usb_hid_relay.get' in methods

def test_import_modules():
    import labgrid.util.agents
    import labgrid.util.agents.dummy
    from labgrid.util.agents import deditec_relais8, sysfsgpio
