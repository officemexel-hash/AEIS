"""Project Mode storage and service helpers for SYLION AEIS."""

from .engine import ProjectExecutionEngine, get_project_execution_engine
from .round_meta_hooks import register_round_meta_hook, round_meta_post_resolve
from .store import ProjectModeStore, get_project_mode_store

# W14 BE-6 — wire round_meta freeze/authorize completion to the
# governance ticket post-resolve registry. Idempotent on repeat import.
register_round_meta_hook()

__all__ = [
    "ProjectExecutionEngine",
    "ProjectModeStore",
    "get_project_execution_engine",
    "get_project_mode_store",
    "register_round_meta_hook",
    "round_meta_post_resolve",
]
