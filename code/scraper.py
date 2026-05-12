"""
Async web scraper for the three support corpora.

Design decisions:
- Uses httpx (async) + BeautifulSoup for robust HTML parsing
- Rate-limited with asyncio.Semaphore to avoid hammering servers
- Content is chunked and stored as JSONL for fast re-use
- Gracefully handles redirects, timeouts, and bot-protection pages
- Idempotent: skips URLs already present in the cache
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

from config import (
    COLLECTION_URLS,
    CORPUS_CACHE,
    SCRAPER_CFG,
    DATA_DIR,
    ScraperConfig,
)
from models import CorpusChunk

console = Console()


# ──────────────────────────────────────────────────────────────────
# HTML → clean text helpers
# ──────────────────────────────────────────────────────────────────


def _extract_text(soup: BeautifulSoup) -> str:
    """Remove scripts/styles and return clean visible text."""
    for tag in soup(
        ["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg", "form"]
    ):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Collapse excessive whitespace
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _extract_title(soup: BeautifulSoup, url: str) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True).split("|")[0].strip()
    return urlparse(url).path.split("/")[-1].replace("-", " ").title()


def _extract_article_links(soup: BeautifulSoup, base_url: str, company: str) -> List[str]:
    """
    Pull article/page hrefs from a collection/category listing page.
    Filters to stay within the same domain & relevant path prefixes.
    """
    domain = urlparse(base_url).netloc
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc != domain:
            continue
        path = parsed.path
        # Company-specific path filters
        if company == "HackerRank" and "/articles/" not in path:
            continue
        if company == "Claude" and "/articles/" not in path:
            continue
        # Avoid duplicate anchors / query-string variants
        clean = parsed._replace(query="", fragment="").geturl()
        if clean not in links:
            links.append(clean)
    return links


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Split long text into overlapping chunks (by character count)."""
    if len(text) <= chunk_size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# ──────────────────────────────────────────────────────────────────
# Core scraper class
# ──────────────────────────────────────────────────────────────────


