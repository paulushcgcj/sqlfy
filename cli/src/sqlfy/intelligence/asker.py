"""
sqlfy.asker
===========
RAG pipeline for natural language schema queries.

Pipeline
--------
1. Build vector chunks from the schema graph (done once)
2. Retrieve the k most relevant chunks for the question
3. Assemble a grounded prompt with schema context
4. Call Claude (claude-sonnet-4-20250514) and stream the answer

Usage
-----
    from cli.asker import Asker

    graph  = reconstruct(files)
    asker  = Asker(graph)
    answer = asker.ask("Which tables cascade delete from users?")
    print(answer.text)

    # Streaming (yields tokens as they arrive)
    for token in asker.ask_stream("What indexes exist on orders?"):
        print(token, end='', flush=True)

    # CLI-friendly: prints directly to stdout
    asker.ask_print("Which columns are nullable FKs?")
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Iterator, Optional

from ..output.chunker import build_chunks
from ..domain.models import SchemaGraph
from .retriever import make_retriever, RetrievedChunk
from .chunk_cache import ChunkCache, compute_schema_fingerprint


# ─────────────────────────────────────────────
# RESULT TYPE
# ─────────────────────────────────────────────

@dataclass
class AskResult:
    question:       str
    answer:         str
    retrieved:      list[RetrievedChunk] = field(default_factory=list)
    model:          str = 'claude-sonnet-4-20250514'
    input_tokens:   int = 0
    output_tokens:  int = 0

    def to_dict(self) -> dict:
        return {
            'question': self.question,
            'answer':   self.answer,
            'model':    self.model,
            'usage':    {'input': self.input_tokens, 'output': self.output_tokens},
            'sources':  [{'id': r.chunk_id, 'title': r.title, 'score': r.score}
                         for r in self.retrieved],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ─────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a database schema expert assistant called sqlfy.

You have been given a set of schema context chunks extracted from Flyway \
SQL migration files. Each chunk represents part of the database schema \
(a table definition, relationship map, or schema summary).

Rules:
- Answer ONLY based on the provided schema context. Do not invent tables, \
columns, or relationships that are not in the context.
- Be precise about column types, constraints (PK, FK, NOT NULL, UNIQUE), \
and FK relationships (including ON DELETE behaviour).
- If the answer cannot be determined from the context, say so clearly.
- Format answers in clear, readable prose. Use bullet points or tables \
when comparing multiple items. Use backticks for table/column names.
- When referencing a table, always use its fully-qualified name \
(e.g. `APP.USERS` not just `USERS`) unless the schema is obvious.
- Keep answers concise — one to three paragraphs unless the question \
explicitly asks for a detailed breakdown.
"""

def _build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    parts.append('## Schema Context\n')
    for i, chunk in enumerate(chunks, 1):
        parts.append(f'### Context {i}: {chunk.title} (relevance: {chunk.score:.3f})')
        parts.append(f'*{chunk.hint}*\n')
        parts.append('```')
        parts.append(chunk.content)
        parts.append('```\n')
    parts.append('---')
    parts.append(f'## Question\n\n{question}')
    return '\n'.join(parts)


# ─────────────────────────────────────────────
# ASKER
# ─────────────────────────────────────────────

