from dataclasses import dataclass
from typing import Any
from updater.fetch import fetch_bytes, fetch_json, fetch_stream_sha256, logger


@dataclass(frozen=True)
class MavenCoord:
    group: str
    artifact: str
    version: str

    @classmethod
    def parse(cls, coord: str) -> "MavenCoord":
        parts = coord.split(":")
        if len(parts) < 3:
            raise ValueError(f"Invalid maven coordinate: {coord}")
        return cls(group=parts[0], artifact=parts[1], version=parts[2])

    @property
    def path(self) -> str:
        return self.group.replace(".", "/")

    def jar_url(self, base_url: str) -> str:
        import urllib.parse
        base = base_url.rstrip("/")
        art = urllib.parse.quote(self.artifact, safe="+")
        ver = urllib.parse.quote(self.version, safe="+")
        return f"{base}/{self.path}/{art}/{ver}/{art}-{ver}.jar"

    def sha256_url(self, base_url: str) -> str:
        return f"{self.jar_url(base_url)}.sha256"

    def sha1_url(self, base_url: str) -> str:
        return f"{self.jar_url(base_url)}.sha1"

    def md5_url(self, base_url: str) -> str:
        return f"{self.jar_url(base_url)}.md5"

    def json_url(self, base_url: str) -> str:
        import urllib.parse
        base = base_url.rstrip("/")
        art = urllib.parse.quote(self.artifact, safe="+")
        ver = urllib.parse.quote(self.version, safe="+")
        return f"{base}/{self.path}/{art}/{ver}/{art}-{ver}.json"




def get_maven_hash(
    coord_str: str,
    base_url: str,
    existing_cache: dict[str, dict] | None = None
) -> tuple[str, str] | None:
    """Gets available hash (sha256, sha1, or md5) from maven repository metadata without downloading the full jar."""
    if existing_cache and coord_str in existing_cache:
        entry = existing_cache[coord_str]
        for h_type in ("sha256", "sha1", "md5"):
            if h_type in entry:
                return (h_type, entry[h_type])

    try:
        coord = MavenCoord.parse(coord_str)
    except Exception as e:
        logger.warning(f"Could not parse maven coordinate '{coord_str}': {e}")
        return None

    # Check sha256, sha1, md5 in order
    candidates = [
        ("sha256", coord.sha256_url(base_url), 64),
        ("sha1", coord.sha1_url(base_url), 40),
        ("md5", coord.md5_url(base_url), 32),
    ]

    for h_type, endpoint, expected_len in candidates:
        try:
            data = fetch_bytes(endpoint, delay=0.02, max_retries=2)
            text = data.decode("utf-8").strip()
            parts = text.split()
            if parts and len(parts[0]) == expected_len:
                return (h_type, parts[0].lower())
        except Exception:
            continue

    return None

