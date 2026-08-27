#!/usr/bin/env python3
# coding: utf-8
#
# (C) 2026 Manfred Schlaegl <manfred.schlaegl@jku.at>, Institute for Complex Systems, JKU Linz
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import common
import config


RUN_DIR_RE = re.compile(r"^RVVTS_(?P<rvvts_hash>[^_]+)_Sail_(?P<sail_hash>[^_]+)_Spike_(?P<spike_hash>.+)$")
VLEN_DIR_RE = re.compile(r"^RVV_vlen(?P<vlen>\d+)$")
FAIL_ID_RE = re.compile(r"^(?P<prefix>.+)-FailID_(?P<fail_id>[^-]+)$")

EXCLUDED_DIRS = {"ARTIFACTS", "TestsetCodeErrMinRunner_0"}
EXCLUDED_FILES = {
    "init_config.log",
    "run_args.log",
    "stats.log",
    "task_pre_result.log",
    "task_result.log",
}

CSV_FIELDS = [
    "xlen",
    "rvvts_hash",
    "ref",
    "ref_hash",
    "dut",
    "dut_hash",
    "extension",
    "vlen",
    "testset_type",
    "kind",
    "category",
    "instruction",
    "path",
]
TESTSET_RUN_FIELDS = [
    "xlen",
    "rvvts_hash",
    "ref",
    "ref_hash",
    "dut",
    "dut_hash",
    "extension",
    "vlen",
    "testset_type",
    "run",
    "path",
    "iterations",
    "failids",
    "testset_len",
    "tests",
    "completes",
    "ignores",
    "timeouts",
    "unknown_faults",
    "errors",
    "reductions",
    "minimizations",
    "minimizations_state",
]

COMBOS = [("RV32", "IVS"), ("RV32", "VS"), ("RV64", "IVS"), ("RV64", "VS")]
CASES_DIR = "CASES"
RUN_STATS_FIELDS = [
    "iterations",
    "failids",
    "testset_len",
    "tests",
    "completes",
    "ignores",
    "timeouts",
    "unknown_faults",
    "errors",
    "reductions",
    "minimizations",
    "minimizations_state",
]
CODE_RUN_STATS_FIELDS = [
    "tests",
    "completes",
    "ignores",
    "timeouts",
    "unknown_faults",
    "errors",
    "reductions",
    "minimizations",
    "minimizations_state",
]


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "unknown"


def heading_anchor(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9 _-]+", "", value)
    value = re.sub(r"\s+", "-", value.strip())
    return value or "section"


def md_link(label: str, target: Path | str) -> str:
    target_text = str(target).replace("\\", "/")
    if target_text.startswith("#"):
        return f"[{label}]({target_text})"
    if "#" in target_text:
        path_text, fragment = target_text.split("#", 1)
        quoted = quote(path_text) + "#" + quote(fragment, safe="._-")
    else:
        quoted = quote(target_text)
    return f"[{label}]({quoted})"


def project_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=10", "HEAD"],
            cwd=common.PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def github_commit_url(repo_url: str, commit: str) -> str | None:
    if commit == "unknown":
        return None
    base = repo_url.removesuffix(".git")
    if not base.startswith("https://github.com/"):
        return None
    return f"{base}/commit/{commit}"


def commit_link(label: str, repo_url: str, commit: str) -> str:
    url = github_commit_url(repo_url, commit)
    if url is None:
        return f"`{commit}`"
    return f"[`{label}`]({url})"


def parse_report_name(name: str) -> tuple[str, str, str] | None:
    fail_match = FAIL_ID_RE.match(name)
    if not fail_match:
        return None
    parts = fail_match.group("prefix").split("-", 2)
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], parts[2]


def parse_report_path(report_dir: Path, reports_root: Path) -> dict[str, str] | None:
    try:
        rel = report_dir.relative_to(reports_root)
    except ValueError:
        return None

    parts = rel.parts
    if len(parts) < 7 or not parts[4].startswith("ReportRunner_") or parts[5] != "REPORTS":
        return None

    run_match = RUN_DIR_RE.match(parts[0])
    vlen_match = VLEN_DIR_RE.match(parts[2])
    report_name = parse_report_name(parts[6])
    if not run_match or not vlen_match or not report_name:
        return None

    kind, category, instruction = report_name
    return {
        "xlen": parts[1],
        "rvvts_hash": run_match.group("rvvts_hash"),
        "ref": "Spike",
        "ref_hash": run_match.group("spike_hash"),
        "dut": "Sail",
        "dut_hash": run_match.group("sail_hash"),
        "extension": parts[2].split("_", 1)[0],
        "vlen": vlen_match.group("vlen"),
        "testset_type": parts[3],
        "kind": kind,
        "category": category,
        "instruction": instruction,
        "path": str(Path(CASES_DIR) / rel),
    }


