# Copyright 2016 Donald Stufft and individual contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import binascii
from typing import Callable, Dict, List, NamedTuple, Optional

from hypothesis import given, settings
from hypothesis.strategies import binary, sampled_from

import pytest

import nacl.bindings as b
import nacl.exceptions as exc

from .utils import read_kv_test_vectors


def chacha20poly1305_agl_vectors() -> List[Dict[str, bytes]]:
    # NIST vectors derived format
    DATA = "chacha20-poly1305-agl_ref.txt"
    return read_kv_test_vectors(DATA, delimiter=b":", newrecord=b"AEAD")


def chacha20poly1305_ietf_vectors() -> List[Dict[str, bytes]]:
    # NIST vectors derived format
    DATA = "chacha20-poly1305-ietf_ref.txt"
    return read_kv_test_vectors(DATA, delimiter=b":", newrecord=b"AEAD")


def xchacha20poly1305_ietf_vectors() -> List[Dict[str, bytes]]:
    # NIST vectors derived format
    DATA = "xchacha20-poly1305-ietf_ref.txt"
    return read_kv_test_vectors(DATA, delimiter=b":", newrecord=b"AEAD")


def aegis256_vectors() -> List[Dict[str, bytes]]:
    # NIST vectors derived format
    DATA = "aegis256.txt"
    return read_kv_test_vectors(DATA, delimiter=b":", newrecord=b"AEAD")


def aegis128l_vectors() -> List[Dict[str, bytes]]:
    # NIST vectors derived format
    DATA = "aegis128l.txt"
    return read_kv_test_vectors(DATA, delimiter=b":", newrecord=b"AEAD")


def aes256gcm_vectors() -> List[Dict[str, bytes]]:
    # NIST vectors derived format
    DATA = "aes256gcm.txt"
    return read_kv_test_vectors(DATA, delimiter=b":", newrecord=b"AEAD")


class Construction(NamedTuple):
    encrypt: Callable[[bytes, Optional[bytes], bytes, bytes], bytes]
    decrypt: Callable[[bytes, Optional[bytes], bytes, bytes], bytes]
    NPUB: int
    KEYBYTES: int


def _getconstruction(construction: bytes) -> Construction:
    if construction == b"chacha20-poly1305-old":
        encrypt = b.crypto_aead_chacha20poly1305_encrypt
        decrypt = b.crypto_aead_chacha20poly1305_decrypt
        NPUB = b.crypto_aead_chacha20poly1305_NPUBBYTES
        KEYBYTES = b.crypto_aead_chacha20poly1305_KEYBYTES
    elif construction == b"chacha20-poly1305":
        encrypt = b.crypto_aead_chacha20poly1305_ietf_encrypt
        decrypt = b.crypto_aead_chacha20poly1305_ietf_decrypt
        NPUB = b.crypto_aead_chacha20poly1305_ietf_NPUBBYTES
        KEYBYTES = b.crypto_aead_chacha20poly1305_ietf_KEYBYTES
    elif construction == b"xchacha20-poly1305":
        encrypt = b.crypto_aead_xchacha20poly1305_ietf_encrypt
        decrypt = b.crypto_aead_xchacha20poly1305_ietf_decrypt
        NPUB = b.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
        KEYBYTES = b.crypto_aead_xchacha20poly1305_ietf_KEYBYTES
    elif construction == b"aegis256":
        encrypt = b.crypto_aead_aegis256_encrypt
        decrypt = b.crypto_aead_aegis256_decrypt
        NPUB = b.crypto_aead_aegis256_NPUBBYTES
        KEYBYTES = b.crypto_aead_aegis256_KEYBYTES
    elif construction == b"aegis128l":
        encrypt = b.crypto_aead_aegis128l_encrypt
        decrypt = b.crypto_aead_aegis128l_decrypt
        NPUB = b.crypto_aead_aegis128l_NPUBBYTES
        KEYBYTES = b.crypto_aead_aegis128l_KEYBYTES
    elif construction == b"aes256gcm":
        encrypt = b.crypto_aead_aes256gcm_encrypt
        decrypt = b.crypto_aead_aes256gcm_decrypt
        NPUB = b.crypto_aead_aes256gcm_NPUBBYTES
        KEYBYTES = b.crypto_aead_aes256gcm_KEYBYTES

    return Construction(encrypt, decrypt, NPUB, KEYBYTES)


