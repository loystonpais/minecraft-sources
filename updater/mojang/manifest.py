from updater.config import RAW_DIR, save_json, logger
from updater.fetch import fetch_json

VERSION_MANIFEST_V2_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_RAW_DIR = RAW_DIR / "mojang"
MANIFEST_FILE = MOJANG_RAW_DIR / "version_manifest_v2.json"


def update_manifest() -> None:
    """Fetches Mojang version_manifest_v2.json into raw/mojang/."""
    logger.info(f"Fetching Mojang version manifest from {VERSION_MANIFEST_V2_URL}...")
    data = fetch_json(VERSION_MANIFEST_V2_URL)
    save_json(MANIFEST_FILE, data)
    versions_count = len(data.get("versions", []))
    logger.info(f"Saved {versions_count} versions to {MANIFEST_FILE}")
