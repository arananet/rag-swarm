"""Multimodal ingestion pipeline — chunking, VLM captioning, and embedding via Cloudflare Workers AI."""

from __future__ import annotations

import base64
import io
import os
import re
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader

from app.embeddings import caption_image, chunk_id, embed_texts
from app.models.schemas import DocumentChunk, Modality
from app.provenance import ProvenanceTracker
from app.vectorstore import add_documents

# ---------- Chunking strategies per modality ----------

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count, respecting sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > chunk_size and current:
            chunks.append(current.strip())
            # Keep overlap
            words = current.split()
            overlap_text = " ".join(words[-overlap // 5 :]) if len(words) > overlap // 5 else ""
            current = overlap_text + " " + sentence
        else:
            current = (current + " " + sentence).strip()
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:chunk_size]]


def _extract_tables_from_text(text: str) -> list[str]:
    """Extract markdown/CSV table blocks from text."""
    table_pattern = re.compile(
        r"(\|.+\|[\r\n]+\|[-| :]+\|[\r\n]+(?:\|.+\|[\r\n]*)+)",
        re.MULTILINE,
    )
    return table_pattern.findall(text)


def _chunk_code(code: str) -> list[str]:
    """Split code into function/class-level chunks, falling back to line-based."""
    # Try to split by function/class definitions
    pattern = re.compile(
        r"^((?:def |class |function |async function |export |public |private ).+)",
        re.MULTILINE,
    )
    splits = pattern.split(code)
    chunks: list[str] = []
    current = ""
    for part in splits:
        if len(current) + len(part) > CHUNK_SIZE * 2 and current:
            chunks.append(current.strip())
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())
    # If no meaningful splits, fall back to line-based chunking
    if len(chunks) <= 1 and len(code) > CHUNK_SIZE:
        return _chunk_text(code, chunk_size=CHUNK_SIZE * 2, overlap=CHUNK_OVERLAP * 2)
    return chunks if chunks else [code]


# ---------- Processors per file type ----------


