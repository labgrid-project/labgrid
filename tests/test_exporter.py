import asyncio

import attr
import pytest

from labgrid.remote.common import ResourceEntry
from labgrid.remote.exporter import Exporter, ResourceExport


@attr.s(eq=False)
class FailingPollResourceExport(ResourceExport):
    def poll(self):
        raise RuntimeError("poll failed")


def make_exporter_with_resource(resource):
    exporter = Exporter.__new__(Exporter)
    exporter.out_queue = asyncio.Queue()
    exporter.groups = {"Testport": {"NetworkSerialPort": resource}}
    return exporter


def test_exporter_release_already_free_resource_succeeds():
    async def release_resource():
        resource = ResourceEntry(
            {
                "cls": "NetworkSerialPort",
                "params": {},
                "acquired": None,
                "avail": True,
            }
        )
        exporter = make_exporter_with_resource(resource)

        await exporter.release("Testport", "NetworkSerialPort")

        update = exporter.out_queue.get_nowait()
        assert update.resource.acquired == ""

    asyncio.run(release_resource())


def test_resource_export_release_restores_acquired_when_poll_fails():
    exported_resource = FailingPollResourceExport(
        {
            "cls": "NetworkSerialPort",
            "params": {},
            "acquired": "test",
            "avail": True,
        }
    )

    with pytest.raises(RuntimeError, match="poll failed"):
        exported_resource.release()

    assert exported_resource.acquired == "test"
