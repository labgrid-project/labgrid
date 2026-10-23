import argparse
import warnings

import pexpect
import pytest
import asyncio
import grpc
import signal
import sys
import textwrap
import time

from labgrid import Environment, Target
from labgrid.driver import NetworkPowerDriver, SSHDriver, SerialDriver
from labgrid.remote.common import Place, ResourceEntry, get_client_credentials, get_metadata_single_value_by_key
from labgrid.remote.coordinator import get_server_credentials
from labgrid.remote.exporter import Exporter, SerialPortExport
from labgrid.remote.generated import labgrid_coordinator_pb2
from labgrid.remote.generated import labgrid_coordinator_pb2_grpc
from labgrid.resource import NetworkPowerPort, NetworkSerialPort, NetworkService, RawSerialPort, RemotePlace
from labgrid.util.yaml import dump


def test_client_help():
    with pexpect.spawn(f"{sys.executable} -m labgrid.remote.client --help") as spawn:
        spawn.expect("usage")
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None


def test_exporter_help():
    with pexpect.spawn(f"{sys.executable} -m labgrid.remote.exporter --help") as spawn:
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

    with pexpect.spawn(f"{sys.executable} -m labgrid.remote.exporter {config}", cwd=tmpdir) as spawn:
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


def setup_tmp_cert_key(tmpdir):
    cert = "cert.pem"
    cert_file = tmpdir.join(cert)
    cert_file.write(
        """-----BEGIN CERTIFICATE-----
MIIGXjCCBEagAwIBAgIUbB+eM8qxEoxQX/KptIJArd7oyhMwDQYJKoZIhvcNAQEL
BQAwgaExCzAJBgNVBAYTAkdCMRIwEAYDVQQIDAlTb21lU3RhdGUxETAPBgNVBAcM
CFNvbWVDaXR5MRQwEgYDVQQKDAtTb21lQ29tcGFueTEXMBUGA1UECwwOU29tZURl
cGFydG1lbnQxEjAQBgNVBAMMCWxvY2FsaG9zdDEoMCYGCSqGSIb3DQEJARYZZW1h
aWwuYWRkcmVzc0Bjb21wYW55LmNvbTAeFw0yNTEyMDUxNDE5MjdaFw0zNTEyMDMx
NDE5MjdaMIGhMQswCQYDVQQGEwJHQjESMBAGA1UECAwJU29tZVN0YXRlMREwDwYD
VQQHDAhTb21lQ2l0eTEUMBIGA1UECgwLU29tZUNvbXBhbnkxFzAVBgNVBAsMDlNv
bWVEZXBhcnRtZW50MRIwEAYDVQQDDAlsb2NhbGhvc3QxKDAmBgkqhkiG9w0BCQEW
GWVtYWlsLmFkZHJlc3NAY29tcGFueS5jb20wggIiMA0GCSqGSIb3DQEBAQUAA4IC
DwAwggIKAoICAQCwISW6WyB2jw6NT4m14BXHjrQE/grXd8TDRTlVNasMGf2TVWmr
y+HTqy0xI6mmcyvh7rPw+kY57qLGJdhISB44ayXbMbWYdSkhb/qBmG9NgH9J4OBX
1yajmi6elgqYTm+9o7CvhyFcF2lcMPy9a8JRADrwucK5L5wuXXVEvqCjWToq2xP4
Qiujdh/CRB0kV/nvwGKsn1rX9SU3JxvP6oMdb0mq9Xp90Wx/5CMzZq8dNrHFCxda
IVhdZcPqRY9yft/K6V9ARJARcl9c6+1gCfZc2uqMLuLVjkrn0UFq06q28n2JvkRP
NC2TmIH82+bhsVolXeO62m8V/VekXT16NCB/cl0HXTVTa37r7qFadFhBGP7uoZy8
TyUhEiumt55N4MCyQMbqXXCT8ypserVL325v4/THyr/vFtLvpLSCayDB2diOe4Ii
s4I0M6dhmF2/ThtwNbWurC25RKYGjBV0gaCe96nG8LxKOb2nYdEI+LOOajJyrd+o
SwPvTgpHcJF4+NP+E8t+QJ5jO1s/geelPqxCEdk6GHXnwWBKiIeY8Lm/wj8O5PH4
SfIMxhapFUIdf9Y5thtLkmcW73k7mEQy7Vqy4RTHvgH0wwAdAO93luci4YVDpmml
G9n1Xg1u5H6hNsn8/D72LBcZvHMfxmjXQPzYaLJb6J5WGADgJzh+yr6EPwIDAQAB
o4GLMIGIMA4GA1UdDwEB/wQEAwIDiDAMBgNVHRMEBTADAQH/MEkGA1UdEQRCMECC
EHNvbWUtY29tcGFueS5jb22CCWxvY2FsaG9zdIIJMTI3LjAuMC4xhwR/AAABhxAA
AAAAAAAAAAAAAAAAAAABMB0GA1UdDgQWBBSV9hF1IhJg+XzkNlMuUsWvaWqhmjAN
BgkqhkiG9w0BAQsFAAOCAgEAcXVn1pCkMDf++z9IQAQOZHdsDklJY0yHSKpnZwd5
XF+lZZlW4OiY6Ednj5nJsXYImhqEJiCWyVYUu/CDzHvFNUVLa1Eav9lHqPhpAZtg
FEjYenEmdcklYDuooGn1Mp7zM0QO442rVAluy65GZSBZw2XF07bvHBqCLLhiYjXi
t8fBe2r4UJ/pv4mpVLQ1tuDYJ3ObH/DQ/nxHRpwFuDobU7Xm0nIBhvtlbvPgddFF
kam3zLwgOQkxVbu5i4k893KwQ9HHLmHath5go/iNx8A5Je3cQqUusY35KWN4sa+K
tGzhuL4xTUKjCvTygSu3KCEvFTafCgCQSA/dM3h1gAnz5STUGUUSS4lxDXWswSI7
S914+8kLkTQ5eKbYWc6LAfNFaUFSPaUqYveWvHZ9K0pQZ/4RPH+JJJ7BCC9J6h+a
bAW6BniHsn4SNtT8AqQN3MVwgHcA4EvoBP2frIO1SWrL8/dRC5hz1yDcMtCemFSB
X/LMdSgjsS5Re4sqeTyYI7u24HxDc/+k8/MZsnI5l2ZezE11KpI30TxWgoSWGmjM
WXNpODmLLad5CatK4Yh6G0Aza+QiUc13R8vbftjWWT6kcf07+AxN193Z06ZMNIoj
igUfKt9THGeZvEUW4G9G/nKD1uT0p4re3NVTibUEs86WOKIJExGXZyAEvovkAS8D
ez4=
-----END CERTIFICATE-----
"""
    )

    key = "key.pem"
    key_file = tmpdir.join(key)
    key_file.write(
        """-----BEGIN PRIVATE KEY-----
MIIJQwIBADANBgkqhkiG9w0BAQEFAASCCS0wggkpAgEAAoICAQCwISW6WyB2jw6N
T4m14BXHjrQE/grXd8TDRTlVNasMGf2TVWmry+HTqy0xI6mmcyvh7rPw+kY57qLG
JdhISB44ayXbMbWYdSkhb/qBmG9NgH9J4OBX1yajmi6elgqYTm+9o7CvhyFcF2lc
MPy9a8JRADrwucK5L5wuXXVEvqCjWToq2xP4Qiujdh/CRB0kV/nvwGKsn1rX9SU3
JxvP6oMdb0mq9Xp90Wx/5CMzZq8dNrHFCxdaIVhdZcPqRY9yft/K6V9ARJARcl9c
6+1gCfZc2uqMLuLVjkrn0UFq06q28n2JvkRPNC2TmIH82+bhsVolXeO62m8V/Vek
XT16NCB/cl0HXTVTa37r7qFadFhBGP7uoZy8TyUhEiumt55N4MCyQMbqXXCT8yps
erVL325v4/THyr/vFtLvpLSCayDB2diOe4Iis4I0M6dhmF2/ThtwNbWurC25RKYG
jBV0gaCe96nG8LxKOb2nYdEI+LOOajJyrd+oSwPvTgpHcJF4+NP+E8t+QJ5jO1s/
geelPqxCEdk6GHXnwWBKiIeY8Lm/wj8O5PH4SfIMxhapFUIdf9Y5thtLkmcW73k7
mEQy7Vqy4RTHvgH0wwAdAO93luci4YVDpmmlG9n1Xg1u5H6hNsn8/D72LBcZvHMf
xmjXQPzYaLJb6J5WGADgJzh+yr6EPwIDAQABAoICACqKnxe/ifxI+n1UUFFfQjN0
uvOXvtujYKG/tyTnNRzTrEVpdIAb2zxqlJxRXllHaTqFku3qLYsxohxVKMPws2fy
LW8ftxqPdfNPHkUuIfgoyNX53IYq//i1NXx1hjKag2/dOUB0VbDuMLMlW+6OuB0j
fpkFbUyYfNNQHJKRrrA1zZBrYQvuQ6cUUYB1Pkq4ezSXFd5XETSnUCldp2CVZrz1
0+fYqhD4xAmx+3SfYT2fp9mNn8LT2gmZGnSb/5VqorhanPijdt7X7sO9cpTnYxuz
fsKEUqK9X0dV6kSYwpu0v3DFRa+RzU5goEkIfmBWG415+5b2yq0Xh5M6OC6rp4tq
VFLfl9qfatQpVVYAMGMidK76Fed09DzvmF6VI+dvQyE5k/yC1PKUDmpp7bDTet5r
H/IB3m7+C2xmw+FbDNajILaBRY6qz9oSmVt2lewBw1tQbp4A8KUHIBJCXhXt2oTN
3cuNW1QbccXxqdLNzGIwCJtnbDbSr6bqIqwlXHBQg5wwjFecgtOhb3b62Dsc/hGV
JUVBPpSNpVn3kBkC0DpIPIvBWXI6IyjtMoTGkY4cQ1wtzOzkGar8ze0bjYf7jz8+
2rYmH5o3AZNsyK0FOft1L9yfl/3+SCkfESCRlFjyUatnZuR9C9kck02x2XC9TVNJ
APZUlozGh65Ib+ANwRxFAoIBAQDdS2oyIA9gOn9dFYZ2BQmB+wvvJrOSuAX1vkhs
Jt9s5rFt1/oKoeMX1lAAhmUkeNcQorhuk7aowjg1R3aQe4rD2tyfxpRZz7avCdDh
od4p3JaTPwded1uygUZ2Bd/HtTxFetGs0tdwL9m9jqj+MLsr63KxytoLz/ZIwKaU
rKfUf8UJd8HNhSu68qabx8dooHY0DDwaHb9AW98sm3pmBLxMXQObyDqs+0xQQ7tA
jibmlXOJeh+4IM8EJorkNHGR2/8+Qrc1RtVUkMsQaf3rJjP8lsjQWpsrhZr+tuz9
8t5CIqtETgX5y0jAlbh838DYyNE0DzLibdQJoGl/kkiCkjTdAoIBAQDLwG8Bdbr0
bsc2PLtc0mQjntNgp702qWHJbxZ7O1Nkvt3CS/PYCSfBdgRb15tjgyvXF0V72OL5
xXnCTfxByhXHjr4HPDdQH3YcpQkwx8Gs4TP15c6Z9miSYF8cGHy0Boc7L47JbK/+
xVtozB+R/HczI08Ak0T0FTo9MagJ96m4/IAyMP7QrkRQXftDHKxWSi4PtgE6TlQm
QniGVU+iZ15bkLaqbaWnCHF8JfErRrdcEtRWtVO3j0X6n5lmPO6hYUVtkNVapuK+
MS3SJeqF5vnCY+86rE4oSIZG0Q8njVBMmM0KHbijLHKSLANIe2ujsS83/0fS1g7w
r2M0q2Modu3LAoIBAQCWv/ou/WIcFp2O5sv7eAD7F+8QUpf/+fatapvheTW49Qqn
nnqKZa/THD7RrLwX9W3kukTTpzLGkdBCk1U0pcRpGZ40Bc4nxHVZlmFCY8d5UvkM
g+JcOwkveBts6SGB5XeSiVFu3w6+MQqutBFxX/cRu0odzeduJpRLCVoxa9DE1OmA
QqG2hOK+bvCKrLSuFKmRWUhULjGMAUnuFFh0SQORLcf4hpVaI7Lf9tQH7Q6ZA/R6
EcSr5UXBORRi00sOpwShAEfYNlG7UwvSObItT5AYoQtZzG9qXZCxtiGJ+bno6b8s
P86YVSBReWz9PFweEedaBISQdWr9x9Y2fouAz2LNAoIBACoAg2GjqWSWKY7uuhkK
bgZByYVVTtYj2LqzocjJlAlip0hUa/IPARkKgR+FtMywz6rJa1N6hF/E67K4bNYL
GK5IqLfJHAXyVmDVTK23oB9JVXLNauemOixinXinO53I8ruqtB6lvyof+RYDbkaj
6tap4rFVqpM+hQD0aZWUbnJp6utt2jmekwqWNSPCl2w6YoBunpYsa4Bvl3TpxT7P
XE436M/9RnbGcM6M68hmDYp3fzpYqudeK6jcmbzPtsmhybQqdTD40iku7ikyE8SC
tt3xx/Eqb/ox6SxUEHGw2erQXQRG2DcbBItJc2vPtYLLFdbPUzkNU4sePK8w3YIL
8j0CggEBANeOXqn8ScWyiPDiFUluO/J+BX1efO9RtMVjdczqrrid531sDWIEcw7A
y6kRvh1qW01VL5ZK+CtQG00kCU4IfMsfC+YGMvdLJo7j6pf8ia2atVBU61OJ9kaN
8hydfD8bDSfNfL6jkiGi7SYvrFd1qlC8eZgRGFo3+IPR6d9y6HEMc4/H/35xeO1X
CNU2gW8ka31bhKYwwkx775Sm8RbHJFiFF80JV6z1oOOicUZcFjjqCDgOW3LENz8f
Cw27rminu+ZSMa9bHmdrkdAnaYkEHSWJaZv/WZARxzrdAWDrdFM5VRTCirj0BIUk
yov2s6hjFo07mz1KLoarpgWSV1BTrjA=
-----END PRIVATE KEY-----
"""
    )

    return (cert_file, key_file)