class Asker:
    """
    RAG-powered schema query engine.

    Args:
        graph:          SchemaGraph from reconstruct().
        api_key:        Anthropic API key (defaults to ANTHROPIC_API_KEY env var).
        use_embeddings: Use vector embeddings for retrieval (requires Voyage API key).
        k:              Number of chunks to retrieve per question (default 6).
        model:          Claude model to use.
        use_cache:      Enable chunk caching (default True).
        files:          Migration files for fingerprint computation (required for caching).
    """

    _API_URL = 'https://api.anthropic.com/v1/messages'
    _MODEL   = 'claude-sonnet-4-20250514'

    def __init__(
        self,
        graph:          SchemaGraph,
        api_key:        Optional[str] = None,
        use_embeddings: bool = False,
        k:              int  = 6,
        model:          Optional[str] = None,
        use_cache:      bool = True,
        files:          Optional[list[dict]] = None,
    ) -> None:
        from ..config import settings as _settings
        self._api_key  = api_key or _settings.api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self._k        = k
        self._model    = model or self._MODEL
        
        # Try to load from cache if enabled
        chunks_from_cache = None
        embeddings_from_cache = None
        cache_hit = False
        
        if use_cache and files:
            fingerprint = compute_schema_fingerprint(files)
            chunk_cache = ChunkCache()
            cached = chunk_cache.get(fingerprint)
            
            if cached:
                chunks_from_cache, embeddings_from_cache = cached
                cache_hit = True
                if chunks_from_cache:
                    print(f"✓ Loaded {len(chunks_from_cache)} chunks from cache", file=sys.stderr)
        
        # Build chunks if not cached
        if chunks_from_cache:
            self._chunks = chunks_from_cache
        else:
            self._chunks = build_chunks(graph)
            
            # Cache chunks if enabled
            if use_cache and files:
                fingerprint = compute_schema_fingerprint(files)
                chunk_cache = ChunkCache()
                # We'll cache embeddings later if using EmbeddingRetriever
                chunk_cache.put(fingerprint, self._chunks, metadata={"dialect": graph.dialect})
        
        # Build retriever (may use cached embeddings if available)
        self._retriever = make_retriever(
            self._chunks,
            use_embeddings=use_embeddings,
            api_key=self._api_key,
            cached_embeddings=embeddings_from_cache if cache_hit else None,
        )

        if not self._api_key:
            raise ValueError(
                'ANTHROPIC_API_KEY not set. '
                'Export it: export ANTHROPIC_API_KEY=sk-ant-...'
            )

    # ── Public API ──────────────────────────────────────────────────────

    def ask(self, question: str, k: Optional[int] = None) -> AskResult:
        """Ask a question and return the full answer synchronously."""
        hits     = self._retriever.retrieve(question, k=k or self._k)
        prompt   = _build_prompt(question, hits)
        response = self._call_api(prompt, stream=False)

        content = response.get('content', [{}])
        text    = next((b['text'] for b in content if b.get('type') == 'text'), '')
        usage   = response.get('usage', {})

        return AskResult(
            question=question, answer=text, retrieved=hits,
            model=self._model,
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
        )

    def ask_stream(self, question: str, k: Optional[int] = None) -> Iterator[str]:
        """Ask a question and yield answer tokens as they arrive (streaming)."""
        hits   = self._retriever.retrieve(question, k=k or self._k)
        prompt = _build_prompt(question, hits)
        yield from self._stream_api(prompt)

    def ask_print(
        self,
        question: str,
        k:        Optional[int] = None,
        show_sources: bool = True,
        stream:   bool = True,
    ) -> AskResult:
        """
        Ask a question and print the answer to stdout in real time.
        Returns the full AskResult after streaming completes.
        """
        hits = self._retriever.retrieve(question, k=k or self._k)

        if show_sources and hits:
            print('\n\033[2m── Retrieved context ──────────────────────────────────\033[0m')
            for h in hits:
                print(f'\033[2m  [{h.score:.3f}] {h.title}\033[0m')
            print('\033[2m───────────────────────────────────────────────────────\033[0m\n')

        print('\033[1m◆ Answer\033[0m\n')

        full_text = ''
        if stream:
            prompt = _build_prompt(question, hits)
            for token in self._stream_api(prompt):
                print(token, end='', flush=True)
                full_text += token
            print('\n')
            return AskResult(
                question=question, answer=full_text, retrieved=hits,
                model=self._model,
            )
        else:
            result = self.ask(question, k=k)
            print(result.answer)
            print()
            if show_sources:
                print(f'\033[2mTokens used: {result.input_tokens} in / {result.output_tokens} out\033[0m')
            return result

    # ── API calls ───────────────────────────────────────────────────────

    def _call_api(self, user_prompt: str, stream: bool = False) -> dict:
        payload = json.dumps({
            'model':      self._model,
            'max_tokens': 1024,
            'system':     _SYSTEM_PROMPT,
            'messages':   [{'role': 'user', 'content': user_prompt}],
            'stream':     stream,
        }).encode()

        req = urllib.request.Request(
            self._API_URL,
            data=payload,
            headers={
                'Content-Type':      'application/json',
                'x-api-key':         self._api_key,
                'anthropic-version': '2023-06-01',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f'Anthropic API error {e.code}: {body}') from e

    def _stream_api(self, user_prompt: str) -> Iterator[str]:
        payload = json.dumps({
            'model':      self._model,
            'max_tokens': 1024,
            'system':     _SYSTEM_PROMPT,
            'messages':   [{'role': 'user', 'content': user_prompt}],
            'stream':     True,
        }).encode()

        req = urllib.request.Request(
            self._API_URL,
            data=payload,
            headers={
                'Content-Type':      'application/json',
                'x-api-key':         self._api_key,
                'anthropic-version': '2023-06-01',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw_line in resp:
                    line = raw_line.decode().strip()
                    if not line.startswith('data:'):
                        continue
                    data = line[5:].strip()
                    if data == '[DONE]':
                        return
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get('type') == 'content_block_delta':
                        delta = event.get('delta', {})
                        if delta.get('type') == 'text_delta':
                            yield delta.get('text', '')
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f'Anthropic API error {e.code}: {body}') from e


# ─────────────────────────────────────────────
# MULTI-TURN CHAT SESSION
# ─────────────────────────────────────────────

class ChatSession:
    """
    Multi-turn conversational session over the schema.

    Maintains message history so follow-up questions work naturally:
      Q: "Which tables have FKs to users?"
      Q: "What are the cascade rules for those?"  ← understands "those"

    Args:
        asker:      An Asker instance (shared retriever/chunks).
        max_turns:  Max history turns to keep in context (default 10).
    """

    def __init__(self, asker: Asker, max_turns: int = 10) -> None:
        self._asker     = asker
        self._max_turns = max_turns
        self._history:  list[dict] = []   # [{ role, content }]

    def ask(self, question: str, stream: bool = True) -> str:
        """Ask a follow-up question in context. Returns the answer text."""
        hits   = self._asker._retriever.retrieve(question, k=self._asker._k)
        ctx    = _build_prompt(question, hits)

        # Build messages array with history
        messages = list(self._history)
        messages.append({'role': 'user', 'content': ctx})

        full_text = ''
        if stream:
            for token in self._call_stream(messages):
                print(token, end='', flush=True)
                full_text += token
            print()
        else:
            full_text = self._call(messages)
            print(full_text)

        # Append to history (keep last N turns)
        self._history.append({'role': 'user',      'content': question})
        self._history.append({'role': 'assistant',  'content': full_text})
        if len(self._history) > self._max_turns * 2:
            self._history = self._history[-(self._max_turns * 2):]

        return full_text

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def _call(self, messages: list[dict]) -> str:
        payload = json.dumps({
            'model':      self._asker._model,
            'max_tokens': 1024,
            'system':     _SYSTEM_PROMPT,
            'messages':   messages,
        }).encode()
        req = urllib.request.Request(
            Asker._API_URL, data=payload,
            headers={
                'Content-Type':      'application/json',
                'x-api-key':         self._asker._api_key,
                'anthropic-version': '2023-06-01',
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return next((b['text'] for b in data.get('content', []) if b.get('type') == 'text'), '')

    def _call_stream(self, messages: list[dict]) -> Iterator[str]:
        payload = json.dumps({
            'model':      self._asker._model,
            'max_tokens': 1024,
            'system':     _SYSTEM_PROMPT,
            'messages':   messages,
            'stream':     True,
        }).encode()
        req = urllib.request.Request(
            Asker._API_URL, data=payload,
            headers={
                'Content-Type':      'application/json',
                'x-api-key':         self._asker._api_key,
                'anthropic-version': '2023-06-01',
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode().strip()
                if not line.startswith('data:'): continue
                data = line[5:].strip()
                if data == '[DONE]': return
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if event.get('type') == 'content_block_delta':
                    delta = event.get('delta', {})
                    if delta.get('type') == 'text_delta':
                        yield delta.get('text', '')