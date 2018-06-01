"""
    RemoteTmpdir is a class that maintains a temporary directory on a
    remote linux system.
    Ex. when copying a test script or binary to DUT, RemoteTmpdir assists
    to prevent pollution of the target.

    RemoteTmpdir is to be created in a fixture, which can take care of a
    testmodule in a subdirectory. Recommended scope is function, to avoid
    polution between tests
"""
import pytest
from labgrid.external import RemoteTmpdir


# scope may also be module or session
@pytest.fixture(scope='function')
def remote_tmpdir(target, request):
    # RemoteTmpdir needs to have a Driver which offers put and run
    shell = target.get_active_driver("CommandProtocol")
    # find the relative root of the files to put
    tmpdir = RemoteTmpdir(shell, request.fspath.dirname)
    yield tmpdir
    # Remove the tmpdir again
    tmpdir.cleanup()


def test_hello(remote_tmpdir):
    shell = target.get_active_driver("CommandProtocol")
    remote_tmpdir.put('hello.sh')
    shell.run_check(remote_tmpdir.path + 'hello.sh')