class SupportScraper:
    def __init__(self, cfg: ScraperConfig = SCRAPER_CFG):
        self.cfg = cfg
        self._seen_urls: Set[str] = set()
        self._sem = asyncio.Semaphore(cfg.max_concurrent)
        self._client: httpx.AsyncClient | None = None

    # ── HTTP helpers ───────────────────────────────────────────────

    async def _get(self, url: str) -> str | None:
        """Fetch URL with rate limiting and error handling."""
        async with self._sem:
            await asyncio.sleep(self.cfg.request_delay)
            try:
                resp = await self._client.get(
                    url,
                    timeout=self.cfg.timeout,
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    return resp.text
                console.print(f"[yellow]  HTTP {resp.status_code} for {url}[/yellow]")
            except Exception as exc:
                console.print(
                    f"[yellow]  Request failed ({exc.__class__.__name__}) " f"for {url}[/yellow]"
                )
        return None

    # ── Per-company scrapers ───────────────────────────────────────

    async def _scrape_article(self, url: str, company: str, section: str = "") -> List[CorpusChunk]:
        """Fetch a single article URL and return chunks."""
        if url in self._seen_urls:
            return []
        self._seen_urls.add(url)

        html = await self._get(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        title = _extract_title(soup, url)
        text = _extract_text(soup)

        if len(text) < self.cfg.min_content_length:
            return []

        chunks = []
        for i, chunk in enumerate(_chunk_text(text, self.cfg.chunk_size, 100)):
            chunks.append(
                CorpusChunk(
                    source=company,
                    url=url,
                    title=title if i == 0 else f"{title} (cont.)",
                    content=chunk,
                    section=section,
                )
            )
        return chunks

    async def _scrape_collection(
        self, collection_url: str, company: str, progress: Progress, task: TaskID
    ) -> List[CorpusChunk]:
        """Fetch an index page and scrape linked articles."""
        html = await self._get(collection_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        section = _extract_title(soup, collection_url)

        # For Visa the collection page IS the article
        if company == "Visa":
            chunks = await self._scrape_article(collection_url, company, section)
            progress.advance(task)
            return chunks

        article_links = _extract_article_links(soup, collection_url, company)[
            : self.cfg.max_articles_per_collection
        ]

        all_chunks: List[CorpusChunk] = []
        for link in article_links:
            chunks = await self._scrape_article(link, company, section)
            all_chunks.extend(chunks)
            progress.advance(task)

        return all_chunks

    # ── Public interface ───────────────────────────────────────────

    async def scrape_all(self) -> List[CorpusChunk]:
        """Scrape all three knowledge bases concurrently."""
        headers = {"User-Agent": self.cfg.user_agent}
        async with httpx.AsyncClient(headers=headers) as client:
            self._client = client

            all_chunks: List[CorpusChunk] = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                tasks = {}
                for company, urls in COLLECTION_URLS.items():
                    total = (
                        sum(SCRAPER_CFG.max_articles_per_collection for _ in urls)
                        if company != "Visa"
                        else len(urls)
                    )
                    tasks[company] = progress.add_task(f"Scraping {company}…", total=total)

                coros = [
                    self._scrape_collection(url, company, progress, tasks[company])
                    for company, urls in COLLECTION_URLS.items()
                    for url in urls
                ]
                results = await asyncio.gather(*coros, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception):
                    console.print(f"[red]Scrape error: {res}[/red]")
                elif isinstance(res, list):
                    all_chunks.extend(res)

        return all_chunks


# ──────────────────────────────────────────────────────────────────
# Corpus cache  (JSONL)
# ──────────────────────────────────────────────────────────────────


def save_corpus(chunks: List[CorpusChunk], path: Path = CORPUS_CACHE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")
    console.print(f"[green]✓ Saved {len(chunks):,} chunks → {path}[/green]")


def load_corpus(path: Path = CORPUS_CACHE) -> List[CorpusChunk]:
    if not path.exists():
        return []
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    chunks.append(CorpusChunk.model_validate_json(line))
                except Exception:
                    pass
    return chunks


def corpus_exists(path: Path = CORPUS_CACHE) -> bool:
    return path.exists() and path.stat().st_size > 0


# ──────────────────────────────────────────────────────────────────
# Convenience: build corpus (scrape then save)
# ──────────────────────────────────────────────────────────────────


def build_corpus(force: bool = False) -> List[CorpusChunk]:
    """
    Build or reload the support corpus.
    Pass force=True to re-scrape even if cache exists.

    Always includes the built-in seed corpus as a baseline.
    """
    # Always load seed corpus as baseline
    from seed_corpus import get_seed_corpus

    seed = get_seed_corpus()

    if not force and corpus_exists():
        console.print(f"[cyan]Loading cached corpus from {CORPUS_CACHE}…[/cyan]")
        cached = load_corpus()
        # Merge: prefer cached (scraped) over seed
        combined = cached + [s for s in seed if s.url not in {c.url for c in cached}]
        console.print(
            f"[green]✓ Loaded {len(combined):,} chunks "
            f"({len(cached):,} scraped + {len(seed):,} seed).[/green]"
        )
        return combined

    console.print("[bold cyan]Building support corpus (scraping + seed)…[/bold cyan]")
    start = time.time()
    try:
        scraped = asyncio.run(SupportScraper().scrape_all())
    except Exception as exc:
        console.print(f"[yellow]Scraping failed ({exc}), using seed corpus only.[/yellow]")
        scraped = []

    elapsed = time.time() - start
    # Merge scraped with seed
    scraped_urls = {c.url for c in scraped}
    combined = scraped + [s for s in seed if s.url not in scraped_urls]

    console.print(
        f"[green]✓ Built corpus: {len(combined):,} chunks "
        f"({len(scraped):,} scraped + {len(seed):,} seed) in {elapsed:.1f}s[/green]"
    )
    if scraped:
        save_corpus(combined)
    return combined
