import argparse
import sys
from pathlib import Path
from updater.config import logger
from updater.modloaders import MODLOADERS
from updater.mojang import (
    update_manifest,
    update_data_versions,
    update_from_local_directory,
    update_from_remote,
    update_mojang_libraries,
)



def update_modloader_command(args: argparse.Namespace) -> int:
    target = args.loader.lower()

    if target == "all":
        targets = list(MODLOADERS.keys())
    elif target in MODLOADERS:
        targets = [target]
    else:
        logger.error(f"Unknown modloader '{target}'. Available: {', '.join(MODLOADERS.keys())}, all")
        return 1

    for name in targets:
        loader_cls = MODLOADERS[name]
        loader = loader_cls()
        logger.info(f"==> Updating data for {name}...")
        try:
            loader.update_raw()
            loader.normalize()
        except Exception as e:
            logger.error(f"Failed to update {name}: {e}")
            return 1

    logger.info("Done.")
    return 0



def mojang_manifest_command(args: argparse.Namespace) -> int:
    try:
        update_manifest()
        return 0
    except Exception as e:
        logger.error(f"Failed to update Mojang manifest: {e}")
        return 1


def mojang_data_versions_command(args: argparse.Namespace) -> int:
    try:
        return update_data_versions(target_version_ids=args.versions or None)
    except Exception as e:
        logger.error(f"Failed to update data versions: {e}")
        return 1


def mojang_assets_command(args: argparse.Namespace) -> int:
    try:
        if args.path:
            return update_from_local_directory(Path(args.path))
        else:
            return update_from_remote(limit_versions=args.limit)
    except Exception as e:
        logger.error(f"Failed to update asset sha256 hashes: {e}")
        return 1


def mojang_libraries_command(args: argparse.Namespace) -> int:
    try:
        return update_mojang_libraries(full=args.full, limit_versions=args.limit)
    except Exception as e:
        logger.error(f"Failed to update Mojang libraries: {e}")
        return 1




from updater.servers import AVAILABLE_SERVERS, update_server
from updater.nixcraft import build_libraries
from updater.lwjgl import update_lwjgl


def update_server_command(args: argparse.Namespace) -> int:
    target = args.server.lower()
    targets = [s for s in AVAILABLE_SERVERS if s != "purpur"] if target == "all-papermc" else (
        AVAILABLE_SERVERS if target == "all" else [target]
    )

    for s in targets:
        try:
            update_server(s)
        except Exception as e:
            logger.error(f"Failed to update server '{s}': {e}")
            return 1
    return 0


from updater.nixcraft import build_all_nixcraft
from updater.verify import verify_all_nixcraft


def nixcraft_command(args: argparse.Namespace) -> int:
    try:
        build_all_nixcraft()
        if not args.no_verify:
            if not verify_all_nixcraft():
                return 1
        return 0
    except Exception as e:
        logger.error(f"Failed to build nixcraft sources: {e}")
        return 1


def verify_command(args: argparse.Namespace) -> int:
    try:
        success = verify_all_nixcraft()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Verification encountered an error: {e}")
        return 1


from updater.waywall import update_waywall


def waywall_command(args: argparse.Namespace) -> int:
    try:
        update_waywall()
        return 0
    except Exception as e:
        logger.error(f"Failed to update Waywall sources: {e}")
        return 1


def lwjgl_command(args: argparse.Namespace) -> int:
    try:
        update_lwjgl()
        return 0
    except Exception as e:
        logger.error(f"Failed to update LWJGL sources: {e}")
        return 1


