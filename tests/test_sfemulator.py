from labgrid.resource.sfemulator import SFEmulator, NetworkSFEmulator
from labgrid.driver.sfemulatordriver import SFEmulatorDriver


def test_sfemulator_network_create(target):
    r = NetworkSFEmulator(target, name=None, serial='DP025143',
                          chip='W25Q64CV', host='localhost')
    assert isinstance(r, NetworkSFEmulator)
    assert r.serial == 'DP025143'
    assert r.chip == 'W25Q64CV'

    d = SFEmulatorDriver(target, name=None)
    assert isinstance(d, SFEmulatorDriver)


def test_sfemulator_driver_create(target):
    r = SFEmulator(target, name=None, serial='DP025143', chip='W25Q64CV')
    assert isinstance(r, SFEmulator)

    d = SFEmulatorDriver(target, name=None)
    assert isinstance(d, SFEmulatorDriver)


def test_sfemulator_driver_write(target, mocker, tmpdir):
    r = SFEmulator(target, name=None, serial='DP025143', chip='W25Q64CV')
    d = SFEmulatorDriver(target, name=None)
    r.avail = True
    target.activate(d)

    image = tmpdir.join('image.bin').strpath
    with open(image, 'wb') as outf:
        outf.write(b'image data')

    pwrap = mocker.patch('labgrid.driver.sfemulatordriver.processwrapper')

    d.write_image(image)
    pwrap.check_output.assert_called_once_with(
        ['em100', '-x', 'DP025143', '-s', '-p', 'LOW', '-c', 'W25Q64CV',
         '-d', image, '-r'])
