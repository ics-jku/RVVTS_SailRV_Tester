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


def format_afc_counts(category_instr_counts: dict[str, dict[str, int]]) -> list[str]:
    lines = ["* AFC_category_errors:"]
    if not category_instr_counts:
        lines.append("  * <none>")
        return lines

    categories = sorted(
        category_instr_counts.items(),
        key=lambda item: (-sum(item[1].values()), str(item[0])),
    )
    for category, instr_counts in categories:
        count = sum(instr_counts.values())
        lines.append(f"  * {category}: {count}")
        for instr, instr_count in sorted(
            instr_counts.items(), key=lambda item: (-item[1], str(item[0]))
        ):
            lines.append(f"    * {instr}: {instr_count}")

    return lines


def record_afc_error(rvvts, runner, category_instr_counts: dict[str, dict[str, int]], ret) -> None:
    if ret[0] != rvvts.RunnerOutcome.ERROR:
        return

    cemr = runner.ReportRunner_dut.codeerrminrunner
    category = getattr(cemr, "error_cause_category", None) or "UNKNOWN"
    instr = getattr(cemr, "error_cause_instr", None) or "unknown"
    instr_counts = category_instr_counts.setdefault(category, {})
    instr_counts[instr] = instr_counts.get(instr, 0) + 1


def print_iteration_stats(
    runner,
    xlen: int,
    testset_type: str,
    testset_max_fragments_per_run: int,
    output_dir: str,
    category_instr_counts: dict[str, dict[str, int]],
) -> None:
    tcem = runner.ReportRunner_dut
    cemr = tcem.codeerrminrunner
    lines = [
        "",
        "* config:",
        f"  * xlen: {xlen}",
        f"  * testset_type: {testset_type}",
        f"  * testset_max_fragments_per_run: {testset_max_fragments_per_run}",
        f"  * output_dir: {output_dir}",
        f"* test: {tcem.testset_idx + 1}/{tcem.testset_len}",
        f"* subrun: {tcem.subrun}/{tcem.subruns}",
        "* stats:",
        f"  * tests: {cemr.tests}",
        f"  * completes: {cemr.completes}",
        f"  * ignores: {cemr.ignores}",
        f"  * timeouts: {cemr.timeouts}",
        f"  * unknown_faults: {cemr.unknown_faults}",
        f"  * errors: {cemr.errors}",
        f"    * reductions: {cemr.reductions}",
        f"      * minimizations: {cemr.minimizations}",
        f"      * minimizations_state: {cemr.minimizations_state}",
    ]
    lines.extend(format_afc_counts(category_instr_counts))
    print("\n".join(lines), flush=True)


def run_testset(
    rvvts,
    runner,
    xlen: int,
    testset_type: str,
    testset_max_fragments_per_run: int,
    output_dir: str,
) -> None:
    category_instr_counts: dict[str, dict[str, int]] = {}
    while True:
        ret = runner.run(blocking=True, timeout=30.0)
        record_afc_error(rvvts, runner, category_instr_counts, ret)
        print_iteration_stats(
            runner,
            xlen,
            testset_type,
            testset_max_fragments_per_run,
            output_dir,
            category_instr_counts,
        )
        if ret[0] == rvvts.RunnerOutcome.INVALID:
            break


def selected(value: str, all_values: list):
    return all_values if value == "ALL" else [type(all_values[0])(value)]


def prepare_result_dirs(configs: list[dict[str, object]], force: bool) -> None:
    existing_dirs = [Path(str(cfg["dir"])) for cfg in configs if Path(str(cfg["dir"])).exists()]
    if not existing_dirs:
        return

    if force:
        for result_dir in existing_dirs:
            shutil.rmtree(result_dir)
            print(f"removed existing result directory: {result_dir}", flush=True)
        return

    formatted = "\n".join(f"  {path}" for path in existing_dirs)
    raise FileExistsError(
        "result directory already exists; aborting to avoid mixing results:\n"
        f"{formatted}\n"
        "rerun with --force to override this check"
    )


def main() -> int:
    common.ensure_venv_python()
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlen", choices=["32", "64", "ALL"], default="ALL")
    parser.add_argument("--testset-type", choices=["VS", "IVS", "ALL"], default="ALL")
    parser.add_argument("--testset_max_fragments_per_run", type=int, default=10)
    parser.add_argument(
        "--force",
        action="store_true",
        help="delete existing target result directories before running",
    )
    args = parser.parse_args()

    rvvts, config_base = common.import_rvvts()
    xlens = selected(args.xlen, [32, 64])
    testset_types = selected(args.testset_type, ["VS", "IVS"])

    configs = [
        (
            xlen,
            testset_type,
            common.build_runner_config(
                rvvts, config_base, xlen, testset_type, args.testset_max_fragments_per_run
            ),
        )
        for xlen in xlens
        for testset_type in testset_types
    ]
    prepare_result_dirs([cfg for _, _, cfg in configs], args.force)

    for xlen, testset_type, cfg in configs:
        runner = rvvts.ReportRunner(cfg)
        try:
            run_testset(
                rvvts,
                runner,
                xlen,
                testset_type,
                args.testset_max_fragments_per_run,
                cfg["dir"],
            )
        finally:
            runner.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
