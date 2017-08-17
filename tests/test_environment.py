import pytest

from labgrid import Environment, NoConfigFoundError
from labgrid.driver.fake import FakeConsoleDriver, FakePowerDriver


class TestEnvironment:
    def test_noconfig_instance(self):
        with pytest.raises(NoConfigFoundError):
            e = Environment()

    def test_instance(self, tmpdir):
        p = tmpdir.join("config.yaml")
        p.write(
            """
        targets:
          test1:
            drivers: {}
          test2:
            role: foo
            resources: {}
        """
        )
        e = Environment(str(p))
        assert (isinstance(e, Environment))

    def test_get_target(self, tmpdir):
        p = tmpdir.join("config.yaml")
        p.write(
            """
        targets:
          test1:
            drivers: {}
          test2:
            role: foo
            resources: {}
        """
        )
        e = Environment(str(p))
        assert (e.get_target("test1"))
        assert (e.get_target("test2"))

    def test_instance_invalid_yaml(self, tmpdir):
        p = tmpdir.join("config.yaml")
        p.write(
            """
        I a(m) no yaml:
          - keks
          cookie
        """
        )
        with pytest.raises(NoConfigFoundError):
            e = Environment(str(p))

    def test_env_imports_yaml(self, tmpdir):
        import sys
        i = tmpdir.join("myimport.py")
        i.write(
"""
class Test:
    pass
"""
        )
        p = tmpdir.join("config.yaml")
        p.write(
    """
targets:
  main:
    drivers: {}
imports:
  - {}
""".format("{}",str(i))
        )
        e = Environment(str(p))
        assert (isinstance(e, Environment))
        assert "myimport" in sys.modules
        import myimport
        t = myimport.Test()
        assert (isinstance(t, myimport.Test))

    def test_create_named_resources(self, tmpdir):
        p = tmpdir.join("config.yaml")
        p.write(
            """
        targets:
          test1:
            resources:
            - AndroidFastboot:
                name: "fastboot"
                match: {}
            - RawSerialPort:
                port: "/dev/ttyUSB0"
                speed: 115200
        """
        )
        e = Environment(str(p))
        t = e.get_target("test1")

    def test_create_named_drivers(self, tmpdir):
        p = tmpdir.join("config.yaml")
        p.write(
            """
        targets:
          test1:
            resources:
            - AndroidFastboot:
                name: "fastboot"
                match: {}
            - RawSerialPort:
                name: "serial_a"
                port: "/dev/ttyUSB0"
                speed: 115200
            - cls: RawSerialPort
              name: "serial_b"
              port: "/dev/ttyUSB0"
              speed: 115200
            drivers:
            - FakeConsoleDriver:
                name: "serial_a"
            - FakeConsoleDriver:
                name: "serial_b"
        """
        )
        e = Environment(str(p))
        t = e.get_target("test1")