def parse_run_path(run_dir: Path, results_dir: Path) -> dict[str, str] | None:
    try:
        rel = run_dir.relative_to(results_dir)
    except ValueError:
        return None

    parts = rel.parts
    if len(parts) != 5 or not parts[4].startswith("ReportRunner_"):
        return None

    run_match = RUN_DIR_RE.match(parts[0])
    vlen_match = VLEN_DIR_RE.match(parts[2])
    if not run_match or not vlen_match:
        return None

    return {
        "xlen": parts[1],
        "rvvts_hash": run_match.group("rvvts_hash"),
        "ref": "Spike",
        "ref_hash": run_match.group("spike_hash"),
        "dut": "Sail",
        "dut_hash": run_match.group("sail_hash"),
        "extension": parts[2].split("_", 1)[0],
        "vlen": vlen_match.group("vlen"),
        "testset_type": parts[3],
        "run": parts[4],
        "path": str(Path(CASES_DIR) / rel),
    }


def parse_stats_file(path: Path) -> dict[str, int]:
    stats = {}
    if not path.is_file():
        return stats
    for line in path.read_text(errors="replace").splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if key in RUN_STATS_FIELDS and re.fullmatch(r"-?\d+", value):
            stats[key] = int(value)
    return stats


def ignore_results(path: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in EXCLUDED_DIRS or name in EXCLUDED_FILES:
            ignored.add(name)
    return ignored


def prepare_output_dir(output_dir: Path, force: bool) -> None:
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        return
    if not force:
        raise FileExistsError(f"output directory already exists: {output_dir}; rerun with --force")
    shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)


def copy_results(results_dir: Path, reports_root: Path) -> None:
    shutil.copytree(results_dir, reports_root, ignore=ignore_results)


def collect_rows(reports_root: Path) -> list[dict[str, str]]:
    rows = []
    for readme in sorted(reports_root.glob("RVVTS_*/RV*/RVV_vlen*/*/ReportRunner_*/REPORTS/*/README.md")):
        row = parse_report_path(readme.parent, reports_root)
        if row is not None:
            rows.append(row)
    return rows


def collect_run_rows(results_dir: Path) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for run_dir in sorted(results_dir.glob("RVVTS_*/RV*/RVV_vlen*/*/ReportRunner_*")):
        if not run_dir.is_dir():
            continue
        row = parse_run_path(run_dir, results_dir)
        if row is None:
            continue

        stats = parse_stats_file(run_dir / "stats.log")
        code_stats = parse_stats_file(
            run_dir / "TestsetCodeErrMinRunner_0" / "CodeErrMinRunner_0" / "stats.log"
        )
        fallback_stats = parse_stats_file(run_dir / "TestsetCodeErrMinRunner_0" / "stats.log")
        for field in CODE_RUN_STATS_FIELDS:
            if field not in code_stats and field in fallback_stats:
                code_stats[field] = fallback_stats[field]

        row.update({field: stats.get(field, 0) for field in ("iterations", "failids")})
        row["testset_len"] = fallback_stats.get("testset_len", 0)
        row.update({field: code_stats.get(field, 0) for field in CODE_RUN_STATS_FIELDS})
        rows.append(row)
    return rows


def write_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
    with csv_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_testset_runs_csv(csv_path: Path, rows: list[dict[str, str | int]]) -> None:
    with csv_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=TESTSET_RUN_FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in TESTSET_RUN_FIELDS} for row in rows])


