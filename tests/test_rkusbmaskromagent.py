from labgrid.util.agents.rkusbmaskrom import (crc16_ccitt_false, rc4_ksa,
                                              rc4_prga)


def test_crc16_ccitt_false():
    crc = crc16_ccitt_false("123456789".encode())
    assert crc == 0x29b1


def test_rc4_keystream():
    # from RFC 6229: Test Vectors for the Stream Cipher RC4
    key = list(bytes.fromhex("1ada31d5cf688221c109163908ebe51debb46227c6cc8b37641910833222772a"))
    keystream = rc4_prga(rc4_ksa(key))
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("dd5bcb0018e922d494759d7c395d02d3"))
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("c8446f8f77abf737685353eb89a1c9eb"))
    for _ in range(4048):
        next(keystream)
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("d5a39e3dfcc50280bac4a6b5aa0dca7d"))
    assert [next(keystream) for _ in range(16)] == list(bytes.fromhex("370b1c1fe655916d97fd0d47ca1d72b8"))
