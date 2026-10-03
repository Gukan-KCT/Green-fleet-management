"""
Code and Configuration Hash Utility for Staleness and Freshness Verification.

Computes a deterministic SHA-256 hash across all Python source files in src/
and configuration files in config/params.yaml.
"""

from __future__ import annotations
import hashlib
import pickle
from pathlib import Path
from typing import Optional, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def compute_code_hash(project_root: Optional[Path] = None) -> str:
    """
    Computes a deterministic hex hash over all .py files in src/
    and the config/params.yaml configuration file.
    """
    root = project_root or PROJECT_ROOT
    hasher = hashlib.sha256()

    # 1. Config file
    cfg_file = root / "config" / "params.yaml"
    if cfg_file.exists():
        hasher.update(cfg_file.read_bytes())

    # 2. Source files in src/ sorted deterministically
    src_dir = root / "src"
    if src_dir.exists():
        py_files = sorted(src_dir.rglob("*.py"))
        for p in py_files:
            # Hash relative path and contents
            hasher.update(str(p.relative_to(root)).encode("utf-8"))
            hasher.update(p.read_bytes())

    return hasher.hexdigest()[:16]


# Aliases for consistent naming across modules
get_codebase_hash = compute_code_hash
CURRENT_CODE_HASH = compute_code_hash()


def verify_pkl_freshness(pkl_data: Any, current_hash: Optional[str] = None) -> bool:
    """
    Verifies if a loaded pickle dictionary contains a matching 'code_hash'.
    Returns True if valid and fresh, False if stale or missing.
    """
    if not isinstance(pkl_data, dict):
        return True  # If not a dict with metadata, pass
    stored_hash = pkl_data.get("code_hash")
    if not stored_hash:
        return False
    curr = current_hash or compute_code_hash()
    return stored_hash == curr


def check_artifact_staleness(filename: str, current_hash: Optional[str] = None) -> bool:
    """
    Checks if a pickle file on disk in data/ is stale relative to the active codebase hash.
    Returns True if stale or missing, False if fresh.
    """
    data_path = PROJECT_ROOT / "data" / filename
    if not data_path.exists():
        return True
    try:
        with open(data_path, "rb") as f:
            data = pickle.load(f)
        return not verify_pkl_freshness(data, current_hash=current_hash)
    except Exception:
        return True
