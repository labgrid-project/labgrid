import pexpect
import pytest
import asyncio
import grpc
import signal
import sys
import time

from labgrid.remote.exporter import Exporter, SerialPortExport
from labgrid.remote.generated import labgrid_coordinator_pb2
from labgrid.remote.generated import labgrid_coordinator_pb2_grpc


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


def test_exporter_restart_after_request_failure(coordinator, tmpdir):
    name = "restart-test"
    working_config = tmpdir.join("working.yaml")
    working_config.write(
        """
    Working:
        NetworkSerialPort:
          host: 'localhost'
          port: 4000
    """
    )

    def broken_exporter_messages():
        startup = labgrid_coordinator_pb2.ExporterInMessage()
        startup.startup.version = "test"
        startup.startup.name = name
        yield startup

        # No command is pending, so this makes the coordinator request task
        # fail after it has already created the exporter session.
        response = labgrid_coordinator_pb2.ExporterInMessage()
        response.response.success = True
        yield response

    channel = grpc.insecure_channel("127.0.0.1:20408")
    stream = labgrid_coordinator_pb2_grpc.CoordinatorStub(channel).ExporterStream(
        broken_exporter_messages(), wait_for_ready=True
    )
    try:
        hello = next(stream)
        assert hello.WhichOneof("kind") == "hello"
        # The hello is sent before the coordinator consumes the request
        # iterator. Give it time to process both messages and fail the request
        # task before cancelling the stream.
        time.sleep(0.5)
    finally:
        stream.cancel()
        channel.close()

    deadline = time.monotonic() + 10
    ready = None
    last_output = b""
    while ready is None and time.monotonic() < deadline:
        exporter = pexpect.spawn(
            f"{sys.executable} -m labgrid.remote.exporter --name {name} {working_config}",
            cwd=tmpdir,
        )
        try:
            timeout = min(2, max(0.1, deadline - time.monotonic()))
            result = exporter.expect(["Exporter ready", pexpect.EOF], timeout=timeout)
            if result == 0:
                # The coordinator sends hello before checking whether the
                # exporter name already exists. Keep watching long enough for
                # a delayed ALREADY_EXISTS response.
                try:
                    # The exporter prints "Exporter ready" on the coordinator's
                    # hello, then dies from the delayed ALREADY_EXISTS roughly
                    # 40ms-1.05s later.
                    exporter.expect(pexpect.EOF, timeout=2)
                    last_output = exporter.before
                except pexpect.TIMEOUT:
                    ready = exporter
                    break
            last_output = exporter.before
        except pexpect.TIMEOUT:
            last_output = exporter.before
        finally:
            if ready is not exporter:
                if exporter.isalive():
                    exporter.kill(signal.SIGKILL)
                exporter.close()
        time.sleep(0.1)

    assert ready is not None, last_output
    ready.kill(signal.SIGTERM)
    ready.expect(pexpect.EOF, timeout=10)
    ready.close()


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
