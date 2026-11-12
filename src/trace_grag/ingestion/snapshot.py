"""
Disk-safe repository snapshots.

Fetches a repo at a pinned commit as a GitHub tarball (smaller than a full git
clone with history), extracts it into a fresh directory, and supports deletion
after the graph is built — the key to staying within a tight disk budget.

Snapshots are treated as untrusted data: we only *parse* them with `ast`
(never import or execute them) during the localization tier. Extraction guards
against path traversal.
"""

from __future__ import annotations

import io
import logging
import shutil
import tarfile
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

CODELOAD = "https://codeload.github.com/{repo}/tar.gz/{commit}"


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> Path:
    dest = dest.resolve()
    members = tar.getmembers()
    top = members[0].name.split("/")[0] if members else ""
    for m in members:
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest)):
            raise RuntimeError(f"unsafe path in tarball: {m.name}")
    tar.extractall(dest)  # paths validated above
    return dest / top


def fetch_snapshot(repo: str, commit: str, dest_root: str, timeout: int = 120) -> Path:
    """Download and extract ``repo`` at ``commit``. Returns the extracted root dir."""
    dest = Path(dest_root)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    url = CODELOAD.format(repo=repo, commit=commit)
    logger.info("fetching %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "trace-grag/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (github only)
        data = resp.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        root = _safe_extract(tar, dest)
    logger.info("extracted to %s (%d bytes compressed)", root, len(data))
    return root


def cleanup(dest_root: str) -> None:
    p = Path(dest_root)
    if p.exists():
        shutil.rmtree(p)
