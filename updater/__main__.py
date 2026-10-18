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


from updater.servers import AVAILABLE_SERVERS, update_server


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m updater",
        description="Minecraft Sources Manager & Updater",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

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
