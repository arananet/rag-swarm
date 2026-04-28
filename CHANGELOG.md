# Changelog

All notable changes to `rag-swarm` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
Guidelines:
- Add a new entry under `## [Unreleased]` as you work — no batching up for release day.
- Group entries under: Added, Changed, Deprecated, Removed, Fixed, Security.
- Reference the spec slug and PR number:  "Added dark mode (spec: dark-mode, #42)".
- On release, rename `[Unreleased]` to the new version with the release date,
  and open a fresh `[Unreleased]` section at the top.
- The release-drafter workflow auto-populates draft release notes from PRs —
  keep PR titles tidy so they flow straight into here.
-->

## [Unreleased]

### Added
- **Karpathy three-layer wiki architecture** — `WikiManager` (`backend/app/wiki/manager.py`) synthesises every ingested source into interlinked markdown pages stored in `backend/wiki/<collection>/`. Knowledge accumulates across ingestions instead of being re-derived per query.
- **Persistent wiki endpoints** — `GET /wiki/{collection}/pages`, `GET /wiki/{collection}/pages/{slug}`, `GET /wiki/{collection}/index`, `GET /wiki/{collection}/log`, `POST /wiki/{collection}/lint`.
- **`wiki_pages` field in query responses** — `/query` now returns pre-synthesised wiki pages alongside raw chunk results; wiki pages are served first (layer 2), raw results second.
- **`wiki_pages_written` field in ingest responses** — `/ingest` and `/ingest-sample` report which wiki page slugs were created or updated.
- **Schema layer** — `backend/wiki/SCHEMA.md` documents page types (Entity, Source summary, Concept comparison, Overview), cross-reference conventions, and operation descriptions (Ingest, Query, Lint).
- **Wiki lint** — `POST /wiki/{collection}/lint` calls the LLM to health-check the wiki for contradictions, orphan pages, and stale claims.
- **`WikiPage`, `WikiIngestResult`, `WikiLintResult` Pydantic models** added to `backend/app/models/schemas.py`.

### Changed
- `IngestResponse` schema extended with `wiki_pages_written: list[str]`.
- `SwarmQueryResponse` schema extended with `wiki_pages: list[WikiPage]`.
- README architecture diagram and "How It Works" section updated to reflect all three Karpathy layers.

---

## [0.1.0] — YYYY-MM-DD

### Added
- Initial release.

[Unreleased]: https://github.com/arananet/rag-swarm/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/arananet/rag-swarm/releases/tag/v0.1.0
