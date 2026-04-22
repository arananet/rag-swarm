import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Radar,
} from 'recharts';

const ACCENT = '#6366f1';
const ACCENT_LIGHT = '#818cf8';
const MUTED = '#4b5073';
const GRID = '#2a2d3a';
const TEXT = '#9399b2';

export default function MetricsComparison({ swarmMetrics, traditionalMetrics, improvement }) {
  if (!swarmMetrics || !traditionalMetrics) return null;

  const barData = [
    { name: 'Precision', swarm: swarmMetrics.precision, traditional: traditionalMetrics.precision },
    { name: 'Recall', swarm: swarmMetrics.recall, traditional: traditionalMetrics.recall },
    { name: 'NDCG', swarm: swarmMetrics.ndcg, traditional: traditionalMetrics.ndcg },
    { name: 'MRR', swarm: swarmMetrics.mrr, traditional: traditionalMetrics.mrr },
    { name: 'Avg Rel', swarm: swarmMetrics.avg_relevance, traditional: traditionalMetrics.avg_relevance },
  ];

  const radarData = barData.map((d) => ({
    metric: d.name,
    Swarm: d.swarm,
    Traditional: d.traditional,
  }));

  return (
    <div>
      {/* Metric Cards */}
      <div className="metrics-grid">
        {barData.map((d) => {
          const impKey = `${d.name.toLowerCase().replace(/\s+/g, '_')}_pct`;
          const impVal = improvement?.[impKey] ?? null;
          const diff = d.swarm - d.traditional;

          return (
            <div key={d.name} className="metric-card">
              <div className="metric-card-label">{d.name}</div>
              <div className="metric-card-values">
                <span className="metric-val swarm">{d.swarm?.toFixed(2)}</span>
                <span className="metric-val traditional">{d.traditional?.toFixed(2)}</span>
              </div>
              {impVal !== null && (
                <div className={`metric-improvement ${impVal < 0 ? 'negative' : ''}`}>
                  {impVal > 0 ? '+' : ''}{impVal}%
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-5)' }}>
        <div className="panel">
          <div className="panel-title">Bar Comparison</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="name" tick={{ fill: TEXT, fontSize: 11 }} />
              <YAxis domain={[0, 1]} tick={{ fill: TEXT, fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: '#1e2130',
                  border: `1px solid ${GRID}`,
                  borderRadius: 10,
                }}
                labelStyle={{ color: '#f0f1f5', fontWeight: 600 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar
                dataKey="swarm"
                fill={ACCENT}
                name="Swarm RAG"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="traditional"
                fill={MUTED}
                name="Traditional RAG"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <div className="panel-title">Radar Comparison</div>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid stroke={GRID} />
              <PolarAngleAxis dataKey="metric" tick={{ fill: TEXT, fontSize: 10 }} />
              <PolarRadiusAxis domain={[0, 1]} tick={{ fill: TEXT, fontSize: 9 }} />
              <Radar
                name="Swarm"
                dataKey="Swarm"
                stroke={ACCENT}
                fill={ACCENT}
                fillOpacity={0.25}
              />
              <Radar
                name="Traditional"
                dataKey="Traditional"
                stroke={MUTED}
                fill={MUTED}
                fillOpacity={0.15}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
