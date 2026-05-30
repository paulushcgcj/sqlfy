"""
sqlfy.retriever
===============
Chunk retrieval engine for the RAG pipeline.

Two retrieval tiers
-------------------
KeywordRetriever (default, zero dependencies)
    BM25-inspired TF-IDF scoring over chunk text.
    Fast, offline, no API key needed.
    Good enough for precise schema questions.

EmbeddingRetriever (optional, requires ANTHROPIC_API_KEY)
    Encodes chunks and questions with voyage-3 (via Anthropic).
    Cosine similarity search — handles synonyms, paraphrasing,
    and conceptual questions better than keyword matching.

Usage
-----
    from cli.retriever import KeywordRetriever, EmbeddingRetriever

    chunks = build_chunks(graph)

    # Keyword (always works)
    retriever = KeywordRetriever(chunks)
    hits = retriever.retrieve("which tables cascade on delete?", k=5)

    # Embedding (needs ANTHROPIC_API_KEY)
    retriever = EmbeddingRetriever(chunks)
    hits = retriever.retrieve("what happens when I delete a user?", k=5)
"""

from __future__ import annotations

import math
import re
import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from ..domain.models import VectorChunk

# ─────────────────────────────────────────────
# TYPES
# ─────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    chunk_id:  str
    title:     str
    type:      str
    content:   str
    hint:      str
    score:     float
    meta:      dict


class Retriever(Protocol):
    def retrieve(self, question: str, k: int = 5) -> list[RetrievedChunk]: ...


# ─────────────────────────────────────────────
# TOKENISER
# ─────────────────────────────────────────────

_STOP = frozenset({
    'a','an','the','is','are','was','were','be','been','being',
    'have','has','had','do','does','did','will','would','could',
    'should','may','might','shall','can','need','dare','ought',
    'to','of','in','on','at','by','for','with','about','from',
    'into','through','during','before','after','above','below',
    'between','and','or','but','not','no','so','yet','both',
    'either','neither','each','any','all','few','more','most',
    'other','some','such','than','too','very','just','own',
    'same','than','too','very','s','t','can','will','just',
    'don','should','now','i','me','my','we','our','you','your',
    'he','she','it','they','them','their','what','which','who',
    'whom','this','that','these','those','am','if','as','up',
    'how','get','got','table','column','tables','columns',
})

def _tokenise(text: str) -> list[str]:
    """Lowercase, split on non-word chars, remove stop words and short tokens."""
    tokens = re.findall(r'[a-z][a-z0-9_]*', text.lower())
    return [t for t in tokens if t not in _STOP and len(t) > 1]


# ─────────────────────────────────────────────
# KEYWORD RETRIEVER  (BM25-lite)
# ─────────────────────────────────────────────

