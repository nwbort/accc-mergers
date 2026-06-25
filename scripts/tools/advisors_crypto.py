#!/usr/bin/env python3
"""
Encryption helpers for the backend-only advisors database.

The advisors data is stored encrypted at rest as a text (JSON) file,
``data/processed/advisors.json.enc``, which is safe to commit to the public
repo. The cleartext (``advisors.json``) is gitignored and never committed.

Encryption: the cleartext JSON is encrypted with Fernet (AES-128-CBC +
HMAC-SHA256). The Fernet key is derived from a passphrase via
PBKDF2-HMAC-SHA256. The passphrase is read from the ``ADVISORS_PASSPHRASE``
environment variable — so CI / GitHub Actions can supply it as a secret
(``ADVISORS_PASSPHRASE: ${{ secrets.ADVISORS_PASSPHRASE }}``). If the env var
is not set and a terminal is attached, you are prompted for it instead.

On-disk format — a small JSON envelope, every field ASCII text, so git tracks
it as a normal text file and only the ``ciphertext`` line changes between
saves (the salt is preserved across re-saves):

    {
      "version": 1,
      "kdf": "pbkdf2_sha256",
      "iterations": 600000,
      "salt": "<base64url>",
      "ciphertext": "<base64url fernet token>"
    }

CLI (bootstrap / inspect):

    # encrypt an existing plaintext advisors.json -> advisors.json.enc
    ADVISORS_PASSPHRASE=... python scripts/tools/advisors_crypto.py encrypt

    # decrypt advisors.json.enc and print the JSON to stdout
    ADVISORS_PASSPHRASE=... python scripts/tools/advisors_crypto.py decrypt
"""

from __future__ import annotations

import base64
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ADVISORS_JSON = REPO_ROOT / "data" / "processed" / "advisors.json"
ADVISORS_ENC = REPO_ROOT / "data" / "processed" / "advisors.json.enc"

ENV_PASSPHRASE = "ADVISORS_PASSPHRASE"
KDF_ITERATIONS = 600_000


class AdvisorsCryptoError(RuntimeError):
    """Raised for any passphrase / decryption problem (with a friendly message)."""


# ── passphrase + key derivation ─────────────────────────────────────────────

def _get_passphrase() -> str:
    pw = os.environ.get(ENV_PASSPHRASE)
    if pw:
        return pw
    if sys.stdin.isatty():
        pw = getpass.getpass(f"Advisors passphrase ({ENV_PASSPHRASE} not set): ")
        if pw:
            return pw
    raise AdvisorsCryptoError(
        f"No passphrase available. Set the {ENV_PASSPHRASE} environment "
        "variable (in CI, supply it as a secret), or run interactively to be "
        "prompted."
    )


def _derive_key(passphrase: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode("ascii"))


# ── encrypt / decrypt ───────────────────────────────────────────────────────

def encrypt_data(data: dict,
                 passphrase: Optional[str] = None,
                 salt: Optional[bytes] = None) -> dict:
    """Return a JSON-serialisable envelope encrypting ``data``."""
    passphrase = passphrase or _get_passphrase()
    salt = salt or os.urandom(16)
    key = _derive_key(passphrase, salt)
    plaintext = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    token = Fernet(key).encrypt(plaintext)
    return {
        "version": 1,
        "kdf": "pbkdf2_sha256",
        "iterations": KDF_ITERATIONS,
        "salt": _b64e(salt),
        "ciphertext": token.decode("ascii"),
    }


def decrypt_envelope(envelope: dict, passphrase: Optional[str] = None) -> dict:
    """Decrypt an envelope produced by :func:`encrypt_data`."""
    passphrase = passphrase or _get_passphrase()
    salt = _b64d(envelope["salt"])
    iterations = int(envelope.get("iterations", KDF_ITERATIONS))
    key = _derive_key(passphrase, salt, iterations)
    try:
        plaintext = Fernet(key).decrypt(envelope["ciphertext"].encode("ascii"))
    except InvalidToken as exc:
        raise AdvisorsCryptoError(
            "Could not decrypt the advisors data — wrong passphrase or "
            "corrupted file."
        ) from exc
    return json.loads(plaintext)


# ── load / save (used by advisors.py) ───────────────────────────────────────

def load_advisors(passphrase: Optional[str] = None) -> dict:
    """Load the advisors data.

    Prefers the encrypted ``advisors.json.enc``; falls back to a legacy
    plaintext ``advisors.json`` (one-time migration path) and finally to an
    empty dict when neither exists.
    """
    if ADVISORS_ENC.exists():
        with ADVISORS_ENC.open() as fh:
            envelope = json.load(fh)
        return decrypt_envelope(envelope, passphrase)
    if ADVISORS_JSON.exists():
        with ADVISORS_JSON.open() as fh:
            return json.load(fh)
    return {}


def save_advisors(data: dict, passphrase: Optional[str] = None) -> None:
    """Encrypt ``data`` and write it to ``advisors.json.enc``.

    Re-uses the existing salt when present so only the ciphertext changes
    between saves, keeping git diffs tidy. Never writes cleartext to disk.
    """
    salt = None
    if ADVISORS_ENC.exists():
        try:
            with ADVISORS_ENC.open() as fh:
                salt = _b64d(json.load(fh)["salt"])
        except (json.JSONDecodeError, KeyError, ValueError):
            salt = None
    envelope = encrypt_data(data, passphrase, salt)
    ADVISORS_ENC.parent.mkdir(parents=True, exist_ok=True)
    with ADVISORS_ENC.open("w") as fh:
        json.dump(envelope, fh, indent=2)
        fh.write("\n")


# ── CLI ─────────────────────────────────────────────────────────────────────

def _cli(argv: list) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Encrypt / decrypt the backend-only advisors database.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser(
        "encrypt", help="Encrypt a plaintext advisors.json into advisors.json.enc")
    p_enc.add_argument(
        "--in", dest="infile", default=str(ADVISORS_JSON),
        help="plaintext JSON to encrypt (default: data/processed/advisors.json)")

    p_dec = sub.add_parser(
        "decrypt", help="Decrypt advisors.json.enc and print (or write) the JSON")
    p_dec.add_argument(
        "--out", dest="outfile", default=None,
        help="write cleartext JSON here instead of stdout")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "encrypt":
            src = Path(args.infile)
            if not src.exists():
                raise AdvisorsCryptoError(f"No such file: {src}")
            with src.open() as fh:
                data = json.load(fh)
            save_advisors(data)
            print(f"Encrypted {src} -> {ADVISORS_ENC}")
            return 0

        if args.cmd == "decrypt":
            data = load_advisors()
            text = json.dumps(data, indent=2, ensure_ascii=False)
            if args.outfile:
                Path(args.outfile).write_text(text + "\n")
                print(f"Wrote cleartext -> {args.outfile}")
            else:
                print(text)
            return 0
    except AdvisorsCryptoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
