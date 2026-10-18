from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json


class LiteLoaderModloader(BaseModloader):
    """LiteLoader raw data updater."""

    @property
    def name(self) -> str:
        return "liteloader"

    def update_raw(self) -> None:
        loader_url = f"{PRISM_META_BASE}/com.mumfrey.liteloader/"

        logger.info(f"Fetching LiteLoader raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data.get('versions', []))} LiteLoader versions to {self.raw_dir / 'manifest.json'}")

    def normalize(self) -> None:
        """Generates liteloader/versions.json and liteloader/versions-list.json."""
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if not manifest_data:
            return

        raw_versions = manifest_data.get("versions", [])
        versions_list = [v["version"] for v in raw_versions]
        save_json(self.output_dir / "versions-list.json", versions_list)
        logger.info(f"Saved {len(versions_list)} LiteLoader versions to {self.output_dir / 'versions-list.json'}")

        # Index by Minecraft version -> list of compatible liteloader builds
        by_game_version: dict[str, list[dict]] = {}
        for v in raw_versions:
            liteloader_ver = v.get("version")
            requires = v.get("requires", [])
            mc_ver = None
            for req in requires:
                if req.get("uid") == "net.minecraft":
                    mc_ver = req.get("equals")
                    break

            if not mc_ver:
                continue

            if mc_ver not in by_game_version:
                by_game_version[mc_ver] = []

            by_game_version[mc_ver].append({
                "version": liteloader_ver,
                "releaseTime": v.get("releaseTime"),
                "recommended": v.get("recommended", False),
                "sha256": v.get("sha256"),
            })

        save_json(self.output_dir / "versions.json", by_game_version)
        logger.info(f"Saved LiteLoader versions for {len(by_game_version)} MC versions to {self.output_dir / 'versions.json'}")

