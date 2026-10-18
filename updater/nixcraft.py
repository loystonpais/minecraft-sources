import base64
import shutil
from pathlib import Path
from typing import Any
from updater.config import REPO_ROOT, save_json, load_json, logger

NIXCRAFT_DIR = REPO_ROOT / "nixcraft"
SCHEMA_VERSION = 1

# Modloader & dependency sources that contribute to libraries.json
SOURCE_LOADERS = ["fabric", "quilt", "forge", "neoforge", "liteloader", "lwjgl"]

# Supported server software
SERVER_PROJECTS = ["paper", "folia", "purpur", "velocity", "waterfall"]


def hex_to_sri(hex_digest: str, algo: str = "sha256") -> str:
    """Converts a hex hash digest to W3C SRI format (e.g. sha256-..., sha1-..., md5-...)."""
    cleaned_hex = hex_digest.strip()
    raw_bytes = bytes.fromhex(cleaned_hex)
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"{algo}-{b64}"


def build_meta() -> None:
    """Writes nixcraft/meta.json containing schema version."""
    meta_path = NIXCRAFT_DIR / "meta.json"
    save_json(meta_path, {"version": SCHEMA_VERSION})
    logger.info(f"Saved {meta_path} (schema version {SCHEMA_VERSION})")


def build_libraries() -> None:
    """Merges all loader libraries.json files into nixcraft/libraries.json with SRI hashes."""
    logger.info("==> Building nixcraft/libraries.json from modloader libraries...")
    merged: dict[str, dict[str, Any]] = {}

    for loader_name in SOURCE_LOADERS:
        lib_file = REPO_ROOT / loader_name / "libraries.json"
        if not lib_file.exists():
            continue

        data = load_json(lib_file)
        if not data:
            continue

        for coord, entry in data.items():
            url = entry.get("url")
            if not url:
                continue

            sri_hash = None
            if "hash" in entry:
                sri_hash = entry["hash"]
            elif "sha256" in entry:
                sri_hash = hex_to_sri(entry["sha256"], "sha256")
            elif "sha1" in entry:
                sri_hash = hex_to_sri(entry["sha1"], "sha1")
            elif "md5" in entry:
                sri_hash = hex_to_sri(entry["md5"], "md5")

            if not sri_hash:
                continue

            # Prefer sha256 over sha1/md5 if already present
            if coord in merged:
                existing_hash = merged[coord]["hash"]
                if existing_hash.startswith("sha256-") and not sri_hash.startswith("sha256-"):
                    continue

            merged[coord] = {
                "url": url,
                "hash": sri_hash,
            }

    dest = NIXCRAFT_DIR / "libraries.json"
    save_json(dest, merged)
    logger.info(f"Saved {len(merged)} total merged libraries to {dest}")


def build_mojang() -> None:
    """Consolidates vanilla Minecraft data into nixcraft/mojang.json and copies asset map."""
    logger.info("==> Building nixcraft/mojang.json...")
    versions_data = load_json(REPO_ROOT / "mojang" / "versions.json") or {}
    versions_list = load_json(REPO_ROOT / "mojang" / "versions-list.json") or []
    data_versions = load_json(REPO_ROOT / "mojang" / "data-versions.json") or {}

    mojang_consolidated = {
        "latest": versions_data.get("latest", {}),
        "versions_list": versions_list,
        "versions": versions_data.get("versions", {}),
        "data_versions": data_versions,
    }

    mojang_dest = NIXCRAFT_DIR / "mojang.json"
    save_json(mojang_dest, mojang_consolidated)
    logger.info(f"Saved consolidated vanilla data to {mojang_dest}")

    # Copy asset map using its exact real filename
    asset_src = REPO_ROOT / "mojang" / "asset-sha1-sha256-map.json"
    asset_dest = NIXCRAFT_DIR / "asset-sha1-sha256-map.json"
    if asset_src.exists():
        shutil.copyfile(asset_src, asset_dest)
        logger.info(f"Copied {asset_src.name} to {asset_dest}")


