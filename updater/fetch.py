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
            logger.warning(f"Stream hash attempt {attempt}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 1.0)

    if last_err:
        raise last_err
    raise RuntimeError(f"Failed to stream and hash {url}")
