from updater.config import REPO_ROOT, RAW_DIR, save_json, load_json, logger
from updater.fetch import fetch_json, fetch_server_jar_metadata

PAPERMC_API_BASE = "https://fill.papermc.io/v3"

# PaperMC projects and whether they target Minecraft versions
PAPERMC_PROJECTS = {
    "paper": "Paper",
    "folia": "Folia",
    "velocity": "Velocity",
    "waterfall": "Waterfall",
}


def update_papermc_project(project_id: str) -> None:
    """Updates raw project metadata and normalized builds for a PaperMC project."""
    if project_id not in PAPERMC_PROJECTS:
        raise ValueError(f"Unknown PaperMC project '{project_id}'. Available: {list(PAPERMC_PROJECTS.keys())}")

    project_name = PAPERMC_PROJECTS[project_id]
    logger.info(f"==> Updating PaperMC project '{project_id}' ({project_name})...")

    # 1. Fetch raw project manifest
    project_url = f"{PAPERMC_API_BASE}/projects/{project_id}"
    raw_project = fetch_json(project_url)

    raw_file = RAW_DIR / project_id / "project.json"
    save_json(raw_file, raw_project)
    logger.info(f"Saved raw project to {raw_file}")

    # 2. Extract ordered version list (preserving upstream grouping order)
    # The 'versions' field is a mapping of version group -> list of versions
    raw_version_groups = raw_project.get("versions", {})
    all_versions: list[str] = []
    for group, v_list in raw_version_groups.items():
        all_versions.extend(v_list)

    versions_list_file = REPO_ROOT / project_id / "versions-list.json"
    save_json(versions_list_file, all_versions)
    logger.info(f"Saved {len(all_versions)} versions to {versions_list_file}")

    # 3. Load existing normalized builds so we can incrementally cache/skip builds that are already finalized
    builds_file = REPO_ROOT / project_id / "builds.json"
    existing_builds: dict[str, dict] = load_json(builds_file) or {}
    updated_builds: dict[str, dict] = dict(existing_builds)

    # 4. Fetch latest build for each version
    total_versions = len(all_versions)
    for idx, ver in enumerate(all_versions, 1):
        try:
            cached = existing_builds.get(ver)
            # Lightweight check: get version metadata (contains build numbers and support status)
            ver_url = f"{PAPERMC_API_BASE}/projects/{project_id}/versions/{ver}"
            ver_data = fetch_json(ver_url, delay=0.03)
            build_nums = ver_data.get("builds", [])
            if not build_nums:
                logger.warning(f"[{idx}/{total_versions}] No builds found for {project_id} {ver}")
                continue

            latest_build_id = build_nums[0] if isinstance(build_nums[0], int) else max(build_nums)

            # If this build is already cached with server metadata (if applicable), skip network requests!
            needs_server = project_id in ("paper", "folia")
            if (
                cached
                and cached.get("build") == latest_build_id
                and cached.get("sha256")
                and (not needs_server or "server" in cached)
            ):
                updated_builds[ver] = cached
                logger.info(f"[{idx}/{total_versions}] {project_id} {ver} -> build {latest_build_id} (already cached)")
                continue

            # Only fetch detailed build payload if build changed or is new
            build_detail_url = f"{PAPERMC_API_BASE}/projects/{project_id}/versions/{ver}/builds/{latest_build_id}"
            latest_build = fetch_json(build_detail_url, delay=0.05)
            build_id = latest_build["id"]

            downloads = latest_build.get("downloads", {})
            server_dl = downloads.get("server:default", {})
            checksums = server_dl.get("checksums", {})
            sha256 = checksums.get("sha256")
            url = server_dl.get("url")

            if not url or not sha256:
                logger.warning(f"[{idx}/{total_versions}] Incomplete download info for {project_id} {ver} build {build_id}")
                continue

            entry = {
                "build": build_id,
                "time": latest_build.get("time"),
                "channel": latest_build.get("channel"),
                "url": url,
                "sha256": sha256,
            }

            if cached and cached.get("build") == build_id and "server" in cached:
                entry["server"] = cached["server"]
            elif needs_server:
                server_meta = fetch_server_jar_metadata(url)
                if server_meta:
                    entry["server"] = server_meta

            updated_builds[ver] = entry
            logger.info(f"[{idx}/{total_versions}] {project_id} {ver} -> build {build_id}")
        except Exception as e:
            logger.error(f"[{idx}/{total_versions}] Error fetching builds for {project_id} {ver}: {e}")

    save_json(builds_file, updated_builds)
    logger.info(f"Saved {len(updated_builds)} normalized builds to {builds_file}")