def test_tls_coordinator_with_client(tmpdir):
    cert, key = setup_tmp_cert_key(tmpdir)

    with pexpect.spawn(
        f"{sys.executable} -m labgrid.remote.coordinator --tls --cert {cert} --key {key}", cwd=tmpdir
    ) as coord_spawn:
        coord_spawn.expect("INFO:root:Coordinator ready", timeout=1)

        with pexpect.spawn(
            f"{sys.executable} -m labgrid.remote.client --tls --cacert {cert} reserve abc=123", cwd=tmpdir
        ) as client_spawn:
            client_spawn.expect("  state: waiting", timeout=1)
            client_spawn.close()

        coord_spawn.close()


def test_tls_coordinator_with_exporter(tmpdir):
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

    cert, key = setup_tmp_cert_key(tmpdir)

    with pexpect.spawn(
        f"{sys.executable} -m labgrid.remote.coordinator --tls --cert {cert} --key {key}", cwd=tmpdir
    ) as coord_spawn:
        coord_spawn.expect("INFO:root:Coordinator ready", timeout=1)

        with pexpect.spawn(
            f"{sys.executable} -m labgrid.remote.exporter --tls --cacert {cert} {config}", cwd=tmpdir
        ) as exporter_spawn:
            exporter_spawn.expect(
                "add resource Testport/NetworkSerialPort: NetworkSerialPort/OrderedDict.*", timeout=1
            )
            exporter_spawn.expect("INFO:root:connected to coordinator version .*", timeout=1)
            exporter_spawn.close()

        coord_spawn.close()


