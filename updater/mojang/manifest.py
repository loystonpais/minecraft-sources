from concurrent.futures import ThreadPoolExecutor
from updater.config import REPO_ROOT, RAW_DIR, save_json, load_json, logger
from updater.fetch import fetch_json

VERSION_MANIFEST_V2_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MOJANG_RAW_DIR = RAW_DIR / "mojang"
RAW_VERSIONS_DIR = MOJANG_RAW_DIR / "versions"
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


def sync_version_file(version_info: dict) -> tuple[dict, bool]:
    """Downloads and saves raw/mojang/versions/<version_id>.json if missing or out-of-date.

    Returns (version_info, is_new_or_changed).
    """
    v_id = version_info.get("id")
    url = version_info.get("url")
    if not v_id or not url:
        return (version_info, False)

    v_file = RAW_VERSIONS_DIR / f"{v_id}.json"
    if v_file.exists():
        return (version_info, False)

    try:
        data = fetch_json(url, delay=0.01)
        save_json(v_file, data)
        return (version_info, True)
    except Exception as e:
        logger.warning(f"Failed to fetch Mojang version {v_id} from {url}: {e}")
        return (version_info, False)


def update_manifest() -> list[dict]:
    """Fetches Mojang version_manifest_v2.json, downloads raw version specs, and generates normalized files.

    Returns the list of version objects that are newly added or changed.
    """
    logger.info(f"Fetching Mojang version manifest from {VERSION_MANIFEST_V2_URL}...")
    data = fetch_json(VERSION_MANIFEST_V2_URL)
    save_json(MANIFEST_FILE, data)
    versions = data.get("versions", [])
    versions_count = len(versions)
    logger.info(f"Saved {versions_count} versions to {MANIFEST_FILE}")

    # Ensure raw/mojang/versions directory exists
    RAW_VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Detect changed or new versions against current normalized versions.json
    existing_normalized = load_json(NORMALIZED_VERSIONS_FILE) or {}
    old_versions = existing_normalized.get("versions", {})

    changed_versions = [
        v for v in versions
        if v.get("id") not in old_versions
        or v.get("sha1") != old_versions[v["id"]].get("sha1")
        or v.get("url") != old_versions[v["id"]].get("url")
    ]

    # Sync missing or changed version files to raw/mojang/versions/
    versions_to_download = [
        v for v in versions
        if not (RAW_VERSIONS_DIR / f"{v['id']}.json").exists() or v in changed_versions
    ]

    if versions_to_download:
        logger.info(f"Downloading {len(versions_to_download)} raw version file(s) to {RAW_VERSIONS_DIR}...")
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(sync_version_file, versions_to_download))
        newly_saved = sum(1 for _, saved in results if saved)
        logger.info(f"Finished downloading raw version files ({newly_saved} saved).")

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



