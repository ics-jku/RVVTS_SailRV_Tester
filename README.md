# RVVTS Sail-RISC-V Tester

Automation wrapper for running RVVTS test sets against Sail-RISC-V with Spike as
the reference model.

Motivation: make Sail-RISC-V vs. Spike regression checks reproducible with one
pinned setup and repeatable RVVTS report output.

[RVVTS](https://github.com/ics-jku/RVVTS) is the RISC-V Vector Test Framework
from JKU ICS; it generates, runs, compares, minimizes, and reports RISC-V test
cases for vector and related ISA-extension verification.

[RVVTS_SailRV_Spike](https://github.com/ics-jku/RVVTS_SailRV_Spike) contains
pre-generated RVVTS test sets and Sail-RISC-V vs. Spike result material. It
accompanies the paper
[Sail-RISC-V and Spike for RISC-V Vector: Toward Consistent Golden Reference Behavior](https://ics.jku.at/files/2026RISC-V_Summit_Europe_RVVTS_SailRV_Spike.pdf),
presented at RISC-V Summit Europe 2026.

## Setup

Install the host packages listed in the RVVTS README first. Then run:

```bash
./01_setup.py
```

The script downloads everything into `external_tools/`:

- a Python virtual environment in `external_tools/python`
- RVVTS
- Spike / `riscv-isa-sim`
- Sail-RISC-V
- Sail compiler binary from the official `rems-project/sail` release assets
- RVVTS Sail-RISC-V/Spike test sets
- a prebuilt `riscv64-unknown-elf-gcc` from the official
  `riscv-collab/riscv-gnu-toolchain` release assets

The binary setup path currently targets x86_64 Linux hosts. Other host
architectures should use locally adjusted toolchain/Sail compiler entries in
`config.py`.

All downloaded component versions are pinned in `config.py`.
Installed binary component metadata is tracked in
`external_tools/.versions.json`; if a pinned binary URL, release, or SHA256 in
`config.py` changes, the next setup run reinstalls that binary component.
Git-based components are fetched and checked out to the pinned commit on every
setup run.

RVVTS Python dependencies installed by setup are limited to `numpy`,
`mergedeep`, and `jsonpickle`.

## Run Test Sets

```bash
./02_run_testsets.py
./02_run_testsets.py --xlen 64 --testset-type VS
./02_run_testsets.py --xlen ALL --testset-type ALL --testset_max_fragments_per_run 10
./02_run_testsets.py --xlen 32 --testset-type VS --force
```

`02_run_testsets.py` automatically re-runs itself with
`external_tools/python/bin/python` when that environment exists.

Results are written to:

```text
results/RVVTS_<hash>_Sail_<hash>_Spike_<hash>/RV<xlen>/RVV_vlen128/<VS|IVS>
```

If a target result directory already exists, the script aborts to avoid mixing
old and new results. `--force` deletes the selected target result directories
before running.

## Generate Report

```bash
./03_gen_report.py
./03_gen_report.py --results-dir results --output-dir report
./03_gen_report.py --output-dir report --force
```

The report generator collects the result tree into `report/CASES/` while
preserving the original result directory structure. It omits bulky or transient
runner data such as `ARTIFACTS`, `TestsetCodeErrMinRunner_0`,
`init_config.log`, `run_args.log`, `stats.log`, `task_pre_result.log`, and
`task_result.log`.

Generated output:

```text
report/
  README.md
  cases.csv
  testset_runs.csv
  CATEGORIES/<category>.md
  INSTRUCTIONS/<instruction>.md
  CASES/<original result structure>
```

`README.md` contains a testset-run overview with runner statistics. `Test Cases`
is the number of testcase files in the testset; `Executed Tests`, `Completes`,
`Ignores`, `Timeouts`, `Unknown Faults`, and the error/minimization counters are
the fragment-level `CodeErrMinRunner` results. Outcome percentages are relative
to `Executed Tests`; reduction and minimization percentages are relative to
`Errors`. The README also contains case category and instruction summary tables
split by `RV32 IVS`, `RV32 VS`, `RV64 IVS`, and `RV64 VS`, plus per-row totals
and a final total row. It ends with a linked table for collected non-error cases
such as `IGNORE`, `TIMEOUT`, and `UNKNOWN_FAULT`. Detail pages in `CATEGORIES/`
and `INSTRUCTIONS/` contain the same summary style for the opposite dimension
and link to the concrete case `README.md` files under `CASES/`.

`cases.csv` contains one row per collected case with:

```text
xlen, rvvts_hash, ref, ref_hash, dut, dut_hash, extension, vlen,
testset_type, kind, category, instruction, path
```

`testset_runs.csv` contains one row per testset run with the numeric counters
used for the `Testset Runs` table, without percentages or the total row.

`--force` deletes the output directory before regenerating the report.

## Run One Test

```bash
./04_run_single_test.py --xlen 64 path/to/testcase_code.json
```

`04_run_single_test.py` automatically re-runs itself with
`external_tools/python/bin/python` when that environment exists. The single-test
result directory is `run_test/`. The script prints the result path and the
generated report, and exits with `0` on `COMPLETE` or `255` (`sys.exit(-1)`)
otherwise.

## License

This project is distributed under the BSD 3-clause "New" or "Revised" License.
See [LICENSE](LICENSE).