def test_get_server_credentials_not_tls():
    args = {
        "tls": False,
        "cert": None,
        "key": None,
    }

    ns = argparse.Namespace(**args)
    credentials = get_server_credentials(ns)

    assert credentials is None


def test_get_server_credentials_only_key():
    args = {
        "tls": True,
        "cert": None,
        "key": "akey",
    }

    ns = argparse.Namespace(**args)

    with pytest.raises(RuntimeError):
        get_server_credentials(ns)


def test_get_server_credentials_only_cert():
    args = {
        "tls": True,
        "cert": "acert",
        "key": None,
    }

    ns = argparse.Namespace(**args)

    with pytest.raises(RuntimeError):
        get_server_credentials(ns)


def test_get_server_credentials_valid(tmpdir):
    cert_path, key_path = setup_tmp_cert_key(tmpdir)

    args = {
        "tls": True,
        "cert": cert_path,
        "key": key_path,
    }

    ns = argparse.Namespace(**args)

    creds = get_server_credentials(ns)

    assert creds is not None


def test_get_client_credentials_not_tls():
    credentials = get_client_credentials(False)

    assert credentials is None


def test_get_client_credentials_valid(tmpdir):
    cert_path, _ = setup_tmp_cert_key(tmpdir)

    creds = get_client_credentials(True, cert_path)

    assert creds is not None


