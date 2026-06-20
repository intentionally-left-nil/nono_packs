"""
Scenario 11: Jupyter kernel starts and executes cells.

Goal: Confirm that Jupyter and ipykernel start normally under the sandbox
and that cells can perform allowed I/O. This exercises the JUPYTER_*
env var redirects (JUPYTER_RUNTIME_DIR, JUPYTER_DATA_DIR,
JUPYTER_CONFIG_DIR) that the profile injects via set_vars.

Tests:

1. ``test_jupyter_notebook_executes``  — checks IMPORTS_OK and that
   output/summary.csv is created.
2. ``test_jupyter_escape_blocked``     — checks ESCAPE_BLOCKED appears in
   cell outputs (PermissionError for /var/tmp write caught by kernel).
3. ``test_jupyter_runtime_dir``        — checks RUNTIME_DIR_OK appears in
   cell outputs (JUPYTER_RUNTIME_DIR starts with CONDA_PREFIX).

All three tests share a session fixture ``executed_notebook`` that runs
``jupyter nbconvert --to notebook --execute`` once and returns the output
notebook path.

Implementation note — escape path is /var/tmp, not /tmp:
    The spec mentions /tmp/escaped.txt but the macOS sandbox grants r+w to
    the entire /tmp hierarchy when the test prefix (/tmp/nono-pypack-test) is
    listed via --allow.  This is the same enforcement gap documented in
    test_webserver.py.  We use /var/tmp/jupyter_escape.txt instead.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_PREFIX = Path("/tmp/nono-pypack-test")
CONDA = shutil.which("conda")

# Minimal CSV written to tmpdir so cell 2 can read it.
INPUT_CSV = "name,value\nalpha,1\nbeta,2\ngamma,3\n"

# ---------------------------------------------------------------------------
# Notebook definition
# ---------------------------------------------------------------------------

def _build_notebook() -> dict:
    """
    Return a minimal nbformat v4 notebook dict with four code cells:

    Cell 0: import pandas and matplotlib, print IMPORTS_OK
    Cell 1: read input.csv, compute describe(), write output/summary.csv
    Cell 2: attempt /var/tmp write (blocked), catch error, print ESCAPE_BLOCKED
    Cell 3: assert JUPYTER_RUNTIME_DIR starts with CONDA_PREFIX, print RUNTIME_DIR_OK
    """
    def code_cell(source: str) -> dict:
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": source,
        }

    cells = [
        code_cell(
            "import pandas as pd, matplotlib\n"
            "print('IMPORTS_OK')"
        ),
        code_cell(
            "import pandas as pd, os\n"
            "df = pd.read_csv('input.csv')\n"
            "summary = df.describe()\n"
            "os.makedirs('output', exist_ok=True)\n"
            "summary.to_csv('output/summary.csv')\n"
            "print('CSV_WRITTEN')"
        ),
        code_cell(
            "try:\n"
            "    open('/var/tmp/jupyter_escape.txt', 'w').write('escaped')\n"
            "    print('ESCAPE_NOT_BLOCKED')\n"
            "except (PermissionError, OSError):\n"
            "    print('ESCAPE_BLOCKED')"
        ),
        code_cell(
            "import os\n"
            "rdir = os.environ['JUPYTER_RUNTIME_DIR']\n"
            "prefix = os.environ['CONDA_PREFIX']\n"
            "assert rdir.startswith(prefix), (\n"
            "    f'JUPYTER_RUNTIME_DIR={rdir!r} does not start with CONDA_PREFIX={prefix!r}'\n"
            ")\n"
            "print('RUNTIME_DIR_OK')"
        ),
    ]

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12",
            },
        },
        "cells": cells,
    }


# ---------------------------------------------------------------------------
# Fixture: install jupyter deps
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def jupyter_deps(python_prefix: Path, patched_policy: str) -> None:
    """
    Ensure jupyter, ipykernel, pandas, and matplotlib are installed in the
    test prefix.  Depends on patched_policy to guarantee the prefix exists
    and the pack is sideloaded first.  Idempotent: checks whether the packages
    are already importable before attempting any install.
    """
    python_bin = python_prefix / "bin" / "python"

    # Fast-path: already installed.
    check = subprocess.run(
        [str(python_bin), "-c",
         "import jupyter_core, ipykernel, pandas, matplotlib"],
        capture_output=True,
    )
    if check.returncode == 0:
        return

    if CONDA:
        result = subprocess.run(
            [
                CONDA, "install", "-p", str(python_prefix),
                "--override-channels", "-c", "defaults",
                "jupyter", "ipykernel", "pandas", "matplotlib",
                "--yes", "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return
        # Fall through to pip if conda fails.

    python_bin_str = str(python_bin)
    subprocess.run(
        [python_bin_str, "-m", "pip", "install", "--quiet",
         "jupyter", "ipykernel", "pandas", "matplotlib"],
        check=True,
    )


# ---------------------------------------------------------------------------
# Fixture: execute the notebook once; share result across all tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def executed_notebook(
    sandbox,
    jupyter_deps: None,
    python_prefix: Path,
) -> Path:
    """
    Write a temporary notebook to a temp dir, run it with
    ``jupyter nbconvert --to notebook --execute`` inside the sandbox, and
    return the path to the output notebook.

    The temp dir is kept alive for the lifetime of the test session (it is
    passed via extra_allow so the sandbox can write to it) and cleaned up
    afterwards.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="nono-jupyter-test-"))
    try:
        # Write input CSV so cell 1 can read it.
        (tmpdir / "input.csv").write_text(INPUT_CSV)

        # Write the notebook.
        nb_path = tmpdir / "test_notebook.ipynb"
        out_nb_path = tmpdir / "test_notebook_output.ipynb"
        nb_path.write_text(json.dumps(_build_notebook(), indent=2))

        # Pre-create jupyter dirs that the policy's set_vars point at.
        # before.sh normally does this, but it may not have run yet when
        # running individual test files.
        for subdir in (
            "tmp/jupyter/runtime",
            "tmp/jupyter/config",
            "tmp/ipython",
            "share/jupyter",
        ):
            (python_prefix / subdir).mkdir(parents=True, exist_ok=True)

        # Run nbconvert inside the sandbox.
        proc = sandbox.popen(
            [
                "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                str(nb_path),
                "--output", str(out_nb_path),
                "--ExecutePreprocessor.timeout=60",
            ],
            extra_allow=[str(tmpdir)],
            cwd=str(tmpdir),
        )

        try:
            rc = proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            out_bytes, err_bytes = proc.communicate()
            pytest.fail(
                "jupyter nbconvert timed out after 120 s.\n"
                f"stdout: {out_bytes.decode(errors='replace')!r}\n"
                f"stderr: {err_bytes.decode(errors='replace')!r}"
            )

        # Collect stdout/stderr for diagnostics.
        out_bytes, err_bytes = proc.communicate()

        if rc != 0:
            pytest.fail(
                f"jupyter nbconvert exited with code {rc}.\n"
                f"stdout: {out_bytes.decode(errors='replace')!r}\n"
                f"stderr: {err_bytes.decode(errors='replace')!r}"
            )

        if not out_nb_path.exists():
            pytest.fail(
                f"Output notebook not found at {out_nb_path}.\n"
                f"stdout: {out_bytes.decode(errors='replace')!r}\n"
                f"stderr: {err_bytes.decode(errors='replace')!r}"
            )

        yield out_nb_path

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_cell_text(nb: dict) -> list[str]:
    """
    Return a flat list of all text output strings from every cell in the
    executed notebook.  Handles both ``stream`` outputs (stdout/stderr) and
    ``error`` outputs (ename + evalue + traceback).
    """
    texts: list[str] = []
    for cell in nb.get("cells", []):
        for output in cell.get("outputs", []):
            otype = output.get("output_type", "")
            if otype == "stream":
                text = output.get("text", "")
                if isinstance(text, list):
                    texts.append("".join(text))
                else:
                    texts.append(str(text))
            elif otype == "error":
                texts.append(output.get("ename", ""))
                texts.append(output.get("evalue", ""))
                for line in output.get("traceback", []):
                    texts.append(line)
    return texts


