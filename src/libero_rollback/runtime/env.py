"""LIBERO runtime bootstrap helpers (repo-local, no precursor repositories).

The helpers here are the only place in the runner that knows how the upstream
LIBERO checkout is wired:

* :func:`resolve_libero_home` reads the checkout location from ``--libero-home``
  or ``LIBERO_HOME`` (never from a hard-coded host path);
* :func:`write_libero_config` writes the five-key ``config.yaml`` that the
  upstream ``libero`` package reads from ``LIBERO_CONFIG_PATH`` (never
  ``~/.libero``);
* :func:`bootstrap_environment` sets ``MUJOCO_GL`` / ``PYTHONPATH`` /
  ``LIBERO_CONFIG_PATH`` *before* robosuite is imported;
* :func:`load_init_row` reads one row of an official ``.pruned_init`` file,
  with an optional subprocess fallback interpreter for torch-less simulators.

Everything that needs numpy/torch/yaml is imported inside the function body so
this module can be imported (and the error paths unit-tested) in the CPU-only
static environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

#: Probe executed by the fallback interpreter when the simulator env cannot
#: import torch itself.  Kept as a string so no torch import leaks into the
#: CPU-only environment.
_INIT_ROW_PROBE = r"""
import json
import sys

import numpy as np
import torch

path, row_index = sys.argv[1], int(sys.argv[2])
payload = torch.load(path, map_location="cpu", weights_only=False)
array = payload.detach().cpu().numpy() if torch.is_tensor(payload) else np.asarray(payload)
row = np.asarray(array[row_index], dtype=np.float64)
payload = {
    "shape": [int(size) for size in array.shape],
    "row": [float(value) for value in row],
}
print(json.dumps(payload))
"""


def resolve_libero_home(cli_value: str | None = None) -> Path:
    """Return the upstream LIBERO checkout root.

    ``cli_value`` (``--libero-home``) wins over ``LIBERO_HOME``.  The returned
    path is the repository root that contains the ``libero`` package unless it
    already points at the package itself; both layouts are accepted by
    :func:`write_libero_config`.
    """

    value = cli_value or os.environ.get("LIBERO_HOME")
    if not value:
        raise RuntimeError(
            "LIBERO checkout not configured: pass --libero-home or set LIBERO_HOME "
            "to the upstream LIBERO repository root"
        )
    return Path(value).expanduser()


def resolve_init_python(cli_value: str | None = None) -> str | None:
    """Interpreter used only to load ``.pruned_init`` rows (needs torch)."""

    return cli_value or os.environ.get("LIBERO_INIT_PYTHON") or None


def _libero_package_dir(libero_root: Path) -> Path:
    """Locate the ``libero/libero`` package that owns the benchmark assets."""

    candidates = (libero_root / "libero" / "libero", libero_root)
    for candidate in candidates:
        if (candidate / "__init__.py").is_file() and (candidate / "bddl_files").is_dir():
            return candidate
    raise FileNotFoundError(
        "raw LIBERO package not found under --libero-home/LIBERO_HOME: expected "
        f"{libero_root / 'libero' / 'libero'} (or the package directory itself) "
        "to contain __init__.py and bddl_files/"
    )


def write_libero_config(config_dir: str | Path, libero_root: str | Path) -> Path:
    """Write the repo-local ``LIBERO_CONFIG_PATH`` ``config.yaml``.

    The upstream ``libero`` package reads five keys: ``benchmark_root``,
    ``bddl_files``, ``init_states``, ``datasets`` and ``assets``.  The config
    directory must be repo-local (e.g. ``<run>/libero_config``); pointing it at
    the global ``~/.libero`` is explicitly out of contract.
    """

    root = Path(libero_root).expanduser()
    package_dir = _libero_package_dir(root)
    assets_dir = package_dir / "assets"
    for required in (package_dir / "bddl_files", package_dir / "init_files", assets_dir):
        if not required.is_dir():
            raise FileNotFoundError(f"raw LIBERO assets incomplete: missing {required}")
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config = {
        "benchmark_root": str(package_dir),
        "bddl_files": str(package_dir / "bddl_files"),
        "init_states": str(package_dir / "init_files"),
        "datasets": str(root / "datasets"),
        "assets": str(assets_dir),
    }
    import yaml  # PyYAML is a core dependency

    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def bootstrap_environment(
    libero_root: str | Path, config_dir: str | Path
) -> dict[str, Any]:
    """Set the environment variables robosuite/libero need before import."""

    root = Path(libero_root).expanduser()
    os.environ.setdefault("MUJOCO_GL", "osmesa")
    pythonpath = [str(root)]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    os.environ["PYTHONPATH"] = os.pathsep.join(pythonpath)
    config_path = write_libero_config(config_dir, root)
    os.environ["LIBERO_CONFIG_PATH"] = str(Path(config_dir))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return {
        "libero_root": str(root),
        "libero_config_path": str(config_path),
        "mujoco_gl": os.environ.get("MUJOCO_GL"),
    }


def _fallback_load_init_row(
    path: Path, row_index: int, python: str
) -> tuple[list[int], Any]:
    import numpy as np

    completed = subprocess.run(
        [python, "-c", _INIT_ROW_PROBE, str(path), str(row_index)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        message = " ".join(completed.stderr.strip().splitlines()[-3:])
        raise RuntimeError(
            f".pruned_init probe exited {completed.returncode} via {python!r}: {message[-400:]}"
        )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    return [int(size) for size in payload["shape"]], np.asarray(payload["row"], dtype=np.float64)


def load_init_row(
    path: str | Path, row_index: int, init_python: str | None = None
) -> tuple[list[int], Any]:
    """Load one row of an official ``.pruned_init`` file.

    ``.pruned_init`` files are ``torch.save`` archives, so reading them needs
    torch.  When the simulation interpreter cannot import torch, an optional
    ``init_python`` (``--libero-python`` / ``LIBERO_INIT_PYTHON``) interpreter is
    used through a subprocess instead.  A missing loader is a hard error: the
    runner never fabricates an init state.
    """

    init_path = Path(path).expanduser()
    if not init_path.is_file():
        raise FileNotFoundError(f"init file not found: {init_path}")
    try:
        import numpy as np
        import torch

        payload = torch.load(str(init_path), map_location="cpu", weights_only=False)
        array = payload.detach().cpu().numpy() if torch.is_tensor(payload) else np.asarray(payload)
        row = np.asarray(array[int(row_index)], dtype=np.float64)
        return [int(size) for size in array.shape], row
    except Exception as direct_error:  # noqa: BLE001 - fall back, then report both
        python = resolve_init_python(init_python)
        if python is None or not Path(python).exists():
            raise RuntimeError(
                f"cannot load .pruned_init {init_path} (in-process error: {direct_error}) "
                "and no fallback interpreter was configured (--libero-python / "
                "LIBERO_INIT_PYTHON)"
            ) from direct_error
        try:
            return _fallback_load_init_row(init_path, int(row_index), python)
        except Exception as subprocess_error:  # noqa: BLE001
            raise RuntimeError(
                f"cannot load .pruned_init {init_path} via {python!r}: {subprocess_error} "
                f"(in-process error: {direct_error})"
            ) from subprocess_error
