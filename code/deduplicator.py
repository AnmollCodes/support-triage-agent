"""
deduplicator.py — Feature 4: Ticket Similarity & Deduplication Engine

Finds duplicate/near-duplicate tickets in a batch using TF-IDF cosine similarity.
Prevents agents from doing the same work twice.

Outputs:
  - DuplicateGroup list: clusters of similar tickets with a similarity score
  - For each ticket: is_duplicate bool, master_ticket_id, similarity_score
  - Dedup report: how many tickets were actually unique
"""

from __future__ import annotations
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DuplicateGroup:
    master_idx: int  # 1-indexed ticket number (primary)
    duplicate_idxs: List[int]  # 1-indexed duplicates
    similarity: float  # max similarity score (0-1)
    shared_topic: str


@dataclass
class DedupResult:
    is_duplicate: bool = False
    master_ticket_id: int = 0  # 1-indexed; 0 = no master
    similarity_score: float = 0.0
    shared_topic: str = ""


_STOPWORDS = frozenset("""
a an the is are was were be been being have has had do does did will would
could should may might shall can i me my we our you your he she it its
they them their this that these those what which who how when where why
in on at to for of with by from as into about between through during
""".split())


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t and t not in _STOPWORDS and len(t) > 2]


def _tfidf_vectors(docs: List[List[str]]) -> List[Dict[str, float]]:
    N = len(docs)
    df: Counter = Counter()
    for tokens in docs:
        for term in set(tokens):
            df[term] += 1
    idf = {t: math.log((N + 1) / (f + 1)) + 1 for t, f in df.items()}

    vectors = []
    for tokens in docs:
        tf = Counter(tokens)
        total = max(len(tokens), 1)
        vec = {t: (cnt / total) * idf.get(t, 0) for t, cnt in tf.items()}
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vec = {t: v / norm for t, v in vec.items()}
        vectors.append(vec)
    return vectors


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    shared = set(a) & set(b)
    return sum(a[t] * b[t] for t in shared)


def _top_shared_terms(a: List[str], b: List[str], n: int = 3) -> str:
    sa, sb = set(a), set(b)
    shared = [t for t in (sa & sb) if len(t) > 3]
    return (
        ", ".join(sorted(shared, key=lambda t: -(a.count(t) + b.count(t)))[:n]) or "similar topic"
    )


def find_duplicates(
    issues: List[str],
    threshold: float = 0.55,
) -> Tuple[List[DedupResult], List[DuplicateGroup]]:
    """
    Args:
        issues:    list of raw ticket issue strings (0-indexed)
        threshold: cosine similarity above which two tickets are "duplicate"

    Returns:
        (per_ticket_results, duplicate_groups)
    """
    tokenized = [_tokenize(txt) for txt in issues]
    vectors = _tfidf_vectors(tokenized)
    n = len(issues)

    results: List[DedupResult] = [DedupResult() for _ in range(n)]
    groups: List[DuplicateGroup] = []

    assigned = set()  # indices already claimed as duplicates

    for i in range(n):
        if i in assigned:
            continue
        dups = []
        for j in range(i + 1, n):
            if j in assigned:
                continue
            sim = _cosine(vectors[i], vectors[j])
            if sim >= threshold:
                shared = _top_shared_terms(tokenized[i], tokenized[j])
                dups.append((j, sim, shared))

        if dups:
            dup_idxs = [d[0] for d in dups]
            max_sim = max(d[1] for d in dups)
            topic = dups[0][2]
            groups.append(
                DuplicateGroup(
                    master_idx=i + 1,
                    duplicate_idxs=[d + 1 for d in dup_idxs],
                    similarity=round(max_sim, 3),
                    shared_topic=topic,
                )
            )
            for j, sim, topic in dups:
                assigned.add(j)
                results[j] = DedupResult(
                    is_duplicate=True,
                    master_ticket_id=i + 1,
                    similarity_score=round(sim, 3),
                    shared_topic=topic,
                )

    return results, groups
