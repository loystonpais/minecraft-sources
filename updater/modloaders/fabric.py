from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json


class FabricModloader(BaseModloader):
    """Fabric modloader raw data updater."""

    @property
    def name(self) -> str:
        return "fabric"

    def update_raw(self) -> None:
        loader_url = f"{PRISM_META_BASE}/net.fabricmc.fabric-loader/"
        intermediary_url = f"{PRISM_META_BASE}/net.fabricmc.intermediary/"

        logger.info(f"Fetching Fabric Loader raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data.get('versions', []))} Fabric versions to {self.raw_dir / 'manifest.json'}")

        logger.info(f"Fetching Fabric Intermediary raw manifest from {intermediary_url}...")
        intermediary_data = fetch_json(intermediary_url)
        save_json(self.raw_dir / "intermediary.json", intermediary_data)
        logger.info(f"Saved {len(intermediary_data.get('versions', []))} Intermediary versions to {self.raw_dir / 'intermediary.json'}")

    def normalize(self) -> None:
        """Generates fabric/game-lock.json and fabric/versions-list.json."""
        # 1. versions-list.json
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if manifest_data:
            versions = [v["version"] for v in manifest_data.get("versions", [])]
            save_json(self.output_dir / "versions-list.json", versions)
            logger.info(f"Saved {len(versions)} Fabric loader versions to {self.output_dir / 'versions-list.json'}")

        # 2. game-lock.json (mapping MC version -> intermediary dependency)
        intermediary_file = self.raw_dir / "intermediary.json"
        intermediary_data = load_json(intermediary_file)
        if intermediary_data:
            game_lock = {}
            for item in intermediary_data.get("versions", []):
                mc_ver = item.get("version")
                if not mc_ver:
                    continue
                # In Fabric, intermediary maven coordinate is net.fabricmc:intermediary:<version>
                game_lock[mc_ver] = {
                    "dependencies": [f"net.fabricmc:intermediary:{mc_ver}"]
                }
            save_json(self.output_dir / "game-lock.json", game_lock)
            logger.info(f"Saved {len(game_lock)} versions to {self.output_dir / 'game-lock.json'}")