def _make_remote_place_config(tmpdir, options=None):
    config = tmpdir.join("config.yaml")
    data = {"targets": {}}
    if options:
        data["options"] = options

    config.write(dump(data))

    return config


@pytest.fixture
def dummy_session(monkeypatch, isolated_resource_managers):
    """Replaces the RemotePlaceManager's coordinator session with a dummy serving the place "test"."""

    class DummySession:
        loop = None

        def __init__(self):
            self.place = Place("test")
            self.resources = {}
            self.start_kwargs = None

        def get_place(self, name):
            return self.place

        def get_target_resources(self, place):
            return self.resources

    session = DummySession()

    def start_session(address, **kwargs):
        session.start_kwargs = kwargs
        return session

    monkeypatch.setattr("labgrid.remote.client.start_session", start_session)
    return session


def _capture_remote_place_credentials(monkeypatch, tmpdir, dummy_session, *, options=None, tls_env=None):
    if tls_env is not None:
        monkeypatch.setenv("LG_COORDINATOR_TLS", tls_env)

    captured = {}

    def get_client_credentials(tls, cacert):
        captured["tls"] = tls
        captured["cacert"] = cacert
        return "credentials" if tls else None

    monkeypatch.setattr("labgrid.remote.common.get_client_credentials", get_client_credentials)

    config = _make_remote_place_config(tmpdir, options=options)
    env = Environment(str(config))
    target = Target("test", env=env)
    RemotePlace(target, name="test")

    captured["credentials"] = dummy_session.start_kwargs["credentials"]
    return captured


