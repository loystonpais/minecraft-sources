from pathlib import Path
from updater.config import REPO_ROOT, RAW_DIR, PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json

LWJGL_RAW_DIR = RAW_DIR / "lwjgl"
LWJGL_DOMAIN_DIR = REPO_ROOT / "lwjgl"

LWJGL_PACKAGES = [
    ("org.lwjgl3", "lwjgl3-index.json"),
    ("org.lwjgl", "lwjgl2-index.json"),
]


def update_lwjgl() -> None:
    """Fetches LWJGL 2 and 3 raw component metadata and generates lwjgl/ domain files."""
    logger.info("==> Updating LWJGL sources...")
    LWJGL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    LWJGL_DOMAIN_DIR.mkdir(parents=True, exist_ok=True)

    all_version_ids: list[str] = []
    versions_data: dict[str, dict] = {}
    libraries_data: dict[str, dict] = {}

    for pkg_uid, raw_index_filename in LWJGL_PACKAGES:
        index_url = f"{PRISM_META_BASE}/{pkg_uid}/index.json"
        logger.info(f"Fetching LWJGL index from {index_url}...")
        index_data = fetch_json(index_url)
        save_json(LWJGL_RAW_DIR / raw_index_filename, index_data)

        raw_versions = index_data.get("versions", [])
        logger.info(f"Found {len(raw_versions)} versions for {pkg_uid}")

        for v_entry in raw_versions:
            ver = v_entry.get("version")
            if not ver:
                continue

            all_version_ids.append(ver)

            # Fetch component specification
            comp_url = f"{PRISM_META_BASE}/{pkg_uid}/{ver}.json"
            raw_comp_file = LWJGL_RAW_DIR / "components" / f"{ver}.json"
            
            comp_spec = load_json(raw_comp_file)
            if not comp_spec:
                logger.info(f"  Fetching {pkg_uid} version {ver}...")
                comp_spec = fetch_json(comp_url, delay=0.02)
                save_json(raw_comp_file, comp_spec)

            versions_data[ver] = comp_spec

            # Extract libraries and hashes
            for lib_entry in comp_spec.get("libraries", []):
                name = lib_entry.get("name")
                if not name:
                    continue

                dl = lib_entry.get("downloads", {}).get("artifact", {})
                url = dl.get("url") or lib_entry.get("url")
                sha1 = dl.get("sha1") or lib_entry.get("sha1")
                sha256 = dl.get("sha256") or lib_entry.get("sha256")

                if url and (sha1 or sha256):
                    entry = {"url": url}
                    if sha256:
                        entry["sha256"] = sha256
                    if sha1:
                        entry["sha1"] = sha1
                    libraries_data[name] = entry

    # 1. Save versions-list.json
    versions_list_file = LWJGL_DOMAIN_DIR / "versions-list.json"
    save_json(versions_list_file, all_version_ids)
    logger.info(f"Saved {len(all_version_ids)} versions to {versions_list_file}")

    # 2. Save versions.json
    versions_file = LWJGL_DOMAIN_DIR / "versions.json"
    save_json(versions_file, versions_data)
    logger.info(f"Saved {len(versions_data)} version specs to {versions_file}")

    # 3. Save libraries.json
    libraries_file = LWJGL_DOMAIN_DIR / "libraries.json"
    save_json(libraries_file, libraries_data)
    logger.info(f"Saved {len(libraries_data)} libraries to {libraries_file}")
