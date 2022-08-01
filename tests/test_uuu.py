import pytest

from labgrid.resource import UUU
from labgrid.resource import NetworkUUU
from labgrid.driver import UniversalUpdateUtilityDriver
from labgrid import Environment


class TestUUU:
    def test_uuu_instanziation(self):
        u = UUU(None, "uuu", "3:8")
        u = UUU(None, "uuu", ["3:8"])
        with pytest.raises(Exception):
            u = UUU(None, "uuu", {"3":"8"})

    def test_network_uuu_instanziation(self):
        u = NetworkUUU(None, "uuu", "ip", "3:8")
        u = NetworkUUU(None, "uuu", "ip", ["3:8"])
        with pytest.raises(Exception):
            u = NetworkUUU(None, "uuu", "ip", {"3":"8"})


class TestUUUDriver:
    def test_uuu_cmd(self, tmpdir):
        p = tmpdir.join("uuu.yaml")
        p.write(
            """
        targets:
          example:
            resources:
              NetworkUUU:
                host: "localhost"
                usb_otg_path: "3:8"
            drivers:
              UniversalUpdateUtilityDriver: {}
        """
        )

        env = Environment(str(p))
        t = env.get_target('example')
        ud = t.get_driver('UniversalUpdateUtilityDriver')

        assert isinstance(ud, UniversalUpdateUtilityDriver)
        assert isinstance(ud.uuu, NetworkUUU)
        uuu_cmd = ud._get_uuu_cmd("-lsusb")
        uuu_cmd[10] = uuu_cmd[10].split("=")[0]
        assert uuu_cmd == [
            'ssh',
            '-tq',
            '-x',
            '-o',
            'LogLevel=ERROR',
            '-o',
            'PasswordAuthentication=no',
            '-o',
            'ControlMaster=no',
            '-o',
            'ControlPath',
            'localhost',
            '--',
            'uuu',
            '-m',
            '3:8',
            '-lsusb'
        ]