@pytest.mark.parametrize(
    ("options", "tls_env", "expected_tls", "expected_cacert"),
    [
        pytest.param({}, None, False, None, id="default-no-tls"),
        pytest.param({}, "true", True, None, id="tls-env-true"),
        pytest.param({}, "1", True, None, id="tls-env-1"),
        pytest.param({}, "false", False, None, id="tls-env-false"),
        pytest.param({}, "0", False, None, id="tls-env-0"),
        pytest.param({}, "", False, None, id="tls-env-empty"),
        pytest.param(
            {"coordinator_tls": True, "coordinator_cacert": "cert.pem"},
            None,
            True,
            "cert.pem",
            id="tls-config",
        ),
        pytest.param({"coordinator_tls": "TRUE"}, None, True, None, id="tls-config-string"),
        pytest.param({"coordinator_tls": False}, "true", False, None, id="config-overrides-env"),
        pytest.param({"coordinator_tls": "false"}, "true", False, None, id="config-string-overrides-env"),
    ],
)
def test_remote_place_client_credentials(
    monkeypatch, tmpdir, dummy_session, options, tls_env, expected_tls, expected_cacert
):
    cert_path, _ = setup_tmp_cert_key(tmpdir)
    assert cert_path.basename == "cert.pem"
    if expected_cacert:
        expected_cacert = str(tmpdir.join(expected_cacert))

    captured = _capture_remote_place_credentials(monkeypatch, tmpdir, dummy_session, options=options, tls_env=tls_env)

    assert captured["tls"] is expected_tls
    assert captured["cacert"] == expected_cacert
    assert captured["credentials"] == ("credentials" if expected_tls else None)


