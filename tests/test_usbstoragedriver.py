from urllib.request import urlopen

import pytest

from labgrid.binding import BindingState
from labgrid.driver.usbstoragedriver import Mode, USBStorageDriver
from labgrid.driver.exception import ExecutionError
from labgrid.resource.common import Resource
from labgrid.resource.remote import NetworkUSBMassStorage
from labgrid.util.managedfile import ManagedFile


@pytest.fixture
def driver(target, mocker):
    storage = NetworkUSBMassStorage(
        target, None, host='exporter', busnum=1, devnum=1,
        path='/dev/fake', vendor_id=1, model_id=1,
    )
    driver = USBStorageDriver(target, None)
    driver.state = BindingState.active
    mocker.patch.object(driver, '_wait_for_medium')
    connection = mocker.patch('labgrid.driver.usbstoragedriver.sshmanager.open').return_value
    # Mirror the forward locally so the mocked command can fetch the real HTTP URL.
    connection.add_remote_port_forward.side_effect = lambda remote, local, **kw: local
    return driver, storage, connection


@pytest.mark.parametrize('with_bmap', [True, False])
@pytest.mark.parametrize('fail', [True, False])
def test_streaming_skips_image_sync_and_cleans_up(driver, tmp_path, mocker, with_bmap, fail):
    drv, storage, connection = driver
    image = tmp_path / 'image.wic.gz'
    image.write_bytes(b'image contents')
    bmap = tmp_path / 'image.wic.bmap'
    if with_bmap:
        bmap.write_text('map contents')
    synced = []

    def sync(mf):
        synced.append(mf.local_path)
        mf.rpath = '/cache/'

    mocker.patch.object(ManagedFile, 'sync_to_resource', sync)
    urls = []

    def run(resource, args, **kwargs):
        assert resource is storage
        assert args[:2] == ['bmaptool', 'copy']
        assert args[3] == '/dev/fake2'
        assert args[4] == ('--bmap=/cache/image.wic.bmap' if with_bmap else '--nobmap')
        urls.append(args[2])
        with urlopen(args[2], timeout=5) as response:
            assert response.read() == image.read_bytes()
        if fail:
            raise ExecutionError('write failed')

    mocker.patch('labgrid.driver.usbstoragedriver.processwrapper.check_wrapped_output', run)
    if fail:
        with pytest.raises(ExecutionError, match='write failed'):
            drv.write_image(str(image), Mode.BMAPTOOL_STREAMING, partition=2)
    else:
        drv.write_image(str(image), Mode.BMAPTOOL_STREAMING, partition=2)

    assert synced == ([str(bmap)] if with_bmap else [])
    port = connection.add_remote_port_forward.call_args.args[1]
    connection.add_remote_port_forward.assert_called_once_with(0, port, remote_bind='127.0.0.1')
    connection.remove_remote_port_forward.assert_called_once_with(port, port, remote_bind='127.0.0.1')
    with pytest.raises(OSError):
        urlopen(urls[0], timeout=5)


@pytest.mark.parametrize('proxy_required', [False, True])
def test_streaming_tunnel_uses_command_endpoint(driver, tmp_path, mocker, proxy_required):
    drv, storage, connection = driver
    storage.extra = {'proxy': 'proxy-exporter', 'proxy_required': proxy_required}
    image = tmp_path / 'image.wic'
    image.write_bytes(b'image')
    open_connection = mocker.patch(
        'labgrid.driver.usbstoragedriver.sshmanager.open', return_value=connection,
    )

    with drv._image_path(str(image), Mode.BMAPTOOL_STREAMING) as url:
        with urlopen(url, timeout=5) as response:
            assert response.read() == b'image'

    open_connection.assert_called_once_with('proxy-exporter' if proxy_required else 'exporter')
    connection.remove_remote_port_forward.assert_called_once()


@pytest.mark.parametrize('mode', [Mode.DD, Mode.BMAPTOOL])
def test_existing_modes_sync_image(driver, tmp_path, mocker, mode):
    drv, _, connection = driver
    image = tmp_path / 'image.wic'
    image.write_bytes(b'image')
    sync = mocker.patch.object(ManagedFile, 'sync_to_resource')
    mocker.patch.object(ManagedFile, 'get_remote_path', return_value='/cache/image.wic')
    command = mocker.patch('labgrid.driver.usbstoragedriver.processwrapper.check_wrapped_output')

    drv.write_image(str(image), mode)

    sync.assert_called_once()
    connection.add_remote_port_forward.assert_not_called()
    args = command.call_args.args[1]
    assert '/cache/image.wic' in args if mode == Mode.BMAPTOOL else 'if=/cache/image.wic' in args


def test_local_streaming_does_not_open_tunnel(driver, tmp_path):
    drv, _, connection = driver
    drv.storage = Resource(None, None)
    image = tmp_path / 'image.wic'
    image.write_bytes(b'image')

    with drv._image_path(str(image), Mode.BMAPTOOL_STREAMING) as url:
        with urlopen(url, timeout=5) as response:
            assert response.read() == b'image'

    connection.add_remote_port_forward.assert_not_called()


@pytest.mark.parametrize('argument', ['skip', 'seek'])
def test_streaming_rejects_offsets(driver, tmp_path, argument):
    drv, _, _ = driver
    image = tmp_path / 'image.wic'
    image.write_bytes(b'image')
    with pytest.raises(ExecutionError, match='does not support skip or seek'):
        drv.write_image(str(image), Mode.BMAPTOOL_STREAMING, **{argument: 1})
