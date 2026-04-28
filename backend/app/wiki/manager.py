"""WikiManager — Karpathy LLM Wiki layer.

On every ingest the LLM:
  1. Reads the source text
  2. Extracts up to MAX_PAGES_PER_SOURCE key entities / concepts
  3. Creates or merges wiki pages for each entity/concept
  4. Updates wiki/<collection>/index.md  (content-oriented page catalog)
  5. Appends an entry to wiki/<collection>/log.md  (chronological record)

On query the wiki is consulted first:
  - index.md is scanned for pages relevant to the query
  - Matching pages are returned as pre-synthesized WikiPage objects
  - These are richer than raw chunks: they reflect accumulated cross-ingestion knowledge

On lint the LLM health-checks the wiki:
  - Contradictions, orphan pages, stale claims, missing cross-references
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from app.embeddings import llm_chat
from app.models.schemas import WikiPage

# How many pages the LLM may write per source (keeps cost bounded)
MAX_PAGES_PER_SOURCE = 5

# Truncate source fed to LLM (tokens ≈ chars / 4; keep well under CF free-tier limit)
SOURCE_PREVIEW_CHARS = 4000

# Root of all wiki directories (one sub-dir per collection)
_DEFAULT_WIKI_ROOT = Path(__file__).parent.parent.parent / "wiki"


class WikiManager:
    """Manages the persistent wiki layer for a rag-swarm deployment."""

    def __init__(self, wiki_root: Path | None = None):
        self.wiki_root = wiki_root or _DEFAULT_WIKI_ROOT

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collection_dir(self, collection: str) -> Path:
        d = self.wiki_root / collection
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _page_path(self, slug: str, collection: str) -> Path:
        safe = re.sub(r"[^\w\-]", "-", slug.lower().strip())
        return self._collection_dir(collection) / f"{safe}.md"

    def _index_path(self, collection: str) -> Path:
        return self._collection_dir(collection) / "index.md"

    def _log_path(self, collection: str) -> Path:
        return self._collection_dir(collection) / "log.md"

    def _read_or_empty(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    # ------------------------------------------------------------------
    # Ingest: synthesise source into wiki pages
    # ------------------------------------------------------------------

    def synthesize_source(
        self,
        source_text: str,
        filename: str,
        collection: str = "default",
    ) -> list[str]:
        """Read a source document and write/update wiki pages for it.

        Returns the list of page slugs that were written.
        """
        if not source_text.strip():
            return []

        preview = source_text[:SOURCE_PREVIEW_CHARS]
        existing_index = self._read_or_empty(self._index_path(collection))

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a disciplined wiki editor maintaining a persistent knowledge base. "
                    "Your job is to read source documents and extract key entities and concepts "
                    "as structured wiki pages. Be concise. Focus on facts, definitions, "
                    "relationships, and cross-references. Never fabricate information not present "
                    "in the source."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Source file: {filename}\n\n"
                    f"Existing wiki index (for cross-reference awareness):\n{existing_index[:1500] or '(empty)'}\n\n"
                    f"Source content (possibly truncated):\n{preview}\n\n"
                    f"Task: Identify up to {MAX_PAGES_PER_SOURCE} key entities or concepts from this source "
                    "that deserve dedicated wiki pages. For each, produce a wiki page using EXACTLY this format:\n\n"
                    "---PAGE: <slug>---\n"
                    "# <Title>\n\n"
                    "<2-4 paragraphs of synthesised knowledge. Include cross-references to other relevant "
                    "pages using [[page-slug]] notation. Note the source with: *Source: filename*>\n\n"
                    "---END---\n\n"
                    "Rules:\n"
                    "- slug must be lowercase-hyphenated, e.g. swarm-intelligence\n"
                    "- If a concept already exists in the index, update/extend its page, do NOT duplicate it\n"
                    "- Each page must end with a *Source: ...* line\n"
                    f"- Produce between 1 and {MAX_PAGES_PER_SOURCE} pages, no more\n"
                    "- Do not add commentary outside the ---PAGE / ---END blocks"
                ),
            },
        ]

        try:
            raw = llm_chat(messages, max_tokens=2048)
        except Exception:
            return []

        pages_written = self._parse_and_write_pages(raw, collection)
        if pages_written:
            self._update_index(pages_written, collection)
            self._append_log(filename, pages_written, collection)

        return pages_written

    def _parse_and_write_pages(self, llm_output: str, collection: str) -> list[str]:
        """Parse LLM output and write wiki pages to disk. Returns written slugs."""
        pattern = re.compile(
            r"---PAGE:\s*(?P<slug>[^\-\n]+)---\s*(?P<content>.*?)---END---",
            re.DOTALL,
        )
        written: list[str] = []
        for match in pattern.finditer(llm_output):
            slug = match.group("slug").strip()
            content = match.group("content").strip()
            if not slug or not content:
                continue

            page_path = self._page_path(slug, collection)

            # If the page already exists, merge: append new content under a section
            if page_path.exists():
                existing = page_path.read_text(encoding="utf-8")
                # Check if this source is already represented to avoid duplication
                if f"*Source: " in content:
                    merged = existing.rstrip() + "\n\n---\n\n" + content
                else:
                    merged = existing
                page_path.write_text(merged, encoding="utf-8")
            else:
                page_path.write_text(content, encoding="utf-8")

            # Normalise slug to match the actual filename written
            written.append(re.sub(r"[^\w\-]", "-", slug.lower().strip()))

        return written

    def _update_index(self, slugs: list[str], collection: str) -> None:
        """Rebuild index.md — a catalog of all wiki pages."""
        col_dir = self._collection_dir(collection)
        pages = sorted(p for p in col_dir.glob("*.md") if p.name not in ("index.md", "log.md"))

        lines = [
            "# Wiki Index\n",
            f"*Collection: `{collection}` — {len(pages)} pages — last updated {_utcnow()}*\n\n",
            "| Page | Summary |\n",
            "|------|----------|\n",
        ]
        for page_path in pages:
            text = page_path.read_text(encoding="utf-8", errors="replace")
            # First non-empty non-heading line as summary
            summary = ""
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    summary = stripped[:120]
                    break
            page_slug = page_path.stem
            lines.append(f"| [[{page_slug}]] | {summary} |\n")

        self._index_path(collection).write_text("".join(lines), encoding="utf-8")

    def _append_log(self, filename: str, pages: list[str], collection: str) -> None:
        """Append a timestamped ingest entry to log.md."""
        log_path = self._log_path(collection)
        timestamp = _utcnow()
        pages_list = ", ".join(f"[[{p}]]" for p in pages)
        entry = f"## [{timestamp}] ingest | {filename}\n\nPages written/updated: {pages_list}\n\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    # ------------------------------------------------------------------
    # Query: retrieve relevant wiki pages
    # ------------------------------------------------------------------

    def get_relevant_pages(
        self,
        query: str,
        collection: str = "default",
        top_k: int = 3,
    ) -> list[WikiPage]:
        """Return the most relevant wiki pages for a query.

        Strategy: keyword overlap between query tokens and page content/title,
        then return top_k by score. Fast, no embedding API call needed.
        """
        col_dir = self._collection_dir(collection)
        if not col_dir.exists():
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored: list[tuple[float, Path]] = []

        for page_path in col_dir.glob("*.md"):
            if page_path.name in ("index.md", "log.md"):
                continue
            text = page_path.read_text(encoding="utf-8", errors="replace").lower()
            page_tokens = set(re.findall(r"\w+", text))
            overlap = len(query_tokens & page_tokens)
            if overlap > 0:
                # Weight by title overlap more than body overlap
                title_tokens = set(re.findall(r"\w+", page_path.stem))
                title_bonus = len(query_tokens & title_tokens) * 2
                scored.append((overlap + title_bonus, page_path))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[WikiPage] = []
        for _, page_path in scored[:top_k]:
            content = page_path.read_text(encoding="utf-8", errors="replace")
            # Extract title from first heading line
            title = page_path.stem
            for line in content.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            results.append(
                WikiPage(
                    slug=page_path.stem,
                    title=title,
                    content=content,
                    collection=collection,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def list_pages(self, collection: str = "default") -> list[str]:
        """Return slugs of all wiki pages in a collection (excludes index/log)."""
        col_dir = self._collection_dir(collection)
        if not col_dir.exists():
            return []
        return sorted(
            p.stem for p in col_dir.glob("*.md") if p.name not in ("index.md", "log.md")
        )

    def read_page(self, slug: str, collection: str = "default") -> str | None:
        """Return raw markdown content of a page, or None if it doesn't exist."""
        path = self._page_path(slug, collection)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def read_index(self, collection: str = "default") -> str:
        """Return the index.md content."""
        return self._read_or_empty(self._index_path(collection))

    def read_log(self, collection: str = "default") -> str:
        """Return the log.md content."""
        return self._read_or_empty(self._log_path(collection))

    def lint(self, collection: str = "default") -> str:
        """Ask the LLM to health-check the wiki for issues."""
        col_dir = self._collection_dir(collection)
        if not col_dir.exists():
            return "Wiki is empty — nothing to lint."

        pages = [p for p in col_dir.glob("*.md") if p.name not in ("index.md", "log.md")]
        if not pages:
            return "Wiki is empty — nothing to lint."

        # Feed the LLM a compact view: title + first paragraph per page
        page_summaries = []
        for page_path in sorted(pages):
            text = page_path.read_text(encoding="utf-8", errors="replace")
            first_para = ""
            for line in text.splitlines():
                if line.strip() and not line.startswith("#"):
                    first_para = line.strip()[:200]
                    break
            page_summaries.append(f"**{page_path.stem}**: {first_para}")

        summary_text = "\n".join(page_summaries)
        index_text = self._read_or_empty(self._index_path(collection))[:1000]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a wiki editor performing a health check on a knowledge base. "
                    "Be concise and specific. Only report genuine issues."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Collection: {collection}\n\n"
                    f"Index:\n{index_text}\n\n"
                    f"Page summaries:\n{summary_text}\n\n"
                    "Please identify:\n"
                    "1. Contradictions between pages\n"
                    "2. Orphan pages with no inbound [[links]]\n"
                    "3. Important concepts mentioned but lacking their own page\n"
                    "4. Missing cross-references that should exist\n"
                    "5. Any stale or suspicious claims\n\n"
                    "Format your response as a concise markdown report."
                ),
            },
        ]

        try:
            return llm_chat(messages, max_tokens=1024)
        except Exception as exc:
            return f"Lint failed: {exc}"


# ------------------------------------------------------------------
# Module-level singleton (shared across the app)
# ------------------------------------------------------------------

wiki_manager = WikiManager()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