def add_report_backlinks(output_dir: Path, rows: list[dict[str, str]]) -> None:
    for row in rows:
        readme = output_dir / row["path"] / "README.md"
        if not readme.is_file():
            continue

        report_dir = readme.parent
        overview = Path(os.path.relpath(output_dir / "README.md", report_dir))
        category = Path(os.path.relpath(output_dir / "CATEGORIES" / f"{slug(row['category'])}.md", report_dir))
        instruction = Path(
            os.path.relpath(output_dir / "INSTRUCTIONS" / f"{slug(row['instruction'])}.md", report_dir)
        )
        links = [
            md_link("Report overview", overview),
            md_link(
                f"Category: {row['category']}",
                f"{category}#{heading_anchor('Instruction: ' + row['instruction'])}",
            ),
            md_link(
                f"Instruction: {row['instruction']}",
                f"{instruction}#{heading_anchor('Category: ' + row['category'])}",
            ),
        ]
        text = readme.read_text(errors="replace")
        nav = "<!-- RVVTS_REPORT_NAV -->\n" + " | ".join(links) + "\n\n---\n\n"
        if "<!-- RVVTS_REPORT_NAV -->" not in text:
            readme.write_text(nav + text)


def combo_counts(rows: list[dict[str, str]], key: str) -> dict[str, Counter[tuple[str, str]]]:
    counts: dict[str, Counter[tuple[str, str]]] = {}
    for row in rows:
        value = row[key]
        combo = (row["xlen"], row["testset_type"])
        counts.setdefault(value, Counter())[combo] += 1
    return counts


