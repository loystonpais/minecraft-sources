from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, logger
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
