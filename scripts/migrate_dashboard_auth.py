#!/usr/bin/env python3
"""Migrate a *specified backup* of legacy dashboard credentials to hashes.

The script never imports or executes the legacy source.  It parses literal
``USERS`` and ``API_KEYS`` assignments with :mod:`ast`, writes a mode-0600 JSON
artifact atomically, and prints counts only.  It is deliberately opt-in because
the old source must be a backup supplied by an operator, never the active server
module.
"""

from __future__ import annotations

import argparse
import ast
import base64
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


SCHEMA_VERSION = "dashboard-auth.v1"
DEFAULT_ITERATIONS = 390_000


def _encoded_hash(secret: str, iterations: int) -> dict[str, Any]:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
    return {
        "algorithm": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "digest": base64.b64encode(digest).decode("ascii"),
    }


def _literal_assignments(path: Path) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise ValueError("legacy source cannot be parsed") from exc
    assignments: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {"USERS", "API_KEYS"}:
                try:
                    assignments[target.id] = ast.literal_eval(node.value)
                except (ValueError, TypeError) as exc:
                    raise ValueError("legacy credential assignment is not literal") from exc
    if not isinstance(assignments.get("USERS"), dict):
        raise ValueError("legacy source contains no literal USERS mapping")
    if not isinstance(assignments.get("API_KEYS"), dict):
        raise ValueError("legacy source contains no literal API_KEYS mapping")
    return assignments


def build_artifact(legacy: dict[str, Any], *, iterations: int) -> dict[str, Any]:
    if not 100_000 <= iterations <= 2_000_000:
        raise ValueError("iterations outside permitted range")
    users: list[dict[str, Any]] = []
    for email, record in sorted(legacy["USERS"].items()):
        if not isinstance(email, str) or not isinstance(record, dict):
            raise ValueError("invalid legacy user record")
        password, role = record.get("pass"), record.get("role")
        if not isinstance(password, str) or not password or role not in {"ADMIN", "USER"}:
            raise ValueError("invalid legacy user record")
        users.append(
            {
                "email": email,
                "role": role,
                "password_hash": _encoded_hash(password, iterations),
            }
        )
    api_keys: list[dict[str, Any]] = []
    for ordinal, (secret, record) in enumerate(sorted(legacy["API_KEYS"].items()), start=1):
        if not isinstance(secret, str) or not secret or not isinstance(record, dict):
            raise ValueError("invalid legacy api key record")
        role = record.get("role")
        owner = record.get("owner")
        if not isinstance(role, str) or not isinstance(owner, str):
            raise ValueError("invalid legacy api key record")
        api_keys.append(
            {
                "id": f"migrated-{ordinal}",
                "role": role,
                "owner": owner,
                "key_hash": _encoded_hash(secret, iterations),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "users": users,
        "api_keys": api_keys,
    }


def atomic_write_mode_600(path: Path, payload: dict[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError("output artifact already exists")
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--confirm-migrate",
        action="store_true",
        help="required acknowledgement before reading a legacy credential backup",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.confirm_migrate:
        raise SystemExit("--confirm-migrate is required")
    legacy = _literal_assignments(args.legacy_source)
    artifact = build_artifact(legacy, iterations=args.iterations)
    atomic_write_mode_600(args.output, artifact, overwrite=args.force)
    print(
        "dashboard auth migration complete "
        f"users={len(artifact['users'])} api_keys={len(artifact['api_keys'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
