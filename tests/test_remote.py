import pexpect
import pytest
import asyncio
import grpc

from labgrid.remote.exporter import Exporter, SerialPortExport


def test_client_help():
    with pexpect.spawn("python -m labgrid.remote.client --help") as spawn:
        spawn.expect("usage")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None


def test_exporter_help():
    with pexpect.spawn("python -m labgrid.remote.exporter --help") as spawn:
        spawn.expect("usage")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None


def test_exporter_start_coordinator_unreachable(monkeypatch, tmpdir):
    monkeypatch.setenv("LG_COORDINATOR", "coordinator.invalid")

    config = "exports.yaml"
    p = tmpdir.join(config)
    p.write(
        """
    Testport:
        NetworkSerialPort:
          host: 'localhost'
          port: 4000
    """
    )

    with pexpect.spawn(f"python -m labgrid.remote.exporter {config}", cwd=tmpdir) as spawn:
        spawn.expect("coordinator is unavailable", timeout=10)
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 100, spawn.before


def test_serial_port_export_del_before_child_init():
    export = object.__new__(SerialPortExport)

    export.__del__()


def test_exporter_message_pump_propagates_grpc_error():
    class FailingStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise grpc.aio.AioRpcError(
                grpc.StatusCode.ALREADY_EXISTS,
                details="exporter already exists",
            )

    async def run():
        exporter = object.__new__(Exporter)
        exporter.out_queue = asyncio.Queue()
        exporter.stub = type(
            "Stub",
            (),
            {"ExporterStream": lambda self, request: FailingStream()},
        )()

        with pytest.raises(grpc.aio.AioRpcError) as excinfo:
            await exporter.message_pump()

        assert excinfo.value.code() is grpc.StatusCode.ALREADY_EXISTS

    asyncio.run(run())


def test_exporter_coordinator_becomes_unreachable(coordinator, exporter):
    coordinator.suspend_tree()

    exporter.spawn.expect(pexpect.EOF, timeout=30)
    exporter.spawn.close()
    assert exporter.exitstatus == 100

    coordinator.resume_tree()


def test_exporter_nfs_provider_export():
    # Regression test: NFSProvider has no internal/external attrs (unlike
    # TFTPProvider/HTTPProvider), so it must not be mapped to
    # ProviderGenericExport or _get_params() raises an AttributeError.
    from labgrid.remote.exporter import exports

    export_cls = exports["NFSProvider"]
    resource = export_cls({"cls": "NFSProvider", "params": {}}, host="exporterhost")

    resource.poll()

    assert resource.params["host"] == "exporterhost"
    assert "internal" not in resource.params
    assert "external" not in resource.params