def process_text_file(filepath: Path, source_name: str) -> list[DocumentChunk]:
    """Process .txt / .md files into text chunks."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    chunks: list[DocumentChunk] = []

    # Extract tables as separate TABLE modality chunks
    tables = _extract_tables_from_text(text)
    for i, table in enumerate(tables):
        cid = chunk_id(table, "table", i)
        chunks.append(
            DocumentChunk(
                id=cid,
                content=table,
                modality=Modality.TABLE,
                metadata={
                    "source": source_name,
                    "filename": filepath.name,
                    "table_index": i,
                },
            )
        )

    # Remove tables from text for clean text chunking
    clean_text = text
    for table in tables:
        clean_text = clean_text.replace(table, "")

    for i, chunk_text in enumerate(_chunk_text(clean_text)):
        cid = chunk_id(chunk_text, "text", i)
        chunks.append(
            DocumentChunk(
                id=cid,
                content=chunk_text,
                modality=Modality.TEXT,
                metadata={
                    "source": source_name,
                    "filename": filepath.name,
                    "chunk_index": i,
                },
            )
        )
    return chunks


def process_pdf_file(filepath: Path, source_name: str) -> list[DocumentChunk]:
    """Process PDF files — extract text per page, then chunk."""
    reader = PdfReader(str(filepath))
    chunks: list[DocumentChunk] = []
    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue
        # Extract tables from PDF page text
        tables = _extract_tables_from_text(page_text)
        for i, table in enumerate(tables):
            cid = chunk_id(table, "table", page_num * 100 + i)
            chunks.append(
                DocumentChunk(
                    id=cid,
                    content=table,
                    modality=Modality.TABLE,
                    metadata={
                        "source": source_name,
                        "filename": filepath.name,
                        "page": page_num + 1,
                        "table_index": i,
                    },
                )
            )
            page_text = page_text.replace(table, "")

        for i, chunk_text in enumerate(_chunk_text(page_text)):
            cid = chunk_id(chunk_text, "pdf", page_num * 1000 + i)
            chunks.append(
                DocumentChunk(
                    id=cid,
                    content=chunk_text,
                    modality=Modality.PDF,
                    metadata={
                        "source": source_name,
                        "filename": filepath.name,
                        "page": page_num + 1,
                        "chunk_index": i,
                    },
                )
            )
    return chunks


def process_image_file(filepath: Path, source_name: str) -> list[DocumentChunk]:
    """Process image files — use Cloudflare VLM for captioning, fallback to sidecar/metadata."""
    img = Image.open(filepath).convert("RGB")
    width, height = img.size

    description = ""

    # Priority 1: Sidecar .txt file with human description
    sidecar = filepath.with_suffix(".txt")
    if sidecar.exists():
        description = sidecar.read_text(encoding="utf-8", errors="replace").strip()

    # Priority 2: VLM caption via Cloudflare Workers AI
    if not description:
        try:
            # Resize for VLM (max 1024px on longest side to keep payload small)
            max_side = 1024
            if max(width, height) > max_side:
                ratio = max_side / max(width, height)
                img = img.resize(
                    (int(width * ratio), int(height * ratio)),
                    Image.LANCZOS,
                )

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            description = caption_image(image_b64)
        except Exception:
            pass

    # Priority 3: Basic metadata fallback
    if not description:
        description = (
            f"Image: {filepath.name}, dimensions: {width}x{height}, "
            f"format: {img.format or filepath.suffix}, source: {source_name}"
        )

    cid = chunk_id(description, "image", 0)
    return [
        DocumentChunk(
            id=cid,
            content=description,
            modality=Modality.IMAGE,
            metadata={
                "source": source_name,
                "filename": filepath.name,
                "width": width,
                "height": height,
                "has_sidecar": sidecar.exists(),
                "vlm_captioned": not sidecar.exists() and "Image:" not in description,
            },
        )
    ]


def process_code_file(filepath: Path, source_name: str) -> list[DocumentChunk]:
    """Process code files (.py, .js, .ts, .java, .go, etc.)."""
    code = filepath.read_text(encoding="utf-8", errors="replace")
    chunks: list[DocumentChunk] = []
    for i, chunk_text in enumerate(_chunk_code(code)):
        cid = chunk_id(chunk_text, "code", i)
        chunks.append(
            DocumentChunk(
                id=cid,
                content=chunk_text,
                modality=Modality.CODE,
                metadata={
                    "source": source_name,
                    "filename": filepath.name,
                    "language": filepath.suffix.lstrip("."),
                    "chunk_index": i,
                },
            )
        )
    return chunks


# ---------- Extension → processor mapping ----------

EXTENSION_MAP: dict[str, callable] = {
    ".txt": process_text_file,
    ".md": process_text_file,
    ".markdown": process_text_file,
    ".rst": process_text_file,
    ".pdf": process_pdf_file,
    ".png": process_image_file,
    ".jpg": process_image_file,
    ".jpeg": process_image_file,
    ".gif": process_image_file,
    ".webp": process_image_file,
    ".bmp": process_image_file,
    ".py": process_code_file,
    ".js": process_code_file,
    ".ts": process_code_file,
    ".java": process_code_file,
    ".go": process_code_file,
    ".rs": process_code_file,
    ".cpp": process_code_file,
    ".c": process_code_file,
    ".rb": process_code_file,
    ".swift": process_code_file,
    ".kt": process_code_file,
    ".cs": process_code_file,
    ".css": process_code_file,
    ".html": process_code_file,
    ".sql": process_code_file,
    ".sh": process_code_file,
    ".yaml": process_text_file,
    ".yml": process_text_file,
    ".json": process_code_file,
    ".csv": process_text_file,
}


def ingest_file(filepath: Path, collection: str = "default") -> list[DocumentChunk]:
    """Ingest a single file into the vector store with provenance tracking."""
    ext = filepath.suffix.lower()
    processor = EXTENSION_MAP.get(ext)
    if processor is None:
        processor = process_text_file

    source_name = filepath.name
    chunks = processor(filepath, source_name)

    if not chunks:
        return []

    # Provenance tracking
    tracker = ProvenanceTracker()
    source_bytes = filepath.read_bytes()
    total = len(chunks)

    # Embed all chunks (text-based for cross-modal search)
    contents = [c.content for c in chunks]
    embeddings = embed_texts(contents)

    # Enrich metadata with provenance records
    metadatas = []
    for i, chunk in enumerate(chunks):
        prov = tracker.create_record(
            chunk_id=chunk.id,
            source_file=source_name,
            source_content=source_bytes,
            chunk_content=chunk.content,
            modality=chunk.modality.value,
            chunk_index=i,
            total_chunks=total,
        )
        meta = {**chunk.metadata, "modality": chunk.modality.value}
        meta.update(tracker.to_metadata(prov))
        metadatas.append(meta)

    # Store in ChromaDB
    add_documents(
        collection_name=collection,
        ids=[c.id for c in chunks],
        documents=contents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    return chunks


def ingest_directory(dirpath: Path, collection: str = "default") -> tuple[int, int, set[str]]:
    """Ingest all supported files in a directory. Returns (files_processed, chunks_created, modalities)."""
    files_processed = 0
    total_chunks = 0
    modalities: set[str] = set()

    for filepath in sorted(dirpath.rglob("*")):
        if filepath.is_file() and filepath.suffix.lower() in EXTENSION_MAP:
            chunks = ingest_file(filepath, collection)
            if chunks:
                files_processed += 1
                total_chunks += len(chunks)
                modalities.update(c.modality.value for c in chunks)

    return files_processed, total_chunks, modalities
