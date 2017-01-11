from labgrid.driver import ShellDriver, SSHDriver
from labgrid.external import USBStick
from labgrid.protocol import InfoProtocol


def test_stick_plugin(stick):
    stick.plug_in()


def test_stick_upload(stick):
    stick.plug_out()
    stick.upload_file('testfile')
    stick.plug_in()