@pytest.mark.parametrize(
    ("tls_env", "expected_tls"),
    [
        pytest.param(None, False, id="tls-env-unset"),
        pytest.param("true", True, id="tls-env-true"),
        pytest.param("1", True, id="tls-env-1"),
        pytest.param("false", False, id="tls-env-false"),
        pytest.param("0", False, id="tls-env-0"),
        pytest.param("", False, id="tls-env-empty"),
    ],
)
def test_client_parser_tls_env_default(monkeypatch, tls_env, expected_tls):
    from labgrid.remote.client import get_parser

    if tls_env is not None:
        monkeypatch.setenv("LG_COORDINATOR_TLS", tls_env)

    args = get_parser().parse_args(["places"])

    assert args.tls is expected_tls


def test_client_parser_tls_flag_overrides_false_env(monkeypatch):
    from labgrid.remote.client import get_parser

    monkeypatch.setenv("LG_COORDINATOR_TLS", "false")
    args = get_parser().parse_args(["--tls", "places"])

    assert args.tls is True


def test_get_metadata_single_value_by_key_returns_value_for_existing_key():
    metadata = [("key1", "value1"), ("key2", "value2")]
    assert get_metadata_single_value_by_key(metadata, "key1") == "value1"
    assert get_metadata_single_value_by_key(metadata, "key2") == "value2"


def test_get_metadata_single_value_by_key_returns_none_for_missing_key():
    metadata = [("key1", "value1")]
    assert get_metadata_single_value_by_key(metadata, "other") is None


def test_get_metadata_single_value_by_key_returns_none_for_empty_metadata():
    assert get_metadata_single_value_by_key((), "key") is None


def test_get_metadata_single_value_by_key_returns_none_for_none_metadata():
    assert get_metadata_single_value_by_key(None, "key") is None


def test_get_metadata_single_value_by_key_returns_first_value_on_duplicate_keys():
    metadata = [("key", "first"), ("key", "second")]
    with pytest.warns(UserWarning, match="Multiple metadata KV pairs"):
        result = get_metadata_single_value_by_key(metadata, "key")
        assert result == "first"


def test_get_metadata_single_value_by_key_no_warning_on_single_match():
    metadata = [("key", "value")]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_metadata_single_value_by_key(metadata, "key")
        assert len(caught) == 0


def test_get_metadata_single_value_by_key_returns_first_value_for_non_adjacent_duplicates():
    metadata = [("key", "first"), ("other", "value"), ("key", "second")]
    with pytest.warns(UserWarning, match="Multiple metadata KV pairs"):
        result = get_metadata_single_value_by_key(metadata, "key")
        assert result == "first"


