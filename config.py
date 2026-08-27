# coding: utf-8
#
# (C) 2026 Manfred Schlaegl <manfred.schlaegl@jku.at>, Institute for Complex Systems, JKU Linz
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

VECTOR_VLEN = 128
VECTOR_VELEN = 64
EXTENSIONS_UNDER_TEST = ["v"]

RVVTS = {
    "url": "https://github.com/ics-jku/RVVTS.git",
    "ref": "f6f1f9557aaa6cbec758be8b31c1271c0d796174",
    "dir": "RVVTS",
}

SPIKE = {
    "url": "https://github.com/riscv-software-src/riscv-isa-sim.git",
    "ref": "650c1a25a15d9de58026d2129c7b81794ed279fe",
    "dir": "riscv-isa-sim",
}

SAIL_RISCV = {
    "url": "https://github.com/riscv/sail-riscv.git",
    "ref": "5df5ca408122b5f08c916ec7bcac6e156090a06c",
    "dir": "sail-riscv",
}

TESTSETS = {
    "url": "https://github.com/ics-jku/RVVTS_SailRV_Spike.git",
    "ref": "bb78189768f591c7f0186335af8aeaeebe6e5379",
    "dir": "RVVTS_SailRV_Spike",
    "generated_subdir": "TestSets_RVV_RefSpike_VLEN128_v1/00_GENERATED_TESTSETS",
    "testcase_pattern": "testcase_code.json",
}

SAIL_COMPILER = {
    "url": "https://github.com/rems-project/sail.git",
    # Latest official binary release as of 2026-08-28. The repository HEAD is
    # newer, but no newer binary release is available.
    "ref": "3b7af38d66466ecadad563158b07ce2f82fe05da",
    "release": "0.20.2-binary",
    "dir": "sail",
    "assets": {
        "x86_64": {
            "url": "https://github.com/rems-project/sail/releases/download/0.20.2-binary/sail-Linux-x86_64.tar.gz",
            "sha256": "26b59bcab2d66e9f220d317dfe45f8b09170ed70e59a824553d6f525134d1ff6",
        },
    },
}

# Official prebuilt GCC-only ELF/Newlib toolchains from
# https://github.com/riscv-collab/riscv-gnu-toolchain/releases/tag/2026.08.27
TOOLCHAIN = {
    "url": "https://github.com/riscv-collab/riscv-gnu-toolchain.git",
    "ref": "d118e5335a33d4dc77fdc64e5a5223931ab422a0",
    "release": "2026.08.27",
    "dir": "riscv-gnu-toolchain-prebuilt",
    "assets": {
        "x86_64-ubuntu-22.04": {
            "url": "https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2026.08.27/riscv64-elf-ubuntu-22.04-gcc.tar.xz",
            "sha256": "dcfb2234a45f2166e33ae9124dec8b5253e6d08e63be139fc4d0014b2802f964",
        },
        "x86_64-ubuntu-24.04": {
            "url": "https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2026.08.27/riscv64-elf-ubuntu-24.04-gcc.tar.xz",
            "sha256": "fe7dadf99dfaee59855b4be5f8d491dc66593bec295090e155a3ec51f0d14f56",
        },
    },
}

PYTHON_DEPS = ["numpy", "mergedeep", "jsonpickle"]
