import os
import re
import base64
import hashlib
from pathlib import Path
from updater.config import REPO_ROOT, RAW_DIR, load_json, save_json, logger
from updater.fetch import fetch_json, fetch_bytes

ASSET_SHA_FILE = REPO_ROOT / "mojang" / "asset-sha1-sha256-map.json"
MANIFEST_FILE = RAW_DIR / "mojang" / "version_manifest_v2.json"
RESOURCE_URL_BASE = "https://resources.download.minecraft.net"


def nix_sha256_sri_from_bytes(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return f"sha256-{base64.b64encode(digest).decode('utf-8')}"


def nix_sha256_sri_from_file(filepath: Path) -> str:
    with filepath.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").digest()
    return f"sha256-{base64.b64encode(digest).decode('utf-8')}"


def update_from_local_directory(directory_path: Path) -> int:
    """Updates asset-sha256.json from local Prism/Mojang assets/objects directory."""
    if not directory_path.is_dir():
        logger.error(f"{directory_path} is not a valid directory")
        return 1

    existing_data: dict[str, str] = load_json(ASSET_SHA_FILE) or {}
    prev_count = len(existing_data)
    new_found = 0

    logger.info(f"Scanning local objects in {directory_path}...")
    for root, _, files in os.walk(directory_path):
        for name in files:
            # Mojang asset objects are 40-char SHA1 hex names
            if re.fullmatch(r"[a-f0-9]{40}", name):
                if name not in existing_data:
                    file_path = Path(root) / name
                    existing_data[name] = nix_sha256_sri_from_file(file_path)
                    new_found += 1

    logger.info(f"Added {new_found} new assets from local cache (Total: {len(existing_data)})")
    if new_found > 0:
        save_json(ASSET_SHA_FILE, existing_data)

    return 0


DEFAULT_REMOTE_ASSET_VERSION_LIMIT = 50


def update_from_remote(limit_versions: int | None = DEFAULT_REMOTE_ASSET_VERSION_LIMIT) -> int:
    """Updates asset-sha1-sha256-map.json by downloading missing assets referenced in version manifest."""
    manifest = load_json(MANIFEST_FILE)
    if not manifest:
        logger.error(f"Cannot find {MANIFEST_FILE}. Please run manifest update first.")
        return 1

    if limit_versions is None:
        limit_versions = DEFAULT_REMOTE_ASSET_VERSION_LIMIT

    existing_data: dict[str, str] = load_json(ASSET_SHA_FILE) or {}
    versions = manifest.get("versions", [])
    if limit_versions:
        versions = versions[:limit_versions]

    missing_hashes: set[str] = set()

    logger.info(f"Scanning asset indexes from {len(versions)} versions in manifest...")
    for v in versions:
        vid = v["id"]
        try:
            v_meta = fetch_json(v["url"])
            asset_index_info = v_meta.get("assetIndex")
            if not asset_index_info or "url" not in asset_index_info:
                continue

            asset_index = fetch_json(asset_index_info["url"])
            objects = asset_index.get("objects", {})

            for obj in objects.values():
                sha1 = obj.get("hash")
                if sha1 and sha1 not in existing_data:
                    missing_hashes.add(sha1)

        except Exception as e:
            logger.warning(f"Failed scanning asset index for {vid}: {e}")

    if not missing_hashes:
        logger.info("All scanned assets are already present in asset-sha256.json")
        return 0

    logger.info(f"Downloading {len(missing_hashes)} missing asset objects from Mojang...")
    added = 0
    for sha1 in missing_hashes:
        url = f"{RESOURCE_URL_BASE}/{sha1[:2]}/{sha1}"
        try:
            raw_bytes = fetch_bytes(url, delay=0.02)
            existing_data[sha1] = nix_sha256_sri_from_bytes(raw_bytes)
            added += 1
            if added % 50 == 0:
                logger.info(f"Downloaded {added}/{len(missing_hashes)} assets...")
        except Exception as e:
            logger.error(f"Failed to download asset {sha1}: {e}")

    if added > 0:
        save_json(ASSET_SHA_FILE, existing_data)
        logger.info(f"Saved {added} new assets to {ASSET_SHA_FILE}")

    return 0