def test_get_metadata_single_value_by_key_is_case_sensitive():
    metadata = [("Key", "value")]
    assert get_metadata_single_value_by_key(metadata, "key") is None
    assert get_metadata_single_value_by_key(metadata, "Key") == "value"


def test_remote_place_config_drivers_bind(dummy_session):
    # bind remote place config's SerialDriver to matched NetworkSerialPort resource
    # bind remote place config's SSHDriver to remote place config's NetworkService resource
    dummy_session.resources[("console", "NetworkSerialPort")] = ResourceEntry(
        {"cls": "NetworkSerialPort", "params": {"host": "localhost", "port": 2342}, "avail": True}
    )
    dummy_session.place.remote_place_config = textwrap.dedent(
        """\
             resources:
               NetworkService:
                 address: "localhost"
                 username: "root"
             drivers:
               SerialDriver: {}
               SSHDriver: {}
        """
    )

    target = Target("test")
    RemotePlace(target, name="test")

    serial_driver = target.get_driver(SerialDriver, activate=False)
    assert serial_driver.port is target.get_resource(NetworkSerialPort, wait_avail=False)
    ssh_driver = target.get_driver(SSHDriver, activate=False)
    assert ssh_driver.networkservice is target.get_resource(NetworkService, wait_avail=False)


def test_remote_place_config_environment(dummy_session, tmpdir, caplog):
    # matched resource
    dummy_session.resources[("power", "NetworkPowerPort")] = ResourceEntry(
        {"cls": "NetworkPowerPort", "params": {"model": "gude", "host": "localhost", "index": 1}, "avail": True}
    )
    # remote place config:
    dummy_session.place.remote_place_config = textwrap.dedent(
        """\
            resources:
              NetworkService:
                address: "192.168.1.42"
                username: "root"
            drivers:
              SerialDriver: {}
            options:
              shared-option: "remote"
              remote-option: 23
        """
    )
    # local environment config
    config = tmpdir.join("env.yaml")
    config.write(
        textwrap.dedent(
            """\
            targets:
              main:
                resources:
                  # defined before RemotePlace, so remote place config's SerialDriver can bind to it
                  RawSerialPort:
                    port: "/dev/ttyUSB0"
                  RemotePlace:
                    name: "test"
                drivers:
                  NetworkPowerDriver: {}
                  SSHDriver: {}
                options:
                  shared-option: "local"
                  local-option: 42
            """
        )
    )

    target = Environment(str(config)).get_target()

    # env config's NetworkPowerDriver binds to matched NetworkPowerPort resource
    power_driver = target.get_driver(NetworkPowerDriver, activate=False)
    assert power_driver.port is target.get_resource(NetworkPowerPort, wait_avail=False)

    # env config's SSHDriver binds to remote place config's NetworkService resource
    ssh_driver = target.get_driver(SSHDriver, activate=False)
    assert ssh_driver.networkservice is target.get_resource(NetworkService, wait_avail=False)

    # remote place config's SerialDriver binds to local RawSerialPort resource
    serial_driver = target.get_driver(SerialDriver, activate=False)
    assert serial_driver.port is target.get_resource(RawSerialPort, wait_avail=False)

    # local options take precedence over the remote place config's options
    assert "ignoring remote place config option 'shared-option' of place test, environment config takes precedence" in caplog.text
    assert target.options == {"shared-option": "local", "remote-option": 23, "local-option": 42}


