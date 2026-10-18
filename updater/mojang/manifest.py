from updater.config import REPO_ROOT, RAW_DIR, save_json, logger
from updater.fetch import fetch_json

VERSION_MANIFEST_V2_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_RAW_DIR = RAW_DIR / "mojang"
MANIFEST_FILE = MOJANG_RAW_DIR / "version_manifest_v2.json"
NORMALIZED_VERSIONS_FILE = REPO_ROOT / "mojang" / "minecraft-versions.json"


def normalize_manifest(raw_manifest: dict) -> dict:
    """Normalizes the version manifest into an indexed dict {version_id: version_info}."""
    versions_list = raw_manifest.get("versions", [])
    indexed_versions = {v["id"]: v for v in versions_list}

    latest = raw_manifest.get("latest", {})
    return {
        "latest": latest,
        "versions": indexed_versions,
    }


def update_manifest() -> None:
    """Fetches Mojang version_manifest_v2.json and generates normalized minecraft-versions.json."""
    logger.info(f"Fetching Mojang version manifest from {VERSION_MANIFEST_V2_URL}...")
    data = fetch_json(VERSION_MANIFEST_V2_URL)
    save_json(MANIFEST_FILE, data)
    versions_count = len(data.get("versions", []))
    logger.info(f"Saved {versions_count} versions to {MANIFEST_FILE}")

    # Generate normalized minecraft-versions.json
    normalized = normalize_manifest(data)
    save_json(NORMALIZED_VERSIONS_FILE, normalized)
    logger.info(f"Saved normalized versions to {NORMALIZED_VERSIONS_FILE}")
