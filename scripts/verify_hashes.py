"""
Quick verification script for pickle artifact code hash matching.
"""

from pathlib import Path
import pickle
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.hashing import compute_code_hash

def check_all_hashes():
    curr_hash = compute_code_hash()
    print(f"Active Codebase SHA-256 Hash: {curr_hash}")
    print("=" * 70)
    print(f"{'Pickle File':<35} | {'Stored Hash':<16} | {'Current Hash':<16} | {'Status'}")
    print("-" * 70)

    data_dir = PROJECT_ROOT / "data"
    pkl_files = sorted(data_dir.glob("*.pkl"))

    all_matched = True
    for p in pkl_files:
        with open(p, "rb") as f:
            data = pickle.load(f)
        stored_hash = "N/A"
        if isinstance(data, dict):
            stored_hash = data.get("code_hash", "None")
        status = "MATCH" if stored_hash == curr_hash else "STALE"
        if status == "STALE":
            all_matched = False
        print(f"{p.name:<35} | {str(stored_hash):<16} | {curr_hash:<16} | {status}")

    print("=" * 70)
    if all_matched:
        print("ALL PICKLE ARTIFACTS ARE FRESH AND VERIFIED!")
    else:
        print("WARNING: SOME ARTIFACTS ARE STALE.")

if __name__ == "__main__":
    check_all_hashes()
