import hashlib
import subprocess
from pathlib import Path
from typing import Any
from updater.config import REPO_ROOT, RAW_DIR, save_json, load_json, logger
from updater.fetch import fetch_json, fetch_bytes

WAYWALL_RAW_DIR = RAW_DIR / "waywall"
WAYWALL_DOMAIN_DIR = REPO_ROOT / "waywall"
WAYWALL_RELEASES_URL = "https://api.github.com/repos/tesselslate/waywall/releases"


def get_unpack_sha256_hex(url: str) -> str:
    """Computes the sha256 hex digest for an unpacked tarball directory (fetchzip / fetchFromGitHub)."""
    res = subprocess.run(
        ["nix-prefetch-url", "--unpack", url],
        capture_output=True,
        text=True,
        check=True,
    )
    b32 = res.stdout.strip()
    hex_cmd = subprocess.run(
        ["nix-hash", "--type", "sha256", "--to-base16", b32],
        capture_output=True,
        text=True,
        check=True,
    )
    return hex_cmd.stdout.strip()


def get_patch_sha256_hex(url: str) -> str | None:
    """Fetches patch bytes and computes sha256 hex digest."""
    try:
        data = fetch_bytes(url, delay=0.02, max_retries=2)
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return None


def update_waywall() -> None:
    """Updates raw Waywall releases and generates waywall/ domain files with hex hashes."""
    logger.info("==> Updating Waywall sources from GitHub...")
    WAYWALL_RAW_DIR.mkdir(parents=True, exist_ok=True)
    WAYWALL_DOMAIN_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch raw releases
    logger.info(f"Fetching Waywall releases from {WAYWALL_RELEASES_URL}...")
    releases_data = fetch_json(WAYWALL_RELEASES_URL)
    save_json(WAYWALL_RAW_DIR / "releases.json", releases_data)

    existing_releases_file = WAYWALL_DOMAIN_DIR / "releases.json"
    existing_releases = load_json(existing_releases_file) or {}

    versions_list: list[str] = []
    releases_map: dict[str, dict[str, Any]] = dict(existing_releases)

    for r in releases_data:
        tag = r.get("tag_name")
        if not tag:
            continue

        versions_list.append(tag)

        # Check if already cached
        if tag in releases_map and "src" in releases_map[tag]:
            continue

        logger.info(f"  Processing Waywall release {tag}...")
        tar_url = f"https://github.com/tesselslate/waywall/archive/refs/tags/{tag}.tar.gz"
        try:
            tar_hex = get_unpack_sha256_hex(tar_url)
        except Exception as e:
            logger.warning(f"Could not compute unpack hash for {tag}: {e}")
            continue

        patch_url = f"https://raw.githubusercontent.com/tesselslate/waywall/{tag}/contrib/glfw.patch"
        patch_hex = get_patch_sha256_hex(patch_url)

        entry = {
            "tag": tag,
            "src": {
                "url": tar_url,
                "sha256": tar_hex,
            },
        }

        if patch_hex:
            entry["patches"] = {
                "glfw": {
                    "url": patch_url,
                    "sha256": patch_hex,
                }
            }

        releases_map[tag] = entry

    # Save domain files
    versions_list_file = WAYWALL_DOMAIN_DIR / "versions-list.json"
    save_json(versions_list_file, versions_list)
    logger.info(f"Saved {len(versions_list)} Waywall versions to {versions_list_file}")

    save_json(existing_releases_file, releases_map)
    logger.info(f"Saved {len(releases_map)} Waywall releases to {existing_releases_file}")
