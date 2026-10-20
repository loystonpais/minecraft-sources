from typing import Any
from concurrent.futures import ThreadPoolExecutor
from updater.config import REPO_ROOT, RAW_DIR, load_json, save_json, logger
from updater.fetch import fetch_json

MOJANG_RAW_DIR = RAW_DIR / "mojang"
RAW_VERSIONS_DIR = MOJANG_RAW_DIR / "versions"
MOJANG_OUTPUT_DIR = REPO_ROOT / "mojang"
MOJANG_LIBRARIES_FILE = MOJANG_OUTPUT_DIR / "libraries.json"
MANIFEST_FILE = MOJANG_RAW_DIR / "version_manifest_v2.json"


def format_classifier_coord(coord: str, classifier: str) -> str:
    """Appends classifier to coordinate in standard Maven format."""
    parts = coord.split(":")
    if len(parts) == 3:
        return f"{parts[0]}:{parts[1]}:{parts[2]}:{classifier}"
    elif len(parts) == 4:
        return f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}-{classifier}"
    return f"{coord}:{classifier}"


def extract_libraries_from_version_data(data: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Extracts library entries mapping coord -> {url, sha1} from Mojang version package JSON."""
    libraries: dict[str, dict[str, str]] = {}
    for lib in data.get("libraries", []):
        base_name = lib.get("name")
        if not base_name:
            continue

        dl = lib.get("downloads", {})

        # Standard artifact
        if "artifact" in dl:
            art = dl["artifact"]
            url = art.get("url")
            sha1 = art.get("sha1")
            if url and sha1:
                libraries[base_name] = {
                    "url": url,
                    "sha1": sha1,
                }

        # Classifiers (natives, etc.)
        if "classifiers" in dl:
            for classifier, c_info in dl["classifiers"].items():
                url = c_info.get("url")
                sha1 = c_info.get("sha1")
                if url and sha1:
                    coord = format_classifier_coord(base_name, classifier)
                    libraries[coord] = {
                        "url": url,
                        "sha1": sha1,
                    }

    return libraries


def fetch_version_in_memory(v_info: dict[str, Any]) -> dict[str, Any] | None:
    """Fetches version JSON directly in-memory without storing raw files on disk."""
    v_id = v_info.get("id")
    url = v_info.get("url")
    if not v_id or not url:
        return None

    try:
        return fetch_json(url, delay=0.01)
    except Exception as e:
        logger.warning(f"Failed to fetch Mojang version {v_id} from {url}: {e}")
        return None


def load_or_fetch_version(v_info: dict[str, Any]) -> dict[str, Any] | None:
    """Loads version JSON from raw/mojang/versions/<v_id>.json if available, else fetches remotely."""
    v_id = v_info.get("id")
    if v_id:
        local_file = RAW_VERSIONS_DIR / f"{v_id}.json"
        if local_file.exists():
            return load_json(local_file)
    return fetch_version_in_memory(v_info)


def update_mojang_libraries(
    target_versions: list[dict[str, Any]] | None = None,
    full: bool = False,
    limit_versions: int | None = None,
) -> int:
    """Incrementally extracts and merges libraries from Mojang version packages into mojang/libraries.json.

    - If mojang/libraries.json exists and no target_versions are provided (and not full), nothing is fetched.
    - If target_versions is provided (e.g. from manifest diff), only those versions are fetched in-memory.
    - If full is True or mojang/libraries.json doesn't exist, all versions are scanned in-memory.
    """
    logger.info("==> Updating Mojang libraries...")
    existing_libraries = load_json(MOJANG_LIBRARIES_FILE) or {}

    versions_to_scan: list[dict[str, Any]] = []

    if target_versions is not None:
        versions_to_scan = list(target_versions)
    elif not existing_libraries or full:
        # Full scan from manifest
        manifest_data = load_json(MANIFEST_FILE)
        if manifest_data:
            versions_to_scan = manifest_data.get("versions", [])
        else:
            versions_data = load_json(MOJANG_OUTPUT_DIR / "versions.json")
            if versions_data:
                versions_to_scan = list(versions_data.get("versions", {}).values())
            else:
                logger.error("No manifest or versions.json found to scan!")
                return 1
    else:
        logger.info("mojang/libraries.json is already populated and no changed versions were specified.")
        return 0

    if limit_versions and limit_versions > 0:
        versions_to_scan = versions_to_scan[:limit_versions]

    if not versions_to_scan:
        logger.info("No versions to scan. mojang/libraries.json is up to date.")
        return 0

    logger.info(f"Scanning {len(versions_to_scan)} Mojang version(s) in-memory for libraries...")

    # Load from local cache or fetch in parallel directly into memory
    with ThreadPoolExecutor(max_workers=16) as pool:
        version_datas = list(pool.map(load_or_fetch_version, versions_to_scan))

    all_libraries: dict[str, dict[str, str]] = dict(existing_libraries)
    total_added = 0

    for v_data in version_datas:
        if not v_data:
            continue
        v_libs = extract_libraries_from_version_data(v_data)
        for coord, info in v_libs.items():
            if coord not in all_libraries:
                all_libraries[coord] = info
                total_added += 1

    # Keep strictly additive & sorted alphabetically by coordinate
    sorted_libraries = dict(sorted(all_libraries.items()))
    save_json(MOJANG_LIBRARIES_FILE, sorted_libraries)
    logger.info(
        f"Saved {len(sorted_libraries)} total libraries ({total_added} newly added) to {MOJANG_LIBRARIES_FILE}"
    )
    return 0
