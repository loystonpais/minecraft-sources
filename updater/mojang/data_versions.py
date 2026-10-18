import io
import json
import zipfile
from updater.config import REPO_ROOT, RAW_DIR, load_json, save_json, logger
from updater.fetch import fetch_json, fetch_bytes

DATA_VERSIONS_FILE = REPO_ROOT / "mojang" / "data-versions.json"
MANIFEST_FILE = RAW_DIR / "mojang" / "version_manifest_v2.json"
DATA_VERSION_CUTOFF = "2015-08-05T12:22:42+00:00"  # Introduced in 15w32a


def extract_data_version_from_client_jar(client_jar_url: str) -> int | None:
    data = fetch_bytes(client_jar_url, delay=0.1)
    zf = zipfile.ZipFile(io.BytesIO(data))
    if "version.json" in zf.namelist():
        v_data = json.loads(zf.read("version.json").decode("utf-8"))
        return v_data.get("world_version")
    return None


def update_data_versions(target_version_ids: list[str] | None = None) -> int:
    """Updates minecraft-data-versions.json by extracting world_version from client jars."""
    manifest = load_json(MANIFEST_FILE)
    if not manifest:
        logger.error(f"Cannot find or load {MANIFEST_FILE}. Run manifest update first.")
        return 1

    data_versions: dict[str, int] = load_json(DATA_VERSIONS_FILE) or {}
    manifest_versions = {v["id"]: v for v in manifest.get("versions", [])}

    to_process: list[tuple[str, str]] = []

    if target_version_ids:
        for vid in target_version_ids:
            if vid in manifest_versions:
                to_process.append((vid, manifest_versions[vid]["url"]))
            else:
                logger.warning(f"Version '{vid}' not found in {MANIFEST_FILE.name}")
    else:
        for v in manifest.get("versions", []):
            vid = v["id"]
            if (
                vid not in data_versions
                and v.get("releaseTime", "") >= DATA_VERSION_CUTOFF
                and vid != "1.8.9"
            ):
                to_process.append((vid, v["url"]))

    # Ensure the dictionary is sorted by DataVersion integer descending (highest/newest first)
    sorted_versions = dict(sorted(data_versions.items(), key=lambda item: item[1], reverse=True))

    if not to_process:
        logger.info("All target versions already present in data-versions.json")
        if list(data_versions.keys()) != list(sorted_versions.keys()):
            save_json(DATA_VERSIONS_FILE, sorted_versions)
            logger.info(f"Re-sorted versions in {DATA_VERSIONS_FILE}")
        return 0

    logger.info(f"Checking {len(to_process)} Minecraft versions for DataVersion...")
    updated_count = 0

    for vid, meta_url in to_process:
        try:
            logger.info(f"Fetching metadata for {vid}...")
            v_meta = fetch_json(meta_url)
            client_dl = v_meta.get("downloads", {}).get("client", {})
            client_jar_url = client_dl.get("url")
            if not client_jar_url:
                logger.warning(f"No client jar URL found for {vid}")
                continue

            logger.info(f"Downloading client jar for {vid} to inspect version.json...")
            world_ver = extract_data_version_from_client_jar(client_jar_url)
            if world_ver is not None:
                data_versions[vid] = world_ver
                updated_count += 1
                logger.info(f"==> {vid} = {world_ver}")
            else:
                logger.warning(f"world_version not found in {vid} client jar")
        except Exception as e:
            logger.error(f"Failed to fetch data version for {vid}: {e}")

    if updated_count > 0 or not target_version_ids:
        # Sort by DataVersion integer descending (highest/newest first)
        sorted_versions = dict(sorted(data_versions.items(), key=lambda item: item[1], reverse=True))
        save_json(DATA_VERSIONS_FILE, sorted_versions)
        if updated_count > 0:
            logger.info(f"Updated {updated_count} versions in {DATA_VERSIONS_FILE}")
        else:
            logger.info(f"Sorted versions in {DATA_VERSIONS_FILE}")

    return 0
