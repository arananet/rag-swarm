import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BookOpen, ChevronDown, ChevronRight, BookMarked, ExternalLink } from 'lucide-react';

function renderWikiContent(content) {
  // Convert [[slug]] cross-references to styled spans and basic markdown headings
  return content
    .split('\n')
    .map((line, i) => {
      // H1
      if (line.startsWith('# ')) {
        return <h3 key={i} className="wiki-page-h1">{line.slice(2)}</h3>;
      }
      // H2
      if (line.startsWith('## ')) {
        return <h4 key={i} className="wiki-page-h2">{line.slice(3)}</h4>;
      }
      // H3
      if (line.startsWith('### ')) {
        return <h5 key={i} className="wiki-page-h3">{line.slice(4)}</h5>;
      }
      // Empty line → spacer
      if (line.trim() === '') {
        return <div key={i} className="wiki-line-break" />;
      }
      // Inline [[links]] and *italic*
      const parts = line.split(/(\[\[[\w-]+\]\]|\*[^*]+\*)/g);
      return (
        <p key={i} className="wiki-page-para">
          {parts.map((part, j) => {
            if (/^\[\[[\w-]+\]\]$/.test(part)) {
              const slug = part.slice(2, -2);
              return (
                <span key={j} className="wiki-crossref">
                  <ExternalLink size={10} />
                  {slug}
                </span>
              );
            }
            if (/^\*[^*]+\*$/.test(part)) {
              return <em key={j}>{part.slice(1, -1)}</em>;
            }
            return part;
          })}
        </p>
      );
    });
}

function WikiPageCard({ page }) {
  const [open, setOpen] = useState(false);

  return (
    <motion.div
      className="wiki-card"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <button
        className="wiki-card-header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className="wiki-card-title">
          <BookMarked size={14} className="wiki-card-icon" />
          <span>{page.title || page.slug}</span>
          <span className="wiki-slug-badge">{page.slug}</span>
        </div>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="wiki-card-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="wiki-content">
              {renderWikiContent(page.content)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function WikiPanel({ wikiPages }) {
  if (!wikiPages || wikiPages.length === 0) {
    return (
      <div className="wiki-empty">
        <BookOpen size={32} />
        <p>No wiki pages matched this query.</p>
        <span>Ingest more documents to build the persistent wiki.</span>
      </div>
    );
  }

  return (
    <div className="wiki-panel">
      <div className="wiki-panel-header">
        <BookOpen size={16} />
        <span>Persistent Wiki — Karpathy layer 2</span>
        <span className="wiki-page-count">{wikiPages.length} page{wikiPages.length !== 1 ? 's' : ''} matched</span>
      </div>
      <p className="wiki-panel-desc">
        Pre-synthesised knowledge compiled from all prior ingestions. Cross-references and
        accumulated context are already in these pages — no re-derivation per query.
      </p>
      <div className="wiki-cards">
        {wikiPages.map((page) => (
          <WikiPageCard key={page.slug} page={page} />
        ))}
      </div>
    </div>
  );
}
