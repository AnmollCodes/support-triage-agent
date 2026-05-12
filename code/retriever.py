"""
Hybrid Retrieval Engine: BM25 + TF-IDF

Design rationale:
- BM25 (rank_bm25) is state-of-the-art keyword retrieval; outperforms TF-IDF
  for short queries on domain-specific corpora.
- TF-IDF acts as a soft fallback / re-ranker to catch term variations.
- Company filter: if the ticket specifies a company we restrict candidate pool
  to that company's corpus first, then fall back to the full pool if the
  company-filtered pool yields no signal.
- The combined score is a weighted linear combination, deterministic.
"""

from __future__ import annotations

import math
import re
import string
from collections import Counter
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from config import RETRIEVER_CFG, RetrieverConfig
from models import CorpusChunk, RetrievedDoc


# ──────────────────────────────────────────────────────────────────
# Tokenisation helpers
# ──────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset("""
a an the is are was were be been being have has had do does did will would
could should may might shall can i me my we our you your he she it its
they them their this that these those what which who how when where why
in on at to for of with by from as into about between through during
before after above below up down out over under again further then once
""".split())


def _tokenise(text: str) -> List[str]:
    """Lower-case, strip punctuation, remove stop-words, return tokens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t and t not in _STOPWORDS]
    return tokens


# ──────────────────────────────────────────────────────────────────
# TF-IDF helpers (no sklearn dependency)
# ──────────────────────────────────────────────────────────────────

def _build_tfidf(chunks: List[CorpusChunk]):
    """
    Returns:
        doc_tf  – list of Counter (term → freq) per doc
        idf     – dict (term → idf value) across corpus
    """
    N = len(chunks)
    doc_tf: List[Counter] = []
    df: Counter = Counter()

    for chunk in chunks:
        tokens = _tokenise(chunk.full_text)
        tf = Counter(tokens)
        doc_tf.append(tf)
        for term in set(tokens):
            df[term] += 1

    idf: Dict[str, float] = {
        term: math.log((N + 1) / (freq + 1)) + 1.0
        for term, freq in df.items()
    }
    return doc_tf, idf


def _tfidf_score(query_tokens: List[str], tf: Counter,
                 idf: Dict[str, float]) -> float:
    """Cosine-like TF-IDF similarity (dot-product, unnormalised)."""
    score = 0.0
    for t in query_tokens:
        if t in tf and t in idf:
            score += tf[t] * idf[t]
    return score


# ──────────────────────────────────────────────────────────────────
# Main Retriever class
# ──────────────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Builds BM25 + TF-IDF indices over the corpus.
    Supports optional company-scoped retrieval.
    """

    def __init__(
        self,
        chunks: List[CorpusChunk],
        cfg: RetrieverConfig = RETRIEVER_CFG,
    ) -> None:
        self.cfg    = cfg
        self.chunks = chunks

        # Build per-company sub-indices and a global index
        self._indices: Dict[str, Tuple] = {}   # company → (bm25, doc_tf, idf, sub_chunks)
        self._global: Tuple | None = None

        self._build_indices()

    # ── Index construction ─────────────────────────────────────────

    def _build_single_index(
        self, chunks: List[CorpusChunk]
    ) -> Tuple:
        tokenised = [_tokenise(c.full_text) for c in chunks]
        bm25     = BM25Okapi(tokenised)
        doc_tf, idf = _build_tfidf(chunks)
        return bm25, doc_tf, idf, chunks

    def _build_indices(self) -> None:
        # Global
        self._global = self._build_single_index(self.chunks)

        # Per-company
        companies = set(c.source for c in self.chunks)
        for co in companies:
            sub = [c for c in self.chunks if c.source == co]
            if sub:
                self._indices[co] = self._build_single_index(sub)

    # ── Query ──────────────────────────────────────────────────────

    def _score_index(
        self,
        query: str,
        index_tuple: Tuple,
        top_k: int,
    ) -> List[RetrievedDoc]:
        bm25, doc_tf, idf, sub_chunks = index_tuple
        q_tokens = _tokenise(query)
        if not q_tokens:
            return []

        bm25_scores  = bm25.get_scores(q_tokens)
        tfidf_scores = [
            _tfidf_score(q_tokens, tf, idf) for tf in doc_tf
        ]

        # Normalise to [0, 1]
        bm25_max  = max(bm25_scores)  if bm25_scores.any()   else 1.0
        tfidf_max = max(tfidf_scores) if any(tfidf_scores)   else 1.0
        bm25_max  = bm25_max  if bm25_max  > 0 else 1.0
        tfidf_max = tfidf_max if tfidf_max > 0 else 1.0

        combined = [
            self.cfg.bm25_weight  * (b / bm25_max)
            + self.cfg.tfidf_weight * (t / tfidf_max)
            for b, t in zip(bm25_scores, tfidf_scores)
        ]

        # Sort descending
        ranked = sorted(
            enumerate(combined), key=lambda x: x[1], reverse=True
        )

        results = []
        seen_urls: set = set()
        for idx, score in ranked[:top_k * 3]:            # over-fetch, then dedupe
            if score < self.cfg.min_score_threshold:
                break
            chunk = sub_chunks[idx]
            key   = (chunk.url, chunk.title)
            if key in seen_urls:
                continue
            seen_urls.add(key)
            results.append(RetrievedDoc(chunk=chunk, score=round(score, 4)))
            if len(results) >= top_k:
                break

        return results

    def retrieve(
        self,
        query: str,
        company: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[RetrievedDoc]:
        """
        Retrieve the top-k most relevant chunks for a query.

        If `company` is provided and has a dedicated index,
        we first query that; if results are weak, we fall back
        to the global index.
        """
        k = top_k or self.cfg.top_k

        # Company-scoped search
        if company and company in self._indices:
            results = self._score_index(
                query, self._indices[company], k
            )
            if results:
                return results

        # Global fallback
        return self._score_index(query, self._global, k)

    # ── Convenience: format for prompt ────────────────────────────

    def format_for_prompt(
        self,
        docs: List[RetrievedDoc],
        max_chars: int = 4000,
    ) -> str:
        """Return a compact string suitable for inclusion in an LLM prompt."""
        parts: List[str] = []
        total = 0
        for i, doc in enumerate(docs, 1):
            header = (
                f"[DOC {i}] [{doc.chunk.source}] "
                f"{doc.chunk.title}"
                + (f" — {doc.chunk.section}" if doc.chunk.section else "")
                + f" (score={doc.score})"
            )
            body = doc.chunk.content[:600]          # cap per-doc
            entry = f"{header}\n{body}\n"
            if total + len(entry) > max_chars:
                break
            parts.append(entry)
            total += len(entry)
        return "\n".join(parts) if parts else "No relevant documentation found."