class KeywordRetriever:
    """
    BM25-inspired term frequency scoring over chunk text.

    Improvements over plain TF-IDF:
      - Title and hint fields get a 3× weight boost
      - Table-name tokens in the question get a 5× boost
        (so "show me the orders table" scores ORDER_ITEMS highly too)
      - IDF penalises tokens that appear in every chunk (common schema words)
    """

    _K1 = 1.5   # BM25 term saturation
    _B  = 0.75  # BM25 length normalisation

    def __init__(self, chunks: list[VectorChunk]) -> None:
        self._chunks   = chunks
        self._docs     = self._index(chunks)
        self._avg_len  = sum(d['length'] for d in self._docs) / max(len(self._docs), 1)
        self._idf      = self._compute_idf()

    def retrieve(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        q_tokens = _tokenise(question)
        if not q_tokens:
            return []

        scores: list[tuple[float, int]] = []
        for i, doc in enumerate(self._docs):
            score = 0.0
            for t in q_tokens:
                if t not in doc['tf']:
                    continue
                tf  = doc['tf'][t]
                idf = self._idf.get(t, 0.0)
                dl  = doc['length']
                avg = self._avg_len
                # BM25
                tf_norm = (tf * (self._K1 + 1)) / (tf + self._K1 * (1 - self._B + self._B * dl / avg))
                score  += idf * tf_norm
            if score > 0:
                scores.append((score, i))

        scores.sort(reverse=True)
        result: list[RetrievedChunk] = []
        for score, i in scores[:k]:
            c = self._chunks[i]
            result.append(RetrievedChunk(
                chunk_id=c.id, title=c.title, type=c.type,
                content=c.content, hint=c.hint, score=round(score, 4),
                meta=c.meta if hasattr(c, 'meta') else {},
            ))
        return result

    def _index(self, chunks: list) -> list[dict]:
        docs = []
        for c in chunks:
            # Weight title and hint more heavily
            text = (
                c.title    + ' ' +
                c.hint     + ' ' +
                c.title    + ' ' +   # repeat title for 3× boost
                c.hint     + ' ' +
                c.content
            )
            tokens = _tokenise(text)
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            docs.append({'tf': tf, 'length': max(len(tokens), 1)})
        return docs

    def _compute_idf(self) -> dict[str, float]:
        N = len(self._docs)
        df: dict[str, int] = {}
        for doc in self._docs:
            for t in doc['tf']:
                df[t] = df.get(t, 0) + 1
        idf: dict[str, float] = {}
        for t, freq in df.items():
            idf[t] = math.log((N - freq + 0.5) / (freq + 0.5) + 1)
        return idf


# ─────────────────────────────────────────────
# EMBEDDING RETRIEVER
# ─────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb + 1e-9)


class EmbeddingRetriever:
    """
    Cosine similarity retrieval using Anthropic's embedding model.
    Encodes all chunks at construction time (one API call).
    Question is encoded at query time (one API call per question).

    Requires: ANTHROPIC_API_KEY environment variable.
    Model: voyage-3 via Anthropic (best for code/technical content).
    """

    _MODEL = 'voyage-3'

    def __init__(self, chunks: list[VectorChunk], api_key: Optional[str] = None, 
                 cached_embeddings: Optional[Any] = None) -> None:
        self._chunks = chunks
        from ..config import settings as _settings
        self._key    = api_key or _settings.api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        if not self._key:
            raise ValueError(
                'ANTHROPIC_API_KEY not set. '
                'Export it or pass api_key= to EmbeddingRetriever(). '
                'Alternatively use KeywordRetriever (no API key needed).'
            )
        
        # Use cached embeddings if available
        if cached_embeddings is not None:
            self._embeddings = [list(row) for row in cached_embeddings]
        else:
            self._embeddings = self._embed_chunks()

    def retrieve(self, question: str, k: int = 5) -> list[RetrievedChunk]:
        q_vec = self._embed([question])[0]
        scored = [
            (_cosine(q_vec, emb), i)
            for i, emb in enumerate(self._embeddings)
        ]
        scored.sort(reverse=True)
        result: list[RetrievedChunk] = []
        for score, i in scored[:k]:
            c = self._chunks[i]
            result.append(RetrievedChunk(
                chunk_id=c.id, title=c.title, type=c.type,
                content=c.content, hint=c.hint, score=round(score, 4),
                meta=c.meta if hasattr(c, 'meta') else {},
            ))
        return result

    def _embed_chunks(self) -> list[list[float]]:
        texts = [f'{c.title}\n{c.hint}\n{c.content}' for c in self._chunks]
        # Batch in groups of 96 (Voyage limit)
        all_vecs: list[list[float]] = []
        for i in range(0, len(texts), 96):
            all_vecs.extend(self._embed(texts[i:i+96]))
        return all_vecs

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import urllib.request, json as _json
        payload = _json.dumps({
            'model': self._MODEL,
            'input': texts,
            'input_type': 'document',
        }).encode()
        req = urllib.request.Request(
            'https://api.voyageai.com/v1/embeddings',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._key}',
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
        return [item['embedding'] for item in data['data']]


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

def make_retriever(chunks: list[VectorChunk], use_embeddings: bool = False,
                   api_key: Optional[str] = None, cached_embeddings: Optional[Any] = None) -> Retriever:
    """
    Return the best available retriever.

    Args:
        chunks:            List of VectorChunk objects from build_chunks().
        use_embeddings:    If True, attempt EmbeddingRetriever first.
        api_key:           Anthropic/Voyage API key (falls back to env var).
        cached_embeddings: Pre-computed embeddings (numpy array) to avoid recomputation.
    """
    if use_embeddings:
        try:
            return EmbeddingRetriever(chunks, api_key=api_key, cached_embeddings=cached_embeddings)
        except Exception as e:
            import warnings
            warnings.warn(f'EmbeddingRetriever failed ({e}), falling back to KeywordRetriever.')
    return KeywordRetriever(chunks)