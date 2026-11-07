from updater.config import REPO_ROOT, RAW_DIR, save_json, load_json, logger
from updater.fetch import fetch_json, fetch_stream_sha256, fetch_server_jar_metadata

PURPUR_API_BASE = "https://api.purpurmc.org/v2"


def update_purpur() -> None:
    """Updates raw Purpur metadata and normalized builds."""
    logger.info("==> Updating Purpur...")

    # 1. Fetch raw project manifest
    manifest_url = f"{PURPUR_API_BASE}/purpur"
    raw_manifest = fetch_json(manifest_url)

    raw_file = RAW_DIR / "purpur" / "project.json"
    save_json(raw_file, raw_manifest)
    logger.info(f"Saved raw Purpur manifest to {raw_file}")

    # 2. Extract versions list (upstream is ascending, we reverse to match newer-first order)
    versions_raw: list[str] = raw_manifest.get("versions", [])
    versions_list = list(reversed(versions_raw))

    versions_list_file = REPO_ROOT / "purpur" / "versions-list.json"
    save_json(versions_list_file, versions_list)
    logger.info(f"Saved {len(versions_list)} versions to {versions_list_file}")

    # 3. Load existing builds to avoid re-streaming/hashing jars when build ID has not changed
    builds_file = REPO_ROOT / "purpur" / "builds.json"
    existing_builds: dict[str, dict] = load_json(builds_file) or {}
    updated_builds: dict[str, dict] = dict(existing_builds)

    total_versions = len(versions_list)
    for idx, ver in enumerate(versions_list, 1):
        try:
            ver_url = f"{PURPUR_API_BASE}/purpur/{ver}"
            ver_data = fetch_json(ver_url, delay=0.05)
            latest_build_str = ver_data.get("builds", {}).get("latest")
            if not latest_build_str:
                logger.warning(f"[{idx}/{total_versions}] No builds found for Purpur {ver}")
                continue

            latest_build_num = int(latest_build_str)

            # Check if existing build is already up to date and has server metadata
            existing = updated_builds.get(ver)
            if existing and existing.get("build") == latest_build_num and existing.get("md5") and "server" in existing:
                logger.info(f"[{idx}/{total_versions}] Purpur {ver} -> build {latest_build_num} (already cached)")
                continue

            # Fetch build metadata (md5, timestamp, etc.)
            build_url = f"{PURPUR_API_BASE}/purpur/{ver}/{latest_build_num}"
            build_info = fetch_json(build_url, delay=0.05)
            md5 = build_info.get("md5")

            download_url = f"{PURPUR_API_BASE}/purpur/{ver}/{latest_build_num}/download"
            entry = {
                "build": latest_build_num,
                "time": build_info.get("timestamp"),
                "md5": md5,
                "url": download_url,
            }

            if existing and existing.get("build") == latest_build_num and "server" in existing:
                entry["server"] = existing["server"]
            else:
                # Fast path: check Paper builds cache since Purpur tracks Paper's Minecraft versions exactly
                paper_builds = load_json(REPO_ROOT / "paper" / "builds.json") or {}
                if ver in paper_builds and "server" in paper_builds[ver]:
                    entry["server"] = paper_builds[ver]["server"]
                else:
                    server_meta = fetch_server_jar_metadata(download_url)
                    if server_meta:
                        entry["server"] = server_meta

            updated_builds[ver] = entry
            logger.info(f"[{idx}/{total_versions}] Purpur {ver} -> build {latest_build_num} (md5: {md5})")
        except Exception as e:
            logger.error(f"[{idx}/{total_versions}] Error fetching Purpur {ver}: {e}")

    save_json(builds_file, updated_builds)
    logger.info(f"Saved {len(updated_builds)} normalized builds to {builds_file}")
