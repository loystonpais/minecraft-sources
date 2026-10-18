from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, logger
from updater.fetch import fetch_json


class NeoForgeModloader(BaseModloader):
    """NeoForge raw data updater."""

    @property
    def name(self) -> str:
        return "neoforge"

    def update_raw(self) -> None:
        loader_url = f"{PRISM_META_BASE}/net.neoforged/"

        logger.info(f"Fetching NeoForge raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data.get('versions', []))} NeoForge versions to {self.raw_dir / 'manifest.json'}")
