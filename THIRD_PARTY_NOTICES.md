# Third-party notices

## LIBERO

This repository depends on the upstream **LIBERO** benchmark repository for task
definitions (BDDL), official initial states (`.pruned_init`) and simulation
assets. LIBERO is distributed under the MIT License:

- Repository: <https://github.com/Lifelong-Robot-Learning/LIBERO>
- Pinned commit: `f78abd68ee283de9f9be3c8f7e2a9ad60246e95c`
- Citation: `arXiv:2306.03310` (Liu et al., *LIBERO: Benchmarking Knowledge
  Transfer for Lifelong Robot Learning*)

LIBERO assets are **not redistributed** in this repository. `scripts/bootstrap_libero.py`
and `scripts/verify_libero.py` only generate a local configuration and verify
the pinned checkout; users obtain the assets from the upstream repository.

## Derived dataset definitions

`dataset/matrices/b-matrix.csv` and `dataset/matrices/d-native-matrix.csv` are
case-matrix definitions developed in the authors' internal `libero-rollback` /
`libero-compose` repositories and imported here with provenance recorded in
`dataset/sources.yaml`. They reference only upstream LIBERO tasks; they do not
redistribute upstream code or assets.

## Models

Model checkpoints are not distributed with this repository. Each model adapter
in `src/libero_rollback/policies/` is an interface to a checkpoint the user
obtains separately, under that model's own license (OpenPI / π0.5, OpenVLA-OFT,
SmolVLA, etc.).
