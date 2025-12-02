import argparse
import pexpect
import pytest
from labgrid.remote.coordinator import get_server_credentials
from labgrid.remote.common import get_client_credentials

def test_client_help():
    with pexpect.spawn('python -m labgrid.remote.client --help') as spawn:
        spawn.expect('usage')
        spawn.expect(pexpect.EOF)
        spawn.close()
        assert spawn.exitstatus == 0
        assert spawn.signalstatus is None

def test_exporter_help():
    with pexpect.spawn('python -m labgrid.remote.exporter --help') as spawn:
        spawn.expect('usage')
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

def test_exporter_coordinator_becomes_unreachable(coordinator, exporter):
    coordinator.suspend_tree()

    exporter.spawn.expect(pexpect.EOF, timeout=30)
    exporter.spawn.close()
    assert exporter.exitstatus == 100

    coordinator.resume_tree()

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
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
yov2s6hjFo07mz1KLoarpgWSV1BTrjA=
-----END PRIVATE KEY-----
"""
    )

    return (cert_file, key_file)

def test_secure_coordinator_with_client(tmpdir):
    cert, key = setup_tmp_cert_key(tmpdir)

    with pexpect.spawn(f'python -m labgrid.remote.coordinator --secure --cert {cert} --key {key}', cwd=tmpdir) as coord_spawn:
        coord_spawn.expect("INFO:root:Coordinator ready", timeout=1)

        with pexpect.spawn(f'python -m labgrid.remote.client --secure --cert {cert} reserve abc=123', cwd=tmpdir) as client_spawn:
            client_spawn.expect("  state: waiting", timeout=1)
            client_spawn.close()

        coord_spawn.close()

def test_secure_coordinator_with_exporter(tmpdir):
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

    with pexpect.spawn(f'python -m labgrid.remote.coordinator --secure --cert {cert} --key {key}', cwd=tmpdir) as coord_spawn:
        coord_spawn.expect("INFO:root:Coordinator ready", timeout=1)

        with pexpect.spawn(f'python -m labgrid.remote.exporter --secure --cert {cert} {config}', cwd=tmpdir) as exporter_spawn:
            exporter_spawn.expect("add resource Testport/NetworkSerialPort: NetworkSerialPort/OrderedDict.*", timeout=1)
            exporter_spawn.expect("INFO:root:connected to coordinator version .*", timeout=1)
            exporter_spawn.close()

        coord_spawn.close()

def test_get_server_credentials_not_secure():
    args = {
        "secure": False,
        "cert": None,
        "key": None,
    }

    ns = argparse.Namespace(**args)
    credentials = get_server_credentials(ns)

    assert credentials is None

def test_get_server_credentials_only_key():
    args = {
        "secure": True,
        "cert": None,
        "key": "akey",
    }

    ns = argparse.Namespace(**args)

    with pytest.raises(RuntimeError):
        get_server_credentials(ns)

def test_get_server_credentials_only_cert():
    args = {
        "secure": True,
        "cert": "acert",
        "key": None,
    }

    ns = argparse.Namespace(**args)

    with pytest.raises(RuntimeError):
        get_server_credentials(ns)

def test_get_server_credentials_valid(tmpdir):
    cert_path, key_path = setup_tmp_cert_key(tmpdir)

    args = {
        "secure": True,
        "cert": cert_path,
        "key": key_path,
    }

    ns = argparse.Namespace(**args)

    creds = get_server_credentials(ns)
    
    assert creds is not None

def test_get_client_credentials_not_secure():
    args = {
        "secure": False,
        "cert": None,
    }

    ns = argparse.Namespace(**args)
    credentials = get_client_credentials(ns)

    assert credentials is None

def test_get_client_credentials_valid(tmpdir):
    cert_path, _ = setup_tmp_cert_key(tmpdir)

    args = {
        "secure": True,
        "cert": cert_path,
    }

    ns = argparse.Namespace(**args)

    creds = get_client_credentials(ns)
    
    assert creds is not None
