import json
import logging
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "raw"
META_FILE = REPO_ROOT / "meta.json"

DEFAULT_INDENT = 2
USER_AGENT = "Nixcraft/minecraft-sources (+https://github.com/loystonpais/nixcraft)"

PRISM_META_BASE = "https://meta.prismlauncher.org/v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger("updater")


def get_json_indent() -> int:
    """Reads indent setting from meta.json if present."""
    if META_FILE.exists():
        try:
            with META_FILE.open("r", encoding="utf-8") as f:
                meta = json.load(f)
                return meta.get("json_indent", DEFAULT_INDENT)
        except Exception as e:
            logger.warning(f"Could not read indent from {META_FILE}: {e}")
    return DEFAULT_INDENT


def load_json(path: Path) -> Any:
    """Loads JSON data from a file, returning None if not found."""
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_json(path: Path, data: Any, indent: int | None = None) -> None:
    """Saves data as formatted JSON to the target path."""
    if indent is None:
        indent = get_json_indent()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write("\n")