def build_fabric_and_quilt() -> None:
    """Consolidates fabric.json and quilt.json (versions, loaders, mappings)."""
    for loader in ["fabric", "quilt"]:
        logger.info(f"==> Building nixcraft/{loader}.json...")
        versions_list = load_json(REPO_ROOT / loader / "versions-list.json") or []
        loaders_data = load_json(REPO_ROOT / loader / "loaders.json") or {}
        mappings_data = load_json(REPO_ROOT / loader / "mappings.json") or {}

        # Simplify mappings format to map MC version -> list of dependency coordinates
        clean_mappings: dict[str, list[str]] = {}
        for mc_ver, m_info in mappings_data.items():
            if isinstance(m_info, dict) and "dependencies" in m_info:
                clean_mappings[mc_ver] = m_info["dependencies"]
            elif isinstance(m_info, list):
                clean_mappings[mc_ver] = m_info
            else:
                clean_mappings[mc_ver] = []

        consolidated = {
            "versions": versions_list,
            "loaders": loaders_data,
            "mappings": clean_mappings,
        }

        dest = NIXCRAFT_DIR / f"{loader}.json"
        save_json(dest, consolidated)
        logger.info(f"Saved {dest}")


def build_forge_and_neoforge() -> None:
    """Consolidates forge.json and neoforge.json (versions, game_versions, loaders)."""
    for loader in ["forge", "neoforge"]:
        logger.info(f"==> Building nixcraft/{loader}.json...")
        versions_list = load_json(REPO_ROOT / loader / "versions-list.json") or []
        by_game_version = load_json(REPO_ROOT / loader / "versions.json") or {}
        loaders_data = load_json(REPO_ROOT / loader / "loaders.json") or {}

        consolidated = {
            "versions": versions_list,
            "game_versions": by_game_version,
            "loaders": loaders_data,
        }

        dest = NIXCRAFT_DIR / f"{loader}.json"
        save_json(dest, consolidated)
        logger.info(f"Saved {dest}")


def build_lwjgl() -> None:
    """Consolidates lwjgl.json (versions, components)."""
    logger.info("==> Building nixcraft/lwjgl.json...")
    versions_list = load_json(REPO_ROOT / "lwjgl" / "versions-list.json") or []
    components_data = load_json(REPO_ROOT / "lwjgl" / "versions.json") or {}

    consolidated = {
        "versions": versions_list,
        "components": components_data,
    }

    dest = NIXCRAFT_DIR / "lwjgl.json"
    save_json(dest, consolidated)
    logger.info(f"Saved {dest}")


def build_servers() -> None:
    """Normalizes and exports server software builds with SRI hashes."""
    for s_name in SERVER_PROJECTS:
        src = REPO_ROOT / s_name / "builds.json"
        if not src.exists():
            continue

        raw_builds = load_json(src) or {}
        sri_builds: dict[str, dict[str, Any]] = {}

        for ver, info in raw_builds.items():
            entry = dict(info)
            if "hash" not in entry:
                if "sha256" in entry:
                    entry["hash"] = hex_to_sri(entry.pop("sha256"), "sha256")
                elif "md5" in entry:
                    entry["hash"] = hex_to_sri(entry.pop("md5"), "md5")
                elif "sha1" in entry:
                    entry["hash"] = hex_to_sri(entry.pop("sha1"), "sha1")
            sri_builds[ver] = entry

        dest = NIXCRAFT_DIR / f"{s_name}.json"
        save_json(dest, sri_builds)
        logger.info(f"Saved {dest} ({len(sri_builds)} versions)")


def build_all_nixcraft() -> None:
    """Builds the entire flat nixcraft/ directory."""
    NIXCRAFT_DIR.mkdir(parents=True, exist_ok=True)
    build_meta()
    build_libraries()
    build_mojang()
    build_fabric_and_quilt()
    build_forge_and_neoforge()
    build_lwjgl()
    build_servers()
    logger.info("==> Successfully updated all nixcraft/ sources.")