def _all_output(executed_notebook_path: Path) -> str:
    """Load the output notebook and return all cell text as one big string."""
    nb = json.loads(executed_notebook_path.read_text())
    return "\n".join(_collect_cell_text(nb))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_jupyter_notebook_executes(executed_notebook: Path, python_prefix: Path) -> None:
    """
    The notebook executes to completion:
    - cell 0 prints IMPORTS_OK (pandas + matplotlib importable)
    - cell 1 writes output/summary.csv in CWD
    """
    all_text = _all_output(executed_notebook)

    assert "IMPORTS_OK" in all_text, (
        f"Expected 'IMPORTS_OK' in notebook outputs, got:\n{all_text}"
    )

    # The output CSV is written relative to the tmpdir CWD.
    # The fixture's tmpdir is cleaned up after the session, but while the
    # test runs we can read the output notebook's parent to find it.
    output_csv = executed_notebook.parent / "output" / "summary.csv"
    assert output_csv.exists(), (
        f"Expected output/summary.csv to be created at {output_csv}, "
        f"but it was not found.\nAll output:\n{all_text}"
    )


def test_jupyter_escape_blocked(executed_notebook: Path) -> None:
    """
    Cell 3 (0-indexed cell 2) attempts open('/var/tmp/jupyter_escape.txt', 'w').
    This should raise a PermissionError (or OSError); the cell catches it and
    prints ESCAPE_BLOCKED.  Critically, subsequent cells still execute
    (the kernel must not crash).
    """
    all_text = _all_output(executed_notebook)

    assert "ESCAPE_BLOCKED" in all_text, (
        f"Expected 'ESCAPE_BLOCKED' in notebook outputs.\n"
        f"All output:\n{all_text}"
    )

    # Also verify kernel did not crash: RUNTIME_DIR_OK from the last cell
    # must appear (subsequent cell ran successfully).
    assert "RUNTIME_DIR_OK" in all_text, (
        "Expected 'RUNTIME_DIR_OK' in notebook outputs — the kernel may have "
        f"crashed after the escape attempt.\nAll output:\n{all_text}"
    )


def test_jupyter_runtime_dir(executed_notebook: Path) -> None:
    """
    Cell 4 (0-indexed cell 3) asserts that JUPYTER_RUNTIME_DIR starts with
    CONDA_PREFIX and prints RUNTIME_DIR_OK if it passes.
    """
    all_text = _all_output(executed_notebook)

    assert "RUNTIME_DIR_OK" in all_text, (
        f"Expected 'RUNTIME_DIR_OK' in notebook outputs.\n"
        f"All output:\n{all_text}"
    )
