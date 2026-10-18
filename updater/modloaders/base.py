from abc import ABC, abstractmethod
from pathlib import Path
from updater.config import RAW_DIR


class BaseModloader(ABC):
    """Base class for all modloader updaters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name / identifier of the modloader (e.g. 'fabric', 'forge')."""
        pass

    @property
    def raw_dir(self) -> Path:
        """Target raw directory for this modloader."""
        return RAW_DIR / self.name

    @abstractmethod
    def update_raw(self) -> None:
        """Fetch upstream raw data and save to raw_dir."""
        pass