@pytest.mark.parametrize(
    "kv",
    chacha20poly1305_agl_vectors()
    + chacha20poly1305_ietf_vectors()
    + xchacha20poly1305_ietf_vectors()
    + aegis256_vectors()
    + aegis128l_vectors()
    + aes256gcm_vectors(),
)
def test_variants_kat(kv: Dict[str, bytes]):
    msg = binascii.unhexlify(kv["IN"])
    ad = binascii.unhexlify(kv["AD"])
    nonce = binascii.unhexlify(kv["NONCE"])
    k = binascii.unhexlify(kv["KEY"])
    c = _getconstruction(kv["AEAD"])
    _tag = kv.get("TAG", b"")
    exp = binascii.unhexlify(kv["CT"]) + binascii.unhexlify(_tag)
    try:
        out = c.encrypt(msg, ad, nonce, k)
        assert out == exp
    except exc.UnavailableError:
        pass


@given(
    sampled_from(
        (
            b"chacha20-poly1305-old",
            b"chacha20-poly1305",
            b"xchacha20-poly1305",
            b"aegis256",
            b"aegis128l",
            b"aes256gcm",
        )
    ),
    binary(min_size=0, max_size=100),
    binary(min_size=1, max_size=50),
    binary(min_size=32, max_size=32),
    binary(min_size=32, max_size=32),
)
@settings(deadline=None, max_examples=20)
def test_variants_roundtrip_aad(
    construction: bytes, message: bytes, aad: bytes, nonce: bytes, key: bytes
):
    c = _getconstruction(construction)
    unonce = nonce[: c.NPUB]
    ukey = key[: c.KEYBYTES]

    try:
        ct = c.encrypt(message, aad, unonce, ukey)
        pt = c.decrypt(ct, aad, unonce, ukey)

        assert pt == message
        with pytest.raises(exc.CryptoError):
            ct1 = bytearray(ct)
            ct1[0] = ct1[0] ^ 0xFF
            c.decrypt(ct1, aad, unonce, ukey)
    except exc.UnavailableError:
        pass


@given(
    sampled_from(
        (
            b"chacha20-poly1305-old",
            b"chacha20-poly1305",
            b"xchacha20-poly1305",
            b"aegis256",
            b"aegis128l",
            b"aes256gcm",
        )
    ),
    binary(min_size=0, max_size=100),
    binary(min_size=0, max_size=0),
    binary(min_size=32, max_size=32),
    binary(min_size=32, max_size=32),
)
@settings(deadline=None, max_examples=20)
def test_variants_roundtrip_no_aad(
    construction: bytes, message: bytes, aad: bytes, nonce: bytes, key: bytes
):
    c = _getconstruction(construction)
    unonce = nonce[: c.NPUB]
    ukey = key[: c.KEYBYTES]

    try:
        ct = c.encrypt(message, aad, unonce, ukey)
        pt = c.decrypt(ct, aad, unonce, ukey)

        assert pt == message
        with pytest.raises(exc.CryptoError):
            ct1 = bytearray(ct)
            ct1[0] = ct1[0] ^ 0xFF
            c.decrypt(ct1, aad, unonce, ukey)
    except exc.UnavailableError:
        pass


@pytest.mark.parametrize(
    "construction",
    [
        b"chacha20-poly1305-old",
        b"chacha20-poly1305",
        b"xchacha20-poly1305",
        b"aegis256",
        b"aegis128l",
        b"aes256gcm",
    ],
)
def test_variants_wrong_params(construction: bytes):
    c = _getconstruction(construction)
    nonce = b"\x00" * c.NPUB
    key = b"\x00" * c.KEYBYTES
    aad = None
    try:
        c.encrypt(b"", aad, nonce, key)
        # The first two checks call encrypt with a nonce/key that's too short. Otherwise,
        # the types are fine. (TODO: Should this raise ValueError rather than TypeError?
        # Doing so would be a breaking change.)
        with pytest.raises(exc.TypeError):
            c.encrypt(b"", aad, nonce[:-1], key)
        with pytest.raises(exc.TypeError):
            c.encrypt(b"", aad, nonce, key[:-1])
        # Type safety: mypy spots these next two errors, but we want to check that they're
        # spotted at runtime too.
        with pytest.raises(exc.TypeError):
            c.encrypt(b"", aad, nonce.decode("utf-8"), key)  # type: ignore[arg-type]
        with pytest.raises(exc.TypeError):
            c.encrypt(b"", aad, nonce, key.decode("utf-8"))  # type: ignore[arg-type]
    except exc.UnavailableError:
        pass


@pytest.mark.parametrize(
    "construction",
    [
        b"chacha20-poly1305-old",
        b"chacha20-poly1305",
        b"xchacha20-poly1305",
        b"aegis256",
        b"aegis128l",
        b"aes256gcm",
    ],
)
def test_variants_str_msg(construction: bytes):
    c = _getconstruction(construction)
    nonce = b"\x00" * c.NPUB
    key = b"\x00" * c.KEYBYTES
    aad = None
    try:
        with pytest.raises(exc.TypeError):
            c.encrypt("", aad, nonce, key)  # type: ignore[arg-type]
    except exc.UnavailableError:
        pass
