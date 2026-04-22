import React from 'react';
import { CheckCircle2, XCircle, FileText, Code, Image, Table, FileDown } from 'lucide-react';

const MODALITY_ICONS = {
  text: FileText,
  code: Code,
  image: Image,
  table: Table,
  pdf: FileDown,
};

function scoreColor(score) {
  if (score >= 0.7) return 'var(--color-success)';
  if (score >= 0.5) return 'var(--color-warning)';
  if (score >= 0.3) return '#ff922b';
  return 'var(--color-danger)';
}

export default function ResultCard({ result, showVerdict, verdict }) {
  const Icon = MODALITY_ICONS[result.modality] || FileText;
  const isCode = result.modality === 'code';
  const pct = Math.min(100, Math.round(result.score * 100));

  return (
    <div className="result-card">
      <div className="result-card-header">
        <div className="result-card-meta">
          <span className="modality-badge" data-modality={result.modality}>
            <Icon size={10} />
            {result.modality}
          </span>
          {result.agent && (
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-tertiary)' }}>
              {result.agent}
            </span>
          )}
        </div>
        <div className="score-bar">
          <div className="score-fill">
            <div
              className="score-fill-inner"
              style={{
                width: `${pct}%`,
                background: scoreColor(result.score),
              }}
            />
          </div>
          <span style={{ color: scoreColor(result.score), fontWeight: 600 }}>
            {result.score.toFixed(3)}
          </span>
        </div>
      </div>

      <div className={`result-card-content ${isCode ? 'code' : ''}`}>
        {result.content}
      </div>

      {(result.metadata?.filename || result.metadata?.source) && (
        <div className="result-card-footer">
          <span className="source-tag">
            <FileText size={10} />
            {result.metadata.filename || result.metadata.source}
          </span>
          {result.metadata?.embed_model && (
            <span style={{ opacity: 0.6 }}>{result.metadata.embed_model}</span>
          )}
        </div>
      )}

      {showVerdict && verdict && (
        <div
          className={`verdict-card ${verdict.passed ? 'passed' : 'failed'}`}
          style={{ marginTop: 'var(--space-3)' }}
        >
          <div className="verdict-header">
            <span className={`verdict-status ${verdict.passed ? 'passed' : 'failed'}`}>
              {verdict.passed ? (
                <><CheckCircle2 size={10} /> Passed</>
              ) : (
                <><XCircle size={10} /> Filtered</>
              )}
            </span>
            <span className="verdict-score" style={{ color: scoreColor(verdict.relevance_score) }}>
              {verdict.relevance_score.toFixed(3)}
            </span>
          </div>
          <div className="verdict-reasoning">{verdict.reasoning}</div>
        </div>
      )}
    </div>
  );
}
