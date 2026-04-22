import React from 'react';
import { motion } from 'framer-motion';
import { Shield, CheckCircle2, XCircle } from 'lucide-react';

export default function OracleVerdicts({ verdicts }) {
  if (!verdicts?.length) return null;

  const passed = verdicts.filter((v) => v.passed).length;
  const failed = verdicts.length - passed;
  const passRate = Math.round((passed / verdicts.length) * 100);

  return (
    <div>
      {/* Summary Stats */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-card-label">Evaluated</div>
          <div className="metric-val" style={{ color: 'var(--color-text-primary)' }}>
            {verdicts.length}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-card-label">Passed</div>
          <div className="metric-val" style={{ color: 'var(--color-success)' }}>{passed}</div>
        </div>
        <div className="metric-card">
          <div className="metric-card-label">Filtered</div>
          <div className="metric-val" style={{ color: 'var(--color-danger)' }}>{failed}</div>
        </div>
        <div className="metric-card">
          <div className="metric-card-label">Pass Rate</div>
          <div className="metric-val" style={{ color: 'var(--color-accent)' }}>{passRate}%</div>
        </div>
      </div>

      {/* Verdict List */}
      <div style={{ maxHeight: 500, overflowY: 'auto' }}>
        {verdicts.map((v, i) => (
          <motion.div
            key={v.chunk_id}
            className={`verdict-card ${v.passed ? 'passed' : 'failed'}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, delay: i * 0.03 }}
          >
            <div className="verdict-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span className={`verdict-status ${v.passed ? 'passed' : 'failed'}`}>
                  {v.passed ? (
                    <><CheckCircle2 size={10} /> Passed</>
                  ) : (
                    <><XCircle size={10} /> Filtered</>
                  )}
                </span>
                <code
                  style={{
                    fontSize: 'var(--text-xs)',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-text-tertiary)',
                  }}
                >
                  {v.chunk_id}
                </code>
              </div>
              <span className="verdict-score">
                {v.relevance_score.toFixed(4)}
              </span>
            </div>
            <div className="verdict-reasoning">{v.reasoning}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
