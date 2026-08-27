#!/usr/bin/env python3
# coding: utf-8
#
# (C) 2026 Manfred Schlaegl <manfred.schlaegl@jku.at>, Institute for Complex Systems, JKU Linz
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import common
import config


def newest_report(run_dir: Path) -> Path | None:
    reports = sorted(run_dir.glob("**/REPORTS/**/README.md"), key=lambda p: p.stat().st_mtime)
    return reports[-1] if reports else None


def main() -> int:
    common.ensure_venv_python()
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlen", choices=["32", "64"], required=True)
    parser.add_argument("testcase_json")
    args = parser.parse_args()

    rvvts, config_base = common.import_rvvts()
    testcase = Path(args.testcase_json).resolve()
    if not testcase.is_file():
        raise FileNotFoundError(testcase)

    xlen = int(args.xlen)
    run_dir = common.RUN_TEST_DIR / f"RV{xlen}" / f"RVV_vlen{config.VECTOR_VLEN}"
    cfg = common.build_runner_config(
        rvvts,
        config_base,
        xlen,
        "VS",
        0,
        testset_dir_override=testcase.parent,
        validate_testset=False,
    )
    cfg["dir"] = str(run_dir)
    cfg["testset_dir"] = str(testcase.parent)
    cfg["ReportRunner_dut"] = rvvts.CodeErrMinRunner
    cfg["archive_on_complete"] = True

    if run_dir.exists():
        shutil.rmtree(run_dir)

    code_block = rvvts.CodeBlock.load(str(testcase))
    runner = rvvts.ReportRunner(cfg)
    ret = runner.run(blocking=True, code_block=code_block, timeout=30.0)
    runner.shutdown()

    report = newest_report(run_dir)
    report_md = run_dir / "REPORT.md"
    print(f"RESULT_DIR: {run_dir}")
    if report:
        report_text = report.read_text(errors="replace")
        report_md.write_text(report_text)
        print(f"REPORT: {report_md}")
        print(report_text)
    else:
        print("REPORT: <not generated>")

    outcome = ret[0].name if hasattr(ret[0], "name") else str(ret[0])
    return 0 if outcome == "COMPLETE" else -1


if __name__ == "__main__":
    raise SystemExit(main())