@pytest.mark.parametrize(
    ("ignore_resources", "expected_resources"),
    [
        pytest.param(
            [],  # ignore nothing
            {"NetworkService:eth0", "NetworkService:eth1", "NetworkPowerPort:power"},  # nothing ignored
            id="none",
        ),
        pytest.param(
            ["NetworkService"],  # ignore existent resource class
            {"NetworkPowerPort:power"},  # both NetworkServices ignored
            id="class",
        ),
        pytest.param(
            ["NetworkService:eth1"],  # ignore existent resource by class:name
            {"NetworkService:eth0", "NetworkPowerPort:power"},  # only eth1 ignored
            id="class:name",
        ),
        pytest.param(
            ["InexistentResource"],  # ignore inexistent resource class
            {"NetworkService:eth0", "NetworkService:eth1", "NetworkPowerPort:power"},  # nothing ignored
            id="inexistent-class",
        ),
        pytest.param(
            ["NetworkService:foo"],  # ignore inexistent resource class/name combination
            {"NetworkService:eth0", "NetworkService:eth1", "NetworkPowerPort:power"},  # nothing ignored
            id="inexistent-class:name",
        ),
    ],
)
def test_remote_place_ignore_resources(dummy_session, ignore_resources, expected_resources):
    # matched resources should never be ignored, so add one and make sure it's always in the target's resources
    dummy_session.resources[("console", "NetworkSerialPort")] = ResourceEntry(
        {"cls": "NetworkSerialPort", "params": {"host": "localhost", "port": 4000}, "avail": True}
    )
    dummy_session.place.remote_place_config = textwrap.dedent(
        """\
            resources:
            - NetworkService:
                name: "eth0"
                address: "192.168.1.42"
                username: "root"
            - NetworkService:
                name: "eth1"
                address: "192.168.2.42"
                username: "root"
            - NetworkPowerPort:
                name: "power"
                model: "gude"
                host: "192.168.1.2"
                index: 1
        """
    )

    target = Target("test")
    RemotePlace(target, name="test", ignore_resources=ignore_resources)

    resources = {f"{resource.__class__.__name__}:{resource.name}" for resource in target.resources}
    assert resources == {"RemotePlace:test", "NetworkSerialPort:console"} | expected_resources


@pytest.mark.parametrize(
    ("ignore_drivers", "expected_drivers"),
    [
        pytest.param(
            [],  # ignore nothing
            {"SerialDriver:console", "ManualPowerDriver:power1", "ManualPowerDriver:power2"},  # nothing ignored
            id="none",
        ),
        pytest.param(
            ["ManualPowerDriver"],  # ignore existent driver class
            {"SerialDriver:console"},  # both ManualPowerDrivers ignored
            id="class",
        ),
        pytest.param(
            ["ManualPowerDriver:power2"],  # ignore existent driver by class:name
            {"SerialDriver:console", "ManualPowerDriver:power1"},  # only power2 ignored
            id="class:name",
        ),
        pytest.param(
            ["InexistentDriver"],  # ignore inexistent driver class
            {"SerialDriver:console", "ManualPowerDriver:power1", "ManualPowerDriver:power2"},  # nothing ignored
            id="inexistent-class",
        ),
        pytest.param(
            ["SerialDriver:foo"],  # ignore inexistent driver class/name combination
            {"SerialDriver:console", "ManualPowerDriver:power1", "ManualPowerDriver:power2"},  # nothing ignored
            id="inexistent-class:name",
        ),
    ],
)
def test_remote_place_ignore_drivers(dummy_session, ignore_drivers, expected_drivers):
    # the SerialDriver from the config binds to a matched NetworkSerialPort resource
    dummy_session.resources[("console", "NetworkSerialPort")] = ResourceEntry(
        {"cls": "NetworkSerialPort", "params": {"host": "localhost", "port": 4000}, "avail": True}
    )
    dummy_session.place.remote_place_config = textwrap.dedent(
        """\
            drivers:
            - SerialDriver:
                name: "console"
            - ManualPowerDriver:
                name: "power1"
            - ManualPowerDriver:
                name: "power2"
        """
    )

    target = Target("test")
    RemotePlace(target, name="test", ignore_drivers=ignore_drivers)

    drivers = {f"{driver.__class__.__name__}:{driver.name}" for driver in target.drivers}
    assert drivers == expected_drivers
