"""LIBERO-Rollback: a controlled-perturbation benchmark for goal-state persistence.

The package is layered so that static tooling (dataset validation, matrix
loading, metrics, reporting) runs without MuJoCo, torch or LIBERO::

    libero_rollback.matrices      # pure-stdlib matrix loading/validation
    libero_rollback.schema        # JSON Schema / metadata validation
    libero_rollback.validation    # dataset-level static validation
    libero_rollback.evidence      # episode verdict classification
    libero_rollback.metrics       # SR / Recovery / EGC / statistics
    libero_rollback.report        # self-contained HTML + aggregate.json
    libero_rollback.runtime.*     # simulation + injection (needs LIBERO/MuJoCo)
    libero_rollback.policies.*    # model adapters (one env per model)
    libero_rollback.runner        # episode loop and batch runner
"""

__version__ = "2.0.0.dev0"

__all__ = ["__version__"]
