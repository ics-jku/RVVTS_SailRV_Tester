#!/usr/bin/env python3
# coding: utf-8
#
# (C) 2026 Manfred Schlaegl <manfred.schlaegl@jku.at>, Institute for Complex Systems, JKU Linz
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

import common
import config


def config_snapshot(value):
    return json.loads(json.dumps(value, sort_keys=True))


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), f"(cwd={cwd})" if cwd else "")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def git_checkout(name: str, spec: dict[str, object], versions: dict[str, object]) -> None:
    dest = common.tool_dir(spec)
    ref = str(spec["ref"])
    if dest.exists():
        run(["git", "fetch", "--tags", "--prune", "origin"], cwd=dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", str(spec["url"]), str(dest)])
    run(["git", "checkout", ref], cwd=dest)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=dest)
    installed_ref = common.git_short_hash(dest)
    versions[name] = {
        "type": "git",
        "url": spec["url"],
        "ref": ref,
        "installed_ref": installed_ref,
    }
    common.save_versions(versions)
    print(f"{name}: {installed_ref}")


def host_machine_key() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    raise RuntimeError(
        "unsupported host architecture: "
        f"{platform.machine()}. The configured prebuilt GCC toolchain is x86_64-only."
    )


def ubuntu_asset_key() -> str:
    machine = host_machine_key()
    os_release = Path("/etc/os-release").read_text(errors="ignore")
    if 'VERSION_ID="24.04"' in os_release or "VERSION_ID=24.04" in os_release:
        return f"{machine}-ubuntu-24.04"
    return f"{machine}-ubuntu-22.04"


def binary_current(
    versions: dict[str, object], name: str, spec: dict[str, object], asset_key: str, binary: Path
) -> bool:
    entry = versions.get(name)
    return (
        binary.is_file()
        and isinstance(entry, dict)
        and entry.get("config") == config_snapshot(spec)
        and entry.get("asset_key") == asset_key
    )


def download_toolchain(versions: dict[str, object]) -> None:
    asset_key = ubuntu_asset_key()
    if binary_current(versions, "toolchain", config.TOOLCHAIN, asset_key, common.gcc_bin()):
        print(f"toolchain: found {common.gcc_bin()}")
        return

    asset = config.TOOLCHAIN["assets"][asset_key]
    archive = common.EXTERNAL_TOOLS / Path(asset["url"]).name
    common.EXTERNAL_TOOLS.mkdir(parents=True, exist_ok=True)

    print(f"toolchain: downloading {asset['url']}")
    urllib.request.urlretrieve(asset["url"], archive)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != asset["sha256"]:
        raise RuntimeError(f"SHA256 mismatch for {archive}: {digest}")

    toolchain_dir = common.tool_dir(config.TOOLCHAIN)
    if toolchain_dir.exists():
        shutil.rmtree(toolchain_dir)
    extract_dir = common.EXTERNAL_TOOLS / "toolchain_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()

    safe_extract(archive, extract_dir)

    gccs = sorted(extract_dir.glob("**/bin/riscv64-unknown-elf-gcc"))
    if not gccs:
        raise RuntimeError("downloaded toolchain does not contain riscv64-unknown-elf-gcc")

    toolchain_root = gccs[0].parents[1]
    shutil.move(str(toolchain_root), str(toolchain_dir))
    shutil.rmtree(extract_dir, ignore_errors=True)
    versions["toolchain"] = {
        "type": "binary",
        "config": config_snapshot(config.TOOLCHAIN),
        "asset_key": asset_key,
        "binary": str(common.gcc_bin()),
    }
    common.save_versions(versions)
    print(f"toolchain: installed {common.gcc_bin()}")


def download_sail_compiler(versions: dict[str, object]) -> None:
    asset_key = host_machine_key()
    if binary_current(
        versions, "sail_compiler", config.SAIL_COMPILER, asset_key, common.sail_compiler_bin()
    ):
        print(f"sail compiler: found {common.sail_compiler_bin()}")
        return

    asset = config.SAIL_COMPILER["assets"][asset_key]
    archive = common.EXTERNAL_TOOLS / Path(asset["url"]).name
    common.EXTERNAL_TOOLS.mkdir(parents=True, exist_ok=True)

    print(f"sail compiler: downloading {asset['url']}")
    urllib.request.urlretrieve(asset["url"], archive)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != asset["sha256"]:
        raise RuntimeError(f"SHA256 mismatch for {archive}: {digest}")

    sail_compiler_dir = common.tool_dir(config.SAIL_COMPILER)
    if sail_compiler_dir.exists():
        shutil.rmtree(sail_compiler_dir)
    extract_dir = common.EXTERNAL_TOOLS / "sail_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()

    safe_extract(archive, extract_dir)
    extracted = extract_dir / "sail"
    if not (extracted / "bin" / "sail").is_file():
        raise RuntimeError("downloaded Sail compiler does not contain bin/sail")
    shutil.move(str(extracted), str(sail_compiler_dir))
    shutil.rmtree(extract_dir, ignore_errors=True)
    versions["sail_compiler"] = {
        "type": "binary",
        "config": config_snapshot(config.SAIL_COMPILER),
        "asset_key": asset_key,
        "binary": str(common.sail_compiler_bin()),
    }
    common.save_versions(versions)
    print(f"sail compiler: installed {common.sail_compiler_bin()}")


def safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as tf:
        dest = destination.resolve()
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            if dest not in [target, *target.parents]:
                raise RuntimeError(f"refusing unsafe tar member: {member.name}")
        try:
            tf.extractall(destination, filter="data")
        except TypeError:
            tf.extractall(destination)


def build_spike() -> None:
    spike = common.spike_bin()
    if spike.is_file():
        print(f"spike: found {spike}")
        return
    run(["./configure"], cwd=common.tool_dir(config.SPIKE))
    run(["make", f"-j{os.cpu_count() or 1}"], cwd=common.tool_dir(config.SPIKE))


def build_sail_riscv() -> None:
    sail_sim = common.sail_riscv_bin()
    if sail_sim.is_file():
        print(f"sail-riscv: found {sail_sim}")
        return
    env = os.environ.copy()
    env["PATH"] = str(common.sail_compiler_bin().parent) + os.pathsep + env["PATH"]
    env.pop("SAIL_DIR", None)
    env.pop("SAIL_PLUGIN_DIR", None)
    run(["./build_simulator.sh"], cwd=common.tool_dir(config.SAIL_RISCV), env=env)


def setup_python_env() -> None:
    if not common.python_bin().is_file():
        run([sys.executable, "-m", "venv", str(common.PYTHON_ENV)])
    run([str(common.python_bin()), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(common.python_bin()), "-m", "pip", "install", *config.PYTHON_DEPS])


def main() -> int:
    argparse.ArgumentParser().parse_args()

    common.EXTERNAL_TOOLS.mkdir(parents=True, exist_ok=True)
    versions = common.load_versions()
    setup_python_env()
    download_toolchain(versions)
    download_sail_compiler(versions)
    git_checkout("RVVTS", config.RVVTS, versions)
    git_checkout("Spike", config.SPIKE, versions)
    git_checkout("Sail-RISC-V", config.SAIL_RISCV, versions)
    git_checkout("testsets", config.TESTSETS, versions)
    build_spike()
    build_sail_riscv()
    print("setup complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
