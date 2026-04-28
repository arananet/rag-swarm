# Wiki Schema

This document defines the conventions the LLM follows when creating and
maintaining pages in this wiki. It is the "schema" layer in Karpathy's
three-layer pattern (raw sources → wiki → schema).

---

## Page types

| Type | Slug convention | When to create |
|---|---|---|
| **Entity** | `<name>` (e.g. `swarm-intelligence`) | Any named concept, technique, algorithm, component, or person with ≥2 mentions across sources |
| **Source summary** | `source-<filename>` (e.g. `source-karpathy-wiki`) | One per ingested source — high-level summary, key takeaways |
| **Concept comparison** | `compare-<a>-vs-<b>` | When two entities are repeatedly contrasted in sources |
| **Overview** | `overview` | Auto-maintained high-level synthesis of the whole collection |

---

## Page format

```markdown
# <Title>

<One-sentence definition or description.>

## Key properties / characteristics

- ...

## Relationships

- Related to [[other-page]]
- Contrasted with [[another-page]]

## Notes / open questions

- ...

*Source: filename1.md, filename2.md*
*Last updated: YYYY-MM-DD*
```

---

## Index conventions (`index.md`)

- One row per page: `| [[slug]] | one-line summary |`
- Rebuilt on every ingest
- The LLM reads this first when answering queries

---

## Log conventions (`log.md`)

- Append-only; never edit existing entries
- Each entry starts with `## [YYYY-MM-DD HH:MM UTC] <operation> | <subject>`
- Operations: `ingest`, `query`, `lint`, `update`
- Parseable with: `grep "^## \[" log.md | tail -10`

---

## Cross-reference rules

- Use `[[slug]]` wikilink notation for every internal reference
- Every entity page must have at least one inbound link from another page or the index
- When a new source contradicts an existing claim, note it explicitly:
  > ⚠️ *Contradicts: [[page]] — [brief note]*

---

## What the LLM does on each operation

### Ingest
1. Read source; identify entities and concepts (up to 5)
2. For each: create a new page **or** update/extend an existing one
3. Rebuild `index.md`
4. Append to `log.md`

### Query
1. Read `index.md` to find candidate pages
2. Read full content of the most relevant pages
3. Synthesise an answer with `[[wiki-link]]` citations

### Lint (periodic health-check)
1. Scan all pages for contradictions
2. Find orphan pages (no inbound links)
3. Note important concepts without their own page
4. Suggest new sources to fill knowledge gaps
5. Append a lint entry to `log.md`
