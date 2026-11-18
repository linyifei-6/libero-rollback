"""Simulation-side runtime: LIBERO environment bootstrap, injection, video.

This subpackage is only importable on an evaluation machine with the
simulation stack installed (``requirements-sim.lock.txt``).  The static layer of
the benchmark (matrix loading / validation / evidence / metrics / report) never
imports it, and :mod:`libero_rollback.runner` imports it lazily inside the
episode loop so that ``--dry-run`` works without MuJoCo.

Modules
-------
``env``
    Locate the upstream LIBERO checkout through ``LIBERO_HOME``, write the
    repo-local ``LIBERO_CONFIG_PATH`` configuration and load one
    ``.pruned_init`` row.
``perturbation``
    The ``C0``/``L0``/``L1``/``L2`` injection family with geometry, validity
    gating and the state-write restorable oracle (needs numpy + a live env).
``video``
    Annotated H.264 episode recorder with an injection decision card (needs
    numpy + Pillow, plus PyAV or imageio for encoding).
"""

from __future__ import annotations

__all__ = ["env", "perturbation", "video"]
