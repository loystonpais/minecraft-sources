from updater.config import REPO_ROOT, RAW_DIR, save_json, logger
from updater.fetch import fetch_json

VERSION_MANIFEST_V2_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_RAW_DIR = RAW_DIR / "mojang"
MANIFEST_FILE = MOJANG_RAW_DIR / "version_manifest_v2.json"
NORMALIZED_VERSIONS_FILE = REPO_ROOT / "mojang" / "versions.json"
VERSIONS_LIST_FILE = REPO_ROOT / "mojang" / "versions-list.json"


def normalize_manifest(raw_manifest: dict) -> dict:
    """Normalizes the version manifest into an indexed dict {version_id: version_info}."""
    versions_list = raw_manifest.get("versions", [])
    indexed_versions = {v["id"]: v for v in versions_list}

    latest = raw_manifest.get("latest", {})
    return {
        "latest": latest,
        "versions": indexed_versions,
    }


def update_manifest() -> list[dict]:
    """Fetches Mojang version_manifest_v2.json and generates normalized files.

    Returns the list of version objects that are newly added or changed.
    """
    logger.info(f"Fetching Mojang version manifest from {VERSION_MANIFEST_V2_URL}...")
    data = fetch_json(VERSION_MANIFEST_V2_URL)
    save_json(MANIFEST_FILE, data)
    versions = data.get("versions", [])
    versions_count = len(versions)
    logger.info(f"Saved {versions_count} versions to {MANIFEST_FILE}")

    # Detect changed or new versions against current normalized versions.json
    from updater.config import load_json
    existing_normalized = load_json(NORMALIZED_VERSIONS_FILE) or {}
    old_versions = existing_normalized.get("versions", {})

    changed_versions = [
        v for v in versions
        if v.get("id") not in old_versions
        or v.get("sha1") != old_versions[v["id"]].get("sha1")
        or v.get("url") != old_versions[v["id"]].get("url")
    ]

    # Generate normalized versions.json
    normalized = normalize_manifest(data)
    save_json(NORMALIZED_VERSIONS_FILE, normalized)
    logger.info(f"Saved normalized versions to {NORMALIZED_VERSIONS_FILE}")

    # Generate ordered list of version IDs
    version_ids = [v["id"] for v in versions]
    save_json(VERSIONS_LIST_FILE, version_ids)
    logger.info(f"Saved ordered version list ({len(version_ids)} items) to {VERSIONS_LIST_FILE}")

    if changed_versions:
        logger.info(f"Detected {len(changed_versions)} changed/new Mojang versions: {[v['id'] for v in changed_versions]}")
    else:
        logger.info("No changed or new Mojang versions detected.")

    return changed_versions



