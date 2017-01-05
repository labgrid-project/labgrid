import pytest

from labgrid.provider.mediafileprovider import MediaFileProvider


class FakeMediaFileProvider(MediaFileProvider):
    def __init__(self):
        super().__init__()

        self._add_file('h264', 'sintel.mkv', '/usr/share/video/sintel.mkv')


class TestMediaFileProvider:
    def test_create(self):
        p = MediaFileProvider()
        assert (isinstance(p, MediaFileProvider))

    def test_list(self):
        p = FakeMediaFileProvider()
        p.list() == ['h264']

    def test_get(self):
        p = FakeMediaFileProvider()
        p.get('h264') == {'sintel.mkv': '/usr/share/video/sintel.mkv'}
        with pytest.raises(KeyError):
            p.get('flv')
