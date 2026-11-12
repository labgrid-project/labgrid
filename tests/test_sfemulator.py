from labgrid.resource.udev import SFEmulator
from labgrid.resource.remote import NetworkSFEmulator
from labgrid.driver.sfemulatordriver import SFEmulatorDriver


def test_sfemulator_network_create(target):
    r = NetworkSFEmulator(target, name=None, host='localhost', busnum=3,
                          devnum=12, path='1-3', vendor_id=0x04b4,
                          model_id=0x1235, chip='W25Q64CV')
    assert isinstance(r, NetworkSFEmulator)
    assert r.chip == 'W25Q64CV'

    d = SFEmulatorDriver(target, name=None)
    assert isinstance(d, SFEmulatorDriver)


def test_sfemulator_driver_create(target):
    r = SFEmulator(target, name=None, match={'ID_PATH': 'pci-0000:00:14.0-usb-0:3'},
                   chip='W25Q64CV')
    assert isinstance(r, SFEmulator)

    d = SFEmulatorDriver(target, name=None)
    assert isinstance(d, SFEmulatorDriver)


def test_sfemulator_driver_write(target, mocker, tmpdir):
    r = SFEmulator(target, name=None, match={'ID_PATH': 'pci-0000:00:14.0-usb-0:3'},
                   chip='W25Q64CV')
    d = SFEmulatorDriver(target, name=None)
    r.avail = True
    target.activate(d)

    mocker.patch.object(SFEmulator, 'busnum', new_callable=mocker.PropertyMock,
                        return_value=3)
    mocker.patch.object(SFEmulator, 'devnum', new_callable=mocker.PropertyMock,
                        return_value=12)

    image = tmpdir.join('image.bin').strpath
    with open(image, 'wb') as outf:
        outf.write(b'image data')

    pwrap = mocker.patch('labgrid.driver.sfemulatordriver.processwrapper')

    d.write_image(image)
    pwrap.check_output.assert_called_once_with(
        ['em100', '--device', '3:12', '-s', '-p', 'LOW', '-c', 'W25Q64CV',
         '-d', image, '-r'])
