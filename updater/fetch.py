import hashlib
import time
import urllib.request
import json
from typing import Any
from updater.config import USER_AGENT, logger


def fetch_bytes(url: str, delay: float = 0.05, max_retries: int = 3) -> bytes:
    """Fetch raw bytes from a URL with retries and delay."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            if delay > 0:
                time.sleep(delay)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            logger.warning(f"Fetch attempt {attempt}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 0.5)

    if last_err:
        raise last_err
    raise RuntimeError(f"Failed to fetch {url}")


def fetch_json(url: str, delay: float = 0.05, max_retries: int = 3) -> Any:
    """Fetch and decode JSON from a URL."""
    content = fetch_bytes(url, delay=delay, max_retries=max_retries)
    return json.loads(content.decode("utf-8"))


def fetch_stream_sha256(url: str, chunk_size: int = 65536, max_retries: int = 3) -> str:
    """Streams a file from URL and computes its SHA256 hex digest without loading the whole file into RAM."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            h = hashlib.sha256()
            with urllib.request.urlopen(req, timeout=60) as resp:
                while chunk := resp.read(chunk_size):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            last_err = e
            logger.warning(f"Stream sha256 attempt {attempt}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 0.5)

    if last_err:
        raise last_err
    raise RuntimeError(f"Failed to compute SHA256 for {url}")


def fetch_server_jar_metadata(jar_url: str, max_retries: int = 3) -> dict[str, str] | None:
    """Extracts vanilla Mojang server JAR metadata (filename, sha256, url) from a Paperclip/Purpur server JAR.

    Uses HTTP Range requests to inspect the ZIP central directory at the tail of the JAR (~64-128 KB)
    without downloading the entire 40-50MB JAR archive.
    Supports modern Paperclip (META-INF/download-context) and legacy Paperclip (patch.properties).
    """
    import io
    import zipfile

    req = urllib.request.Request(jar_url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                cr = resp.headers.get("Content-Range", "")
                size = int(cr.split("/")[-1]) if cr else int(resp.headers.get("Content-Length", 0))
                final_url = resp.geturl()

            if not size:
                return None

            read_size = min(size, 131072)
            tail_req = urllib.request.Request(
                final_url,
                headers={"User-Agent": USER_AGENT, "Range": f"bytes={size - read_size}-{size - 1}"},
            )
            with urllib.request.urlopen(tail_req, timeout=20) as resp:
                tail = resp.read()

            class TailZip(io.RawIOBase):
                def __init__(self, tail_buf: bytes, total_sz: int, target_url: str):
                    self.tail = tail_buf
                    self.total_size = total_sz
                    self.tail_offset = total_sz - len(tail_buf)
                    self.pos = 0
                    self.url = target_url
                    self.cache: dict[tuple[int, int], bytes] = {}

                def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
                    if whence == io.SEEK_SET:
                        self.pos = offset
                    elif whence == io.SEEK_CUR:
                        self.pos += offset
                    elif whence == io.SEEK_END:
                        self.pos = self.total_size + offset
                    return self.pos

                def tell(self) -> int:
                    return self.pos

                def read(self, n: int = -1) -> bytes:
                    if self.pos < self.tail_offset:
                        for (c_start, c_end), c_data in self.cache.items():
                            if c_start <= self.pos < c_end:
                                offset = self.pos - c_start
                                chunk = c_data[offset : offset + n] if n > 0 else c_data[offset:]
                                self.pos += len(chunk)
                                return chunk

                        fetch_n = max(n if n > 0 else 65536, 65536)
                        end = min(self.pos + fetch_n - 1, self.total_size - 1)
                        r = urllib.request.Request(
                            self.url,
                            headers={"User-Agent": USER_AGENT, "Range": f"bytes={self.pos}-{end}"},
                        )
                        with urllib.request.urlopen(r, timeout=20) as rp:
                            data = rp.read()
                        self.cache[(self.pos, self.pos + len(data))] = data
                        chunk = data[:n] if n > 0 else data
                        self.pos += len(chunk)
                        return chunk
                    rel = self.pos - self.tail_offset
                    chunk = self.tail[rel : rel + n] if n >= 0 else self.tail[rel:]
                    self.pos += len(chunk)
                    return chunk

            tz = TailZip(tail, size, final_url)
            with zipfile.ZipFile(tz) as zf:
                namelist = zf.namelist()
                # 1. Modern Paperclip
                if "META-INF/download-context" in namelist:
                    raw = zf.read("META-INF/download-context").decode("utf-8", errors="replace")
                    for line in raw.strip().splitlines():
                        parts = line.strip().split("\t")
                        if len(parts) >= 3:
                            sha256 = parts[0].strip().lower()
                            url = parts[1].strip()
                            filename = parts[2].strip()
                            return {"filename": filename, "sha256": sha256, "url": url}

                # 2. Intermediate Paperclip (patch.json)
                if "patch.json" in namelist:
                    import json

                    raw = zf.read("patch.json").decode("utf-8", errors="replace")
                    pj = json.loads(raw)
                    url = pj.get("sourceUrl")
                    sha256 = pj.get("originalHash")
                    ver = pj.get("version", "")
                    filename = f"mojang_{ver}.jar" if ver else "server.jar"
                    if url and sha256:
                        return {"filename": filename, "sha256": sha256.lower(), "url": url}

                # 3. Legacy Paperclip (patch.properties)
                if "patch.properties" in namelist:
                    raw = zf.read("patch.properties").decode("utf-8", errors="replace")
                    props: dict[str, str] = {}
                    for line in raw.splitlines():
                        if "=" in line and not line.strip().startswith("#"):
                            k, v = line.split("=", 1)
                            props[k.strip()] = v.strip().replace(r"\:", ":")
                    url = props.get("sourceUrl")
                    sha256 = props.get("originalHash")
                    ver = props.get("version", "")
                    filename = f"mojang_{ver}.jar" if ver else "server.jar"
                    if url and sha256:
                        return {"filename": filename, "sha256": sha256.lower(), "url": url}

            return None
        except Exception as e:
            last_err = e
            logger.warning(f"fetch_server_jar_metadata attempt {attempt}/{max_retries} failed for {jar_url}: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 0.5)

    if last_err:
        logger.error(f"Error extracting server metadata from {jar_url}: {last_err}")
    return None