def count_table(
    title_key: str,
    counts: dict[str, Counter[tuple[str, str]]],
    link_dir: str,
    *,
    local_links: bool = False,
) -> str:
    lines = [
        f"| {title_key} | RV32 IVS | RV32 VS | RV64 IVS | RV64 VS | Total |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    items = sorted(counts.items(), key=lambda item: (-sum(item[1].values()), item[0]))
    totals = Counter()
    for value, counter in items:
        total = sum(counter.values())
        totals.update(counter)
        if local_links:
            link = md_link(value, f"#{heading_anchor(title_key + ': ' + value)}")
        else:
            link = md_link(value, f"{link_dir}/{slug(value)}.md")
        combo_values = [str(counter.get(combo, 0)) for combo in COMBOS]
        lines.append(f"| {link} | {' | '.join(combo_values)} | {total} |")
    if not items:
        lines.append("| _none_ | 0 | 0 | 0 | 0 | 0 |")
        return "\n".join(lines)
    combo_totals = [str(totals.get(combo, 0)) for combo in COMBOS]
    lines.append(f"| **Total** | {' | '.join(combo_totals)} | {sum(totals.values())} |")
    return "\n".join(lines)


def report_rows_table(
    rows: list[dict[str, str]], output_dir: Path, page_dir: Path
) -> str:
    columns = [
        ("xlen", "XLEN"),
        ("testset_type", "Testset"),
        ("kind", "Kind"),
        ("category", "Category"),
        ("instruction", "Instruction"),
    ]
    lines = ["| " + " | ".join([label for _, label in columns] + ["Case Report"]) + " |"]
    lines.append("| " + " | ".join(["---"] * (len(columns) + 1)) + " |")
    for row in sorted(
        rows,
        key=lambda item: (
            item["xlen"],
            item["testset_type"],
            item["category"],
            item["instruction"],
            item["path"],
        ),
    ):
        report_readme = output_dir / row["path"] / "README.md"
        rel_report = Path(os.path.relpath(report_readme, page_dir))
        values = [row[key] for key, _ in columns]
        values.append(md_link("README.md", rel_report))
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", f"Cases: {len(rows)}"])
    return "\n".join(lines)


def count_pct(value: int, total: int) -> str:
    if total <= 0:
        return f"{value} (n/a)"
    return f"{value} ({value / total * 100:.1f}%)"


def run_rows_table(run_rows: list[dict[str, str | int]]) -> str:
    lines = [
        "| Run | XLEN | Testset | VLEN | Test Cases | Executed Tests | Completes | Ignores | Timeouts | Unknown Faults | Errors | Reduced Errors | Minimized Errors | State-Minimized Errors |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    totals = Counter()
    for row in sorted(
        run_rows,
        key=lambda item: (
            str(item["xlen"]),
            str(item["testset_type"]),
            str(item["rvvts_hash"]),
            str(item["run"]),
        ),
    ):
        path = str(row["path"])
        reports_path = Path(path) / "REPORTS"
        executed_tests = int(row["tests"])
        errors = int(row["errors"])
        values = [
            md_link(str(row["run"]), reports_path),
            str(row["xlen"]),
            str(row["testset_type"]),
            str(row["vlen"]),
            str(row["testset_len"]),
            str(executed_tests),
            count_pct(int(row["completes"]), executed_tests),
            count_pct(int(row["ignores"]), executed_tests),
            count_pct(int(row["timeouts"]), executed_tests),
            count_pct(int(row["unknown_faults"]), executed_tests),
            count_pct(errors, executed_tests),
            count_pct(int(row["reductions"]), errors),
            count_pct(int(row["minimizations"]), errors),
            count_pct(int(row["minimizations_state"]), errors),
        ]
        lines.append("| " + " | ".join(values) + " |")
        for field in (
            "testset_len",
            "tests",
            "completes",
            "ignores",
            "timeouts",
            "unknown_faults",
            "errors",
            "reductions",
            "minimizations",
            "minimizations_state",
        ):
            totals[field] += int(row[field])
    if not run_rows:
        lines.append("| _none_ |  |  | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
    else:
        total_tests = totals["tests"]
        total_errors = totals["errors"]
        lines.append(
            "| **Total** |  |  |  | "
            + " | ".join(
                [
                    str(totals["testset_len"]),
                    str(total_tests),
                    count_pct(totals["completes"], total_tests),
                    count_pct(totals["ignores"], total_tests),
                    count_pct(totals["timeouts"], total_tests),
                    count_pct(totals["unknown_faults"], total_tests),
                    count_pct(total_errors, total_tests),
                    count_pct(totals["reductions"], total_errors),
                    count_pct(totals["minimizations"], total_errors),
                    count_pct(totals["minimizations_state"], total_errors),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def detail_page_nav(output_dir: Path, page_dir: Path, key: str, value: str) -> str:
    links = [md_link("Report overview", Path(os.path.relpath(output_dir / "README.md", page_dir)))]
    if key == "category":
        links.append(md_link(f"Category: {value}", f"#{heading_anchor('Category: ' + value)}"))
    else:
        links.append(md_link(f"Instruction: {value}", f"#{heading_anchor('Instruction: ' + value)}"))
    return " | ".join(links)


def subgroup_nav(output_dir: Path, page_dir: Path, key: str, value: str, grouped_value: str) -> str:
    links = [md_link("Report overview", Path(os.path.relpath(output_dir / "README.md", page_dir)))]
    if key == "category":
        links.extend(
            [
                md_link(f"Category: {value}", f"#{heading_anchor('Category: ' + value)}"),
                md_link(
                    f"Instruction: {grouped_value}",
                    Path(os.path.relpath(output_dir / "INSTRUCTIONS" / f"{slug(grouped_value)}.md", page_dir))
                    .as_posix()
                    + f"#{heading_anchor('Category: ' + value)}",
                ),
            ]
        )
    else:
        links.extend(
            [
                md_link(f"Instruction: {value}", f"#{heading_anchor('Instruction: ' + value)}"),
                md_link(
                    f"Category: {grouped_value}",
                    Path(os.path.relpath(output_dir / "CATEGORIES" / f"{slug(grouped_value)}.md", page_dir))
                    .as_posix()
                    + f"#{heading_anchor('Instruction: ' + value)}",
                ),
            ]
        )
    return " | ".join(links)


def write_detail_pages(
    output_dir: Path,
    rows: list[dict[str, str]],
    key: str,
    other_key: str,
) -> None:
    dirname = "CATEGORIES" if key == "category" else "INSTRUCTIONS"
    page_dir = output_dir / dirname
    page_dir.mkdir()

    values = sorted({row[key] for row in rows})
    for value in values:
        value_rows = [row for row in rows if row[key] == value]
        grouped_counts = combo_counts(value_rows, other_key)
        grouped_values = sorted(
            grouped_counts,
            key=lambda item: (-sum(grouped_counts[item].values()), item),
        )
        text = [
            f"# {key.title()}: {value}",
            "",
            detail_page_nav(output_dir, page_dir, key, value),
            "",
            count_table(
                other_key.title(),
                grouped_counts,
                "",
                local_links=True,
            ),
            "",
        ]
        for grouped_value in grouped_values:
            grouped_rows = [row for row in value_rows if row[other_key] == grouped_value]
            text.extend(
                [
                    f"## {other_key.title()}: {grouped_value}",
                    "",
                    subgroup_nav(output_dir, page_dir, key, value, grouped_value),
                    "",
                    report_rows_table(grouped_rows, output_dir, page_dir),
                    "",
                ]
            )
        (page_dir / f"{slug(value)}.md").write_text("\n".join(text))


def write_readme(output_dir: Path, rows: list[dict[str, str]], run_rows: list[dict[str, str | int]]) -> None:
    category_counts = combo_counts(rows, "category")
    instruction_counts = combo_counts(rows, "instruction")
    non_error_rows = [row for row in rows if row["kind"] != "ERROR"]
    runs = sorted(
        {
            (row["rvvts_hash"], row["dut_hash"], row["ref_hash"], row["extension"], row["vlen"])
            for row in rows
        }
    )

    lines = [
        "# RVVTS Report: Sail-RISC-V vs. Spike",
        "",
        "This report summarizes collected RVVTS cases from Sail-RISC-V runs against Spike.",
        "",
        "Tested and generated with "
        "[RVVTS_SailRV_Tester](https://github.com/ics-jku/RVVTS_SailRV_Tester).",
        "",
        "## Test Setup",
        "",
    ]
    if runs:
        tester_commit = project_commit()
        for rvvts_hash, dut_hash, ref_hash, extension, vlen in runs:
            lines.extend(
                [
                    "* Report tooling: RVVTS_SailRV_Tester, commit "
                    f"{commit_link(tester_commit, 'https://github.com/ics-jku/RVVTS_SailRV_Tester.git', tester_commit)}.",
                    f"* Reference model (REF): Spike, commit {commit_link(ref_hash, config.SPIKE['url'], ref_hash)}.",
                    f"* DUT: Sail-RISC-V, commit {commit_link(dut_hash, config.SAIL_RISCV['url'], dut_hash)}.",
                    f"* Test framework: RVVTS, commit {commit_link(rvvts_hash, config.RVVTS['url'], rvvts_hash)}.",
                    f"* Target: RV32 and RV64 with {extension} and `VLEN = {vlen}` bit.",
                ]
            )
    else:
        lines.append("* No reports found.")
    lines.extend(
        [
            "",
            "## Testset Runs",
            "",
            run_rows_table(run_rows),
            "",
            "## Case Categories",
            "",
            count_table("Category", category_counts, "CATEGORIES"),
            "",
            "## Case Instructions",
            "",
            count_table("Instruction", instruction_counts, "INSTRUCTIONS"),
            "",
            "## Files",
            "",
            f"* Cases CSV: {md_link('cases.csv', 'cases.csv')}",
            f"* Testset run statistics CSV: {md_link('testset_runs.csv', 'testset_runs.csv')}",
            f"* Collected cases: {md_link(CASES_DIR, CASES_DIR)}",
            "",
            "## Non-Error Cases",
            "",
            "The following table lists collected `IGNORE`, `TIMEOUT`, `UNKNOWN_FAULT`, and other non-error cases.",
            "",
            report_rows_table(non_error_rows, output_dir, output_dir),
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines))


def ensure_output_not_inside_results(output_dir: Path, results_dir: Path) -> None:
    try:
        output_dir.relative_to(results_dir)
    except ValueError:
        return
    raise ValueError("output directory must not be inside results-dir")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=common.RESULTS_DIR)
    parser.add_argument("--output-dir", type=Path, default=common.PROJECT_ROOT / "report")
    parser.add_argument("--force", action="store_true", help="delete output directory before writing")
    args = parser.parse_args()

    results_dir = args.results_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not results_dir.is_dir():
        raise FileNotFoundError(results_dir)
    ensure_output_not_inside_results(output_dir, results_dir)

    run_rows = collect_run_rows(results_dir)
    prepare_output_dir(output_dir, args.force)
    reports_root = output_dir / CASES_DIR
    copy_results(results_dir, reports_root)
    rows = collect_rows(reports_root)
    write_csv(output_dir / "cases.csv", rows)
    write_testset_runs_csv(output_dir / "testset_runs.csv", run_rows)
    add_report_backlinks(output_dir, rows)
    write_detail_pages(output_dir, rows, "category", "instruction")
    write_detail_pages(output_dir, rows, "instruction", "category")
    write_readme(output_dir, rows, run_rows)

    print(f"REPORT_DIR: {output_dir}")
    print(f"CASES_CSV: {output_dir / 'cases.csv'}")
    print(f"CASES: {len(rows)}")
    print(f"RUNS: {len(run_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
