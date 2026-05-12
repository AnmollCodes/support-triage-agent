"""
corpus.py — Corpus management

Priority order for corpus sources:
1. data/<company>/ directory (repo-provided pre-scraped files)
2. JSONL cache (previously scraped via web)
3. Web scraping (live, fallback)

The repo ships a data/ directory with the support corpus. This module
tries to load from there first, making the agent fully offline-capable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from rich.console import Console

from config import CORPUS_CACHE, DATA_DIR, RETRIEVER_CFG
from models import CorpusChunk

console = Console()

# Map of company name → data subdirectory
COMPANY_DATA_DIRS = {
    "HackerRank": DATA_DIR / "hackerrank",
    "Claude": DATA_DIR / "claude",
    "Visa": DATA_DIR / "visa",
}


def _load_from_data_dir() -> List[CorpusChunk]:
    """
    Load support corpus from the repo's data/ directory.
    Supports .txt, .md, .json, and .jsonl files.
    """
    chunks: List[CorpusChunk] = []

    for company, dir_path in COMPANY_DATA_DIRS.items():
        if not dir_path.exists():
            continue

        for filepath in sorted(dir_path.rglob("*")):
            if not filepath.is_file():
                continue

            suffix = filepath.suffix.lower()
            try:
                if suffix == ".jsonl":
                    with open(filepath, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                data = json.loads(line)
                                chunks.append(
                                    CorpusChunk(
                                        source=data.get("source", company),
                                        url=data.get("url", str(filepath)),
                                        title=data.get("title", filepath.stem),
                                        content=data.get("content", ""),
                                        section=data.get("section", ""),
                                    )
                                )

                elif suffix == ".json":
                    with open(filepath, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            chunks.append(
                                CorpusChunk(
                                    source=item.get("source", company),
                                    url=item.get("url", str(filepath)),
                                    title=item.get("title", filepath.stem),
                                    content=item.get("content", ""),
                                    section=item.get("section", ""),
                                )
                            )
                    elif isinstance(data, dict):
                        chunks.append(
                            CorpusChunk(
                                source=data.get("source", company),
                                url=data.get("url", str(filepath)),
                                title=data.get("title", filepath.stem),
                                content=data.get("content", ""),
                                section=data.get("section", ""),
                            )
                        )

                elif suffix in (".txt", ".md"):
                    text = filepath.read_text(encoding="utf-8", errors="replace").strip()
                    if len(text) >= 50:
                        # Chunk large files
                        from scraper import _chunk_text

                        for i, chunk in enumerate(_chunk_text(text, 800, 100)):
                            title = filepath.stem.replace("-", " ").replace("_", " ").title()
                            chunks.append(
                                CorpusChunk(
                                    source=company,
                                    url=str(filepath),
                                    title=title if i == 0 else f"{title} (cont.)",
                                    content=chunk,
                                    section=dir_path.name,
                                )
                            )
            except Exception as exc:
                console.print(f"[yellow]  Skipping {filepath}: {exc}[/yellow]")

    return chunks


def _load_from_cache() -> List[CorpusChunk]:
    """Load from JSONL cache built by scraper."""
    from scraper import load_corpus

    return load_corpus(CORPUS_CACHE)


def load_or_build_corpus(force_scrape: bool = False) -> List[CorpusChunk]:
    """
    Master corpus loader with fallback chain.

    1. Repo data directory  (offline, instant)
    2. JSONL cache          (offline, fast)
    3. Web scraping         (online, slow)
    """
    if not force_scrape:
        # Try repo data dir first
        data_dir_chunks = _load_from_data_dir()
        if data_dir_chunks:
            console.print(
                f"[green]✓ Loaded {len(data_dir_chunks):,} chunks " f"from data/ directory[/green]"
            )
            return data_dir_chunks

        # Try JSONL cache
        cache_chunks = _load_from_cache()
        if cache_chunks:
            console.print(
                f"[green]✓ Loaded {len(cache_chunks):,} chunks " f"from corpus cache[/green]"
            )
            return cache_chunks

    # Fall back to live scraping
    from scraper import build_corpus

    return build_corpus(force=force_scrape)
