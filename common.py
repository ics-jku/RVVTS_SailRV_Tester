# coding: utf-8
#
# (C) 2026 Manfred Schlaegl <manfred.schlaegl@jku.at>, Institute for Complex Systems, JKU Linz
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

import config


PROJECT_ROOT = Path(__file__).resolve().parent
EXTERNAL_TOOLS = PROJECT_ROOT / "external_tools"
PYTHON_ENV = EXTERNAL_TOOLS / "python"
RESULTS_DIR = PROJECT_ROOT / "results"
RUN_TEST_DIR = PROJECT_ROOT / "run_test"
VERSIONS_MANIFEST = EXTERNAL_TOOLS / ".versions.json"


def tool_dir(spec: dict[str, object]) -> Path:
    return EXTERNAL_TOOLS / str(spec["dir"])


def generated_testsets_dir() -> Path:
    return tool_dir(config.TESTSETS) / str(config.TESTSETS["generated_subdir"])


def testset_dir(xlen: int, testset_type: str) -> Path:
    return generated_testsets_dir() / f"RV{xlen}" / testset_type


def gcc_bin() -> Path:
    return tool_dir(config.TOOLCHAIN) / "bin" / "riscv64-unknown-elf-gcc"


def gdb_bin() -> Path:
    return tool_dir(config.TOOLCHAIN) / "bin" / "riscv64-unknown-elf-gdb"


def sail_compiler_bin() -> Path:
    return tool_dir(config.SAIL_COMPILER) / "bin" / "sail"


def spike_bin() -> Path:
    return tool_dir(config.SPIKE) / "spike"


def sail_riscv_bin() -> Path:
    return tool_dir(config.SAIL_RISCV) / "build" / "c_emulator" / "sail_riscv_sim"


def python_bin() -> Path:
    return PYTHON_ENV / "bin" / "python"


def pip_bin() -> Path:
    return PYTHON_ENV / "bin" / "pip"


def load_versions() -> dict[str, object]:
    if not VERSIONS_MANIFEST.is_file():
        return {}
    return json.loads(VERSIONS_MANIFEST.read_text())


def save_versions(versions: dict[str, object]) -> None:
    VERSIONS_MANIFEST.write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n")


def ensure_venv_python() -> None:
    expected = python_bin()
    in_venv = Path(sys.prefix).resolve() == PYTHON_ENV.resolve()
    if expected.exists() and not in_venv:
        os.execv(str(expected), [str(expected), *sys.argv])


def git_short_hash(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=10", "HEAD"], cwd=path, text=True
        ).strip()
    except Exception:
        return "unknown"


def result_base() -> Path:
    return (
        RESULTS_DIR
        / f"RVVTS_{git_short_hash(tool_dir(config.RVVTS))}_"
        f"Sail_{git_short_hash(tool_dir(config.SAIL_RISCV))}_"
        f"Spike_{git_short_hash(tool_dir(config.SPIKE))}"
    )


def import_rvvts():
    sys.path.insert(0, str(tool_dir(config.RVVTS)))
    import config_base  # type: ignore
    import rvvts  # type: ignore

    return rvvts, config_base


def build_runner_config(
    rvvts,
    config_base,
    xlen: int,
    testset_type: str,
    fragments: int,
    *,
    testset_dir_override: Path | None = None,
    validate_testset: bool = True,
):
    run_dir = result_base() / f"RV{xlen}" / f"RVV_vlen{config.VECTOR_VLEN}" / testset_type
    tests = testset_dir_override or testset_dir(xlen, testset_type)
    if validate_testset and not tests.is_dir():
        raise FileNotFoundError(f"testset directory not found: {tests}")

    cfg = {}
    cfg.update(config_base.config.copy())
    cfg.update(
        {
            "gcc_bin": str(gcc_bin()),
            "gdb_bin": str(gdb_bin()) if gdb_bin().exists() else "",
            "sail_riscv_bin": str(sail_riscv_bin()),
            "spike_bin": str(spike_bin()),
            "riscvovpsim_bin": "",
            "vp_path": "",
            "ara_tb_bin": "",
            "qemu_path": "",
            "minresvp_bin": "",
            "dir": str(run_dir),
            "ReportRunner_dut": rvvts.TestsetCodeErrMinRunner,
            "testset_dir": str(tests),
            "testset_pattern": config.TESTSETS["testcase_pattern"],
            "testset_max_fragments_per_run": fragments,
            "debug_port": 8000 + xlen,
            "CompareRunner_dut": rvvts.SailRunner,
            "RefCovRunner_ref": rvvts.SpikeRunner,
            "RefCovRunner_coverage": None,
            "AFC_Categorizer": rvvts.AFC_Sail,
            "rvisacfg": rvvts.RVISACfg(
                xlen=xlen,
                extensions_under_test=config.EXTENSIONS_UNDER_TEST,
                vlen=config.VECTOR_VLEN,
                velen=config.VECTOR_VELEN,
            ),
            "archive_on_timeout": True,
            "archive_on_ignore": True,
            "archive_on_error": True,
            "archive_on_complete": False,
        }
    )
    return cfg
