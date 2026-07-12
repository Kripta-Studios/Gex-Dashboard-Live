"""Fail-closed runtime lock for wall-surface-flow research artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_package(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def parse_runtime_lock(path: str | Path) -> dict[str, Any]:
    metadata: dict[str, str] = {}
    packages: dict[str, str] = {}
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            declaration = line[1:].strip()
            if "=" not in declaration:
                continue
            key, value = (part.strip() for part in declaration.split("=", 1))
            if not key or not value or key in metadata:
                raise AssertionError(f"invalid/duplicate runtime metadata at line {number}")
            metadata[key] = value
            continue
        if "==" not in line or line.count("==") != 1:
            raise AssertionError(f"runtime lock requires exact package pins at line {number}: {line}")
        name, version = (part.strip() for part in line.split("==", 1))
        normalized = _normalized_package(name)
        if not normalized or not version or normalized in packages:
            raise AssertionError(f"invalid/duplicate package pin at line {number}: {line}")
        packages[normalized] = version
    required_metadata = {"python_version", "platform", "platform_machine"}
    missing = sorted(required_metadata.difference(metadata))
    if missing or not packages:
        raise AssertionError(f"runtime lock incomplete: missing_metadata={missing} packages={len(packages)}")
    return {"metadata": metadata, "packages": dict(sorted(packages.items()))}


def runtime_environment(package_names: list[str] | tuple[str, ...]) -> dict[str, Any]:
    packages = {
        _normalized_package(name): importlib.metadata.version(name)
        for name in sorted({_normalized_package(value) for value in package_names})
    }
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "platform_machine": platform.machine(),
        "packages": packages,
    }


def assert_runtime_lock(path: str | Path) -> dict[str, Any]:
    lock_path = Path(path)
    parsed = parse_runtime_lock(lock_path)
    environment = runtime_environment(tuple(parsed["packages"]))
    expected_metadata = parsed["metadata"]
    observed_metadata = {
        "python_version": environment["python_version"],
        "platform": environment["platform"],
        "platform_machine": environment["platform_machine"],
    }
    if observed_metadata != expected_metadata:
        raise AssertionError(
            f"runtime platform mismatch: observed={observed_metadata} expected={expected_metadata}"
        )
    if environment["packages"] != parsed["packages"]:
        raise AssertionError(
            f"runtime package mismatch: observed={environment['packages']} expected={parsed['packages']}"
        )
    return {
        "lock_path": str(lock_path),
        "lock_sha256": sha256_file(lock_path),
        "environment": environment,
        "environment_sha256": canonical_hash(environment),
    }
