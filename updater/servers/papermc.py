from updater.config import REPO_ROOT, RAW_DIR, save_json, load_json, logger
from updater.fetch import fetch_json

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
            builds_url = f"{PAPERMC_API_BASE}/projects/{project_id}/versions/{ver}/builds"
            builds_data = fetch_json(builds_url, delay=0.05)
            if not builds_data:
                logger.warning(f"[{idx}/{total_versions}] No builds found for {project_id} {ver}")
                continue

            # Upstream builds list has highest build id first, or we can sort by id
            latest_build = max(builds_data, key=lambda b: b["id"])
            build_id = latest_build["id"]

            downloads = latest_build.get("downloads", {})
            server_dl = downloads.get("server:default", {})
            checksums = server_dl.get("checksums", {})
            sha256 = checksums.get("sha256")
            url = server_dl.get("url")

            if not url or not sha256:
                logger.warning(f"[{idx}/{total_versions}] Incomplete download info for {project_id} {ver} build {build_id}")
                continue

            updated_builds[ver] = {
                "build": build_id,
                "time": latest_build.get("time"),
                "channel": latest_build.get("channel"),
                "url": url,
                "sha256": sha256,
            }
            logger.info(f"[{idx}/{total_versions}] {project_id} {ver} -> build {build_id}")
        except Exception as e:
            logger.error(f"[{idx}/{total_versions}] Error fetching builds for {project_id} {ver}: {e}")

    save_json(builds_file, updated_builds)
    logger.info(f"Saved {len(updated_builds)} normalized builds to {builds_file}")
