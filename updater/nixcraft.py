import base64
from pathlib import Path
from typing import Any
from updater.config import REPO_ROOT, save_json, load_json, logger

NIXCRAFT_DIR = REPO_ROOT / "nixcraft"
NIXCRAFT_LIBRARIES_FILE = NIXCRAFT_DIR / "libraries.json"

# Directories that produce libraries.json to pool
SOURCE_LOADERS = ["fabric", "quilt", "forge", "neoforge", "liteloader", "lwjgl"]



def hex_to_sri(hex_digest: str, algo: str = "sha256") -> str:
    """Converts a hex hash digest to W3C SRI format (e.g. sha256-..., sha1-..., md5-...)."""
    cleaned_hex = hex_digest.strip()
    raw_bytes = bytes.fromhex(cleaned_hex)
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"{algo}-{b64}"


def build_libraries() -> None:
    """Merges all loader libraries.json files into nixcraft/libraries.json with SRI hashes."""
    logger.info("==> Building nixcraft/libraries.json from modloader libraries...")
    merged: dict[str, dict[str, Any]] = {}

    for loader_name in SOURCE_LOADERS:
        lib_file = REPO_ROOT / loader_name / "libraries.json"
        if not lib_file.exists():
            continue

        data = load_json(lib_file)
        if not data:
            continue

        logger.info(f"Merging {len(data)} libraries from {loader_name}...")
        for coord, entry in data.items():
            url = entry.get("url")
            if not url:
                continue

            # Determine algorithm and value
            sri_hash = None
            if "hash" in entry:
                sri_hash = entry["hash"]
            elif "sha256" in entry:
                sri_hash = hex_to_sri(entry["sha256"], "sha256")
            elif "sha1" in entry:
                sri_hash = hex_to_sri(entry["sha1"], "sha1")
            elif "md5" in entry:
                sri_hash = hex_to_sri(entry["md5"], "md5")

            if not sri_hash:
                continue

            # Prefer sha256 over sha1/md5 if coordinate is already present
            if coord in merged:
                existing_hash = merged[coord]["hash"]
                if existing_hash.startswith("sha256-") and not sri_hash.startswith("sha256-"):
                    continue

            merged[coord] = {
                "url": url,
                "hash": sri_hash,
            }

    save_json(NIXCRAFT_LIBRARIES_FILE, merged)
    logger.info(f"Saved {len(merged)} total merged libraries to {NIXCRAFT_LIBRARIES_FILE}")
