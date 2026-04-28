"""Wiki layer — persistent LLM-maintained knowledge synthesis.

Implements Karpathy's three-layer pattern:
  Layer 1: Raw sources  → ChromaDB chunks         (existing ingest pipeline)
  Layer 2: Wiki         → wiki/<collection>/*.md  (THIS module)
  Layer 3: Schema       → wiki/SCHEMA.md           (wiki/SCHEMA.md)
"""
