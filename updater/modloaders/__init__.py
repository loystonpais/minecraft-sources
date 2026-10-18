from typing import Dict, Type
from updater.modloaders.base import BaseModloader
from updater.modloaders.fabric import FabricModloader
from updater.modloaders.quilt import QuiltModloader
from updater.modloaders.forge import ForgeModloader
from updater.modloaders.neoforge import NeoForgeModloader
from updater.modloaders.liteloader import LiteLoaderModloader

MODLOADERS: Dict[str, Type[BaseModloader]] = {
    "fabric": FabricModloader,
    "quilt": QuiltModloader,
    "forge": ForgeModloader,
    "neoforge": NeoForgeModloader,
    "liteloader": LiteLoaderModloader,
}

__all__ = [
    "BaseModloader",
    "FabricModloader",
    "QuiltModloader",
    "ForgeModloader",
    "NeoForgeModloader",
    "LiteLoaderModloader",
    "MODLOADERS",
]
