from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, logger
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
