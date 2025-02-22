# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Functionality for a shared binary build and release path for all tests."""

import os
import platform
from pathlib import Path

from framework import defs, utils
from framework.defs import (
    FC_BINARY_NAME,
    FC_WORKSPACE_DIR,
    FC_WORKSPACE_TARGET_DIR,
    JAILER_BINARY_NAME,
)
from framework.with_filelock import with_filelock

CARGO_BUILD_REL_PATH = "firecracker_binaries"
"""Keep a single build path across all build tests."""

CARGO_RELEASE_REL_PATH = os.path.join(CARGO_BUILD_REL_PATH, "release")
"""Keep a single Firecracker release binary path across all test types."""


DEFAULT_BUILD_TARGET = "{}-unknown-linux-musl".format(platform.machine())
RELEASE_BINARIES_REL_PATH = "{}/release/".format(DEFAULT_BUILD_TARGET)

CARGO_UNITTEST_REL_PATH = os.path.join(CARGO_BUILD_REL_PATH, "test")


@with_filelock
def cargo_build(path, extra_args="", src_dir="", extra_env=""):
    """Trigger build depending on flags provided."""
    cmd = "CARGO_TARGET_DIR={} {} cargo build {}".format(path, extra_env, extra_args)
    if src_dir:
        cmd = "cd {} && {}".format(src_dir, cmd)

    utils.run_cmd(cmd)


def cargo_test(path, extra_args=""):
    """Trigger unit tests depending on flags provided."""
    path = os.path.join(path, CARGO_UNITTEST_REL_PATH)
    cmd = (
        "CARGO_TARGET_DIR={} RUST_TEST_THREADS=1 RUST_BACKTRACE=1 "
        'RUSTFLAGS="{}" cargo test {} --all --no-fail-fast'.format(
            path, get_rustflags(), extra_args
        )
    )
    utils.run_cmd(cmd)


@with_filelock
def get_firecracker_binaries():
    """Build the Firecracker and Jailer binaries if they don't exist.

    Returns the location of the firecracker related binaries eventually after
    building them in case they do not exist at the specified root_path.
    """
    target = DEFAULT_BUILD_TARGET
    target_dir = FC_WORKSPACE_TARGET_DIR
    out_dir = Path(f"{target_dir}/{target}/release")
    fc_bin_path = out_dir / FC_BINARY_NAME
    jailer_bin_path = out_dir / JAILER_BINARY_NAME

    if not fc_bin_path.exists():
        cd_cmd = "cd {}".format(FC_WORKSPACE_DIR)
        flags = 'RUSTFLAGS="{}"'.format(get_rustflags())
        cargo_default_cmd = f"cargo build --release --target {target}"
        cargo_jailer_cmd = f"cargo build -p jailer --release --target {target}"
        cmd = "{0} && {1} {2} && {1} {3}".format(
            cd_cmd, flags, cargo_default_cmd, cargo_jailer_cmd
        )

        utils.run_cmd(cmd)
        utils.run_cmd(f"strip --strip-debug {fc_bin_path} {jailer_bin_path}")

    return fc_bin_path, jailer_bin_path


def get_rustflags():
    """Get the relevant rustflags for building/unit testing."""
    rustflags = "-D warnings"
    if platform.machine() == "aarch64":
        rustflags += " -C link-arg=-lgcc -C link-arg=-lfdt "
    return rustflags


@with_filelock
def run_seccompiler_bin(bpf_path, json_path=defs.SECCOMP_JSON_DIR, basic=False):
    """
    Run seccompiler-bin.

    :param bpf_path: path to the output file
    :param json_path: optional path to json file
    """
    cargo_target = "{}-unknown-linux-musl".format(platform.machine())

    # If no custom json filter, use the default one for the current target.
    if json_path == defs.SECCOMP_JSON_DIR:
        json_path = json_path / "{}.json".format(cargo_target)

    cmd = "cargo run -p seccompiler --target-dir {} --target {} --\
        --input-file {} --target-arch {} --output-file {}".format(
        defs.SECCOMPILER_TARGET_DIR,
        cargo_target,
        json_path,
        platform.machine(),
        bpf_path,
    )

    if basic:
        cmd += " --basic"

    rc, _, _ = utils.run_cmd(cmd)

    assert rc == 0


@with_filelock
def run_rebase_snap_bin(base_snap, diff_snap):
    """
    Run apply_diff_snap.

    :param base_snap: path to the base snapshot mem file
    :param diff_snap: path to diff snapshot mem file
    """
    cargo_target = "{}-unknown-linux-musl".format(platform.machine())

    cmd = "cargo run -p rebase-snap --target {} --\
        --base-file {} --diff-file {}".format(
        cargo_target, base_snap, diff_snap
    )

    rc, _, _ = utils.run_cmd(cmd)

    assert rc == 0