def update_all_command(args: argparse.Namespace) -> int:
    """Executes full update pipeline across all sources followed by nixcraft compilation and verification."""
    logger.info("==================================================")
    logger.info("   Starting Full Minecraft Sources Update Pipeline")
    logger.info("==================================================")

    # 1. Mojang Manifest & Data Versions & Libraries
    logger.info("\n==> [1/7] Updating Mojang Manifest, Data Versions & Libraries...")
    try:
        changed_versions = update_manifest()
        update_data_versions()
        update_mojang_libraries(target_versions=changed_versions)
    except Exception as e:
        logger.error(f"Failed during Mojang update: {e}")
        return 1



    # 2. Modloaders (Fabric, Quilt, Forge, NeoForge, LiteLoader)
    logger.info("\n==> [2/7] Updating Modloaders...")
    for name, loader_cls in MODLOADERS.items():
        logger.info(f"--> Updating {name}...")
        try:
            loader = loader_cls()
            loader.update_raw()
            loader.normalize()
        except Exception as e:
            logger.error(f"Failed updating modloader {name}: {e}")
            return 1

    # 3. Server Software (Paper, Folia, Purpur, Velocity, Waterfall)
    logger.info("\n==> [3/7] Updating Server Software...")
    for s_name in AVAILABLE_SERVERS:
        logger.info(f"--> Updating server {s_name}...")
        try:
            update_server(s_name)
        except Exception as e:
            logger.error(f"Failed updating server {s_name}: {e}")
            return 1

    # 4. LWJGL 2 & 3
    logger.info("\n==> [4/7] Updating LWJGL...")
    try:
        update_lwjgl()
    except Exception as e:
        logger.error(f"Failed updating LWJGL: {e}")
        return 1

    # 5. Waywall
    logger.info("\n==> [5/7] Updating Waywall...")
    try:
        update_waywall()
    except Exception as e:
        logger.error(f"Failed updating Waywall: {e}")
        return 1

    # 6. Nixcraft Compilation
    logger.info("\n==> [6/7] Building nixcraft/ Directory...")
    try:
        build_all_nixcraft()
    except Exception as e:
        logger.error(f"Failed compiling nixcraft: {e}")
        return 1

    # 7. Verification
    logger.info("\n==> [7/7] Validating nixcraft/ Schemas...")
    if not args.no_verify:
        if not verify_all_nixcraft():
            logger.error("Schema validation failed!")
            return 1

    logger.info("\n==================================================")
    logger.info("   Full Pipeline Completed Successfully!")
    logger.info("==================================================")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m updater",
        description="Minecraft Sources Manager & Updater",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # all subcommand
    all_parser = subparsers.add_parser("all", help="Update all sources, build nixcraft/, and verify schemas")
    all_parser.add_argument("--no-verify", action="store_true", help="Skip schema verification after build")
    all_parser.set_defaults(func=update_all_command)

    # verify subcommand
    verify_parser = subparsers.add_parser("verify", help="Exhaustively validate schema and attributes of nixcraft/ files")
    verify_parser.set_defaults(func=verify_command)

    # waywall subcommand
    waywall_parser = subparsers.add_parser("waywall", help="Update Waywall releases and patch sources")
    waywall_parser.set_defaults(func=waywall_command)

    # lwjgl subcommand
    lwjgl_parser = subparsers.add_parser("lwjgl", help="Update LWJGL 2 and 3 sources")
    lwjgl_parser.set_defaults(func=lwjgl_command)

    # nixcraft subcommand
    nixcraft_parser = subparsers.add_parser("nixcraft", help="Build/update nixcraft/ domain files (merged libraries, etc.)")
    nixcraft_parser.add_argument("--no-verify", action="store_true", help="Skip schema verification after build")
    nixcraft_parser.set_defaults(func=nixcraft_command)

    # server subcommand
    server_parser = subparsers.add_parser("server", help="Update server software sources (Paper, Folia, etc.)")
    server_parser.add_argument(
        "server",
        choices=AVAILABLE_SERVERS + ["all", "all-papermc"],
        help="Server project name, 'all-papermc', or 'all'",
    )


    server_parser.set_defaults(func=update_server_command)

    # modloader subcommand
    modloader_parser = subparsers.add_parser("modloader", help="Update modloader sources")
    modloader_parser.add_argument(
        "loader",
        choices=list(MODLOADERS.keys()) + ["all"],
        help="Modloader name or 'all'",
    )
    modloader_parser.set_defaults(func=update_modloader_command)

    # mojang subcommand
    mojang_parser = subparsers.add_parser("mojang", help="Mojang sources and metadata")
    mojang_subparsers = mojang_parser.add_subparsers(dest="mojang_action", help="Mojang action to perform")

    # mojang manifest
    m_manifest = mojang_subparsers.add_parser("manifest", help="Update raw/mojang/version_manifest_v2.json")
    m_manifest.set_defaults(func=mojang_manifest_command)

    # mojang data-versions
    m_data = mojang_subparsers.add_parser("data-versions", help="Update minecraft-data-versions.json")
    m_data.add_argument("versions", nargs="*", help="Optional specific version IDs to update")
    m_data.set_defaults(func=mojang_data_versions_command)

    # mojang assets
    m_assets = mojang_subparsers.add_parser("assets", help="Update mojang/asset-sha1-sha256-map.json")
    m_assets.add_argument("--path", "-p", help="Local assets/objects directory (e.g. from Prism Launcher)")
    m_assets.add_argument(
        "--limit",
        "-l",
        type=int,
        default=50,
        help="Limit number of manifest versions to scan remotely (default: 50, pass 0 for all)",
    )
    m_assets.set_defaults(func=mojang_assets_command)

    # mojang libraries
    m_libs = mojang_subparsers.add_parser("libraries", help="Update mojang/libraries.json from version packages")
    m_libs.add_argument(
        "--full",
        action="store_true",
        help="Perform full scan of all versions in manifest instead of incremental diff",
    )
    m_libs.add_argument(
        "--limit",
        "-l",
        type=int,
        default=0,
        help="Limit number of manifest versions to scan remotely (default: 0 for all)",
    )
    m_libs.set_defaults(func=mojang_libraries_command)


    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
