from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json


class QuiltModloader(BaseModloader):
    """Quilt modloader raw data updater."""

    QUILT_META_BASE = "https://meta.quiltmc.org/v3/versions"

    @property
    def name(self) -> str:
        return "quilt"

    def update_raw(self) -> None:
        loader_url = f"{PRISM_META_BASE}/org.quiltmc.quilt-loader/"
        hashed_url = f"{self.QUILT_META_BASE}/hashed"
        intermediary_url = f"{self.QUILT_META_BASE}/intermediary"

        logger.info(f"Fetching Quilt Loader raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data.get('versions', []))} Quilt versions to {self.raw_dir / 'manifest.json'}")

        logger.info(f"Fetching Quilt hashed mappings from {hashed_url}...")
        hashed_data = fetch_json(hashed_url)
        save_json(self.raw_dir / "hashed.json", hashed_data)
        logger.info(f"Saved {len(hashed_data)} Quilt hashed versions to {self.raw_dir / 'hashed.json'}")

        logger.info(f"Fetching Quilt intermediary mappings from {intermediary_url}...")
        intermediary_data = fetch_json(intermediary_url)
        save_json(self.raw_dir / "intermediary.json", intermediary_data)
        logger.info(f"Saved {len(intermediary_data)} Quilt intermediary versions to {self.raw_dir / 'intermediary.json'}")

    def normalize(self) -> None:
        """Generates quilt/game-lock.json and quilt/versions-list.json."""
        # 1. versions-list.json
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if manifest_data:
            versions = [v["version"] for v in manifest_data.get("versions", [])]
            save_json(self.output_dir / "versions-list.json", versions)
            logger.info(f"Saved {len(versions)} Quilt loader versions to {self.output_dir / 'versions-list.json'}")

        # 2. game-lock.json (mapping MC version -> intermediary & hashed dependencies)
        hashed_file = self.raw_dir / "hashed.json"
        hashed_data = load_json(hashed_file) or []

        intermediary_file = self.raw_dir / "intermediary.json"
        intermediary_data = load_json(intermediary_file) or []

        game_lock: dict[str, dict[str, list[str]]] = {}

        # Intermediary mappings
        for item in intermediary_data:
            mc_ver = item.get("version")
            maven = item.get("maven")
            if mc_ver and maven:
                if mc_ver not in game_lock:
                    game_lock[mc_ver] = {"dependencies": []}
                if maven not in game_lock[mc_ver]["dependencies"]:
                    game_lock[mc_ver]["dependencies"].append(maven)

        # Hashed mappings
        for item in hashed_data:
            mc_ver = item.get("version")
            maven = item.get("maven")
            if mc_ver and maven:
                if mc_ver not in game_lock:
                    game_lock[mc_ver] = {"dependencies": []}
                if maven not in game_lock[mc_ver]["dependencies"]:
                    game_lock[mc_ver]["dependencies"].append(maven)

        save_json(self.output_dir / "game-lock.json", game_lock)
        logger.info(f"Saved {len(game_lock)} versions to {self.output_dir / 'game-lock.json'}")

