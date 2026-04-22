import React, { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Upload, Database, Zap, Shield, BarChart3,
  FileText, Code, Image, Table, FileDown, ChevronRight,
  CheckCircle2, XCircle, Loader2, Layers, ArrowRight,
  Sparkles, Eye,
} from 'lucide-react';
import VectorViz from './components/VectorViz.jsx';
import MetricsComparison from './components/MetricsComparison.jsx';
import ResultCard from './components/ResultCard.jsx';
import OracleVerdicts from './components/OracleVerdicts.jsx';
import { compare, ingestFiles, ingestSample, getCollections } from './api/client.js';

const AGENT_ICONS = {
  TextAgent: FileText,
  CodeAgent: Code,
  ImageAgent: Image,
  TableAgent: Table,
  PDFAgent: FileDown,
};

const AGENT_KEYS = {
  TextAgent: 'text',
  CodeAgent: 'code',
  ImageAgent: 'image',
  TableAgent: 'table',
  PDFAgent: 'pdf',
};

const PIPELINE_STAGES = [
  { key: 'dispatch', label: 'Dispatch', icon: Layers },
  { key: 'search', label: 'Vector Search', icon: Search },
  { key: 'dedup', label: 'Deduplicate', icon: Zap },
  { key: 'rerank', label: 'Re-rank', icon: BarChart3 },
  { key: 'oracle', label: 'Oracle', icon: Shield },
];

export default function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [tab, setTab] = useState('compare');
  const [topK, setTopK] = useState(10);
  const [threshold, setThreshold] = useState(0.3);
  const [collection, setCollection] = useState('default');
  const [collections, setCollections] = useState([]);
  const [status, setStatus] = useState('Ready');
  const [pipelineStage, setPipelineStage] = useState(null);
  const fileRef = useRef(null);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResults(null);

    // Animate pipeline stages
    for (const stage of PIPELINE_STAGES) {
      setPipelineStage(stage.key);
      await new Promise(r => setTimeout(r, 400));
    }

    try {
      const data = await compare(query, collection, topK, threshold);
      setResults(data);
      setPipelineStage('done');
      setStatus(
        `${data.swarm.filtered_count} swarm results from ${data.swarm.total_candidates} candidates`
      );
    } catch (err) {
      setStatus(`Error: ${err.message}`);
      setPipelineStage(null);
    } finally {
      setLoading(false);
    }
  }, [query, collection, topK, threshold]);

  const handleIngestSample = async () => {
    setIngesting(true);
    setStatus('Ingesting sample data...');
    try {
      const data = await ingestSample(collection);
      setStatus(
        `Ingested ${data.documents_processed} files into ${data.chunks_created} chunks`
      );
      refreshCollections();
    } catch (err) {
      setStatus(`Ingest error: ${err.message}`);
    } finally {
      setIngesting(false);
    }
  };

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files?.length) return;
    setIngesting(true);
    setStatus(`Uploading ${files.length} file(s)...`);
    try {
      const data = await ingestFiles(files, collection);
      setStatus(
        `Ingested ${data.documents_processed} files into ${data.chunks_created} chunks`
      );
      refreshCollections();
    } catch (err) {
      setStatus(`Upload error: ${err.message}`);
    } finally {
      setIngesting(false);
    }
  };

  const refreshCollections = async () => {
    try {
      const data = await getCollections();
      setCollections(data);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refreshCollections();
  }, []);

  const swarmResults = results?.swarm?.results || [];
  const tradResults = results?.traditional?.results || [];
  const verdicts = results?.swarm?.oracle_verdicts || [];
  const verdictMap = Object.fromEntries(
    verdicts.map((v) => [v.chunk_id, v])
  );
  const agentsUsed = results?.swarm?.agents_used || [];

  return (
    <div className="app">
      {/* ── Header ──────────────────────────── */}
      <header>
        <div className="header-brand">
          <Sparkles size={20} style={{ color: 'var(--color-accent)' }} />
          <h1>RAG Swarm</h1>
          <span className="header-badge">
            <Zap size={10} /> Cloudflare AI
          </span>
        </div>
        <div className="header-status">
          <div className={`status-dot ${loading ? 'warning' : ''}`} />
          <span>{status}</span>
        </div>
      </header>

      {/* ── Main Content ────────────────────── */}
      <div className="main-content">
        {/* ── Sidebar ─────────────────────── */}
        <div className="sidebar">
          <div className="panel">
            <div className="panel-title">
              <Upload size={16} /> Ingest Documents
            </div>
            <div
              className="upload-zone"
              onClick={() => fileRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) =>
                e.key === 'Enter' && fileRef.current?.click()
              }
            >
              <Upload size={24} />
              <span>Drop files here or click to upload</span>
              <span style={{ fontSize: 'var(--text-xs)' }}>
                Text, PDF, Images, Code
              </span>
              <input
                ref={fileRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileUpload}
                aria-label="Upload files"
              />
            </div>
            <button
              className="btn btn-secondary"
              style={{ width: '100%' }}
              onClick={handleIngestSample}
              disabled={ingesting}
            >
              {ingesting ? (
                <>
                  <Loader2 size={14} className="spinner" /> Ingesting...
                </>
              ) : (
                <>
                  <Database size={14} /> Load Sample Data
                </>
              )}
            </button>
          </div>

          <div className="panel">
            <div className="panel-title">
              <BarChart3 size={16} /> Query Settings
            </div>
            <div className="control-group">
              <label className="control-label">Collection</label>
              <select
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
              >
                <option value="default">default</option>
                {collections.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.count})
                  </option>
                ))}
              </select>
            </div>
            <div className="control-group">
              <label className="control-label">Top K</label>
              <input
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              />
            </div>
            <div className="control-group">
              <label className="control-label">Oracle Threshold</label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              />
            </div>
          </div>

          {/* Active Agents */}
          {agentsUsed.length > 0 && (
            <motion.div
              className="panel"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
            >
              <div className="panel-title">
                <Layers size={16} /> Active Agents
              </div>
              <div className="agent-chips">
                {Object.entries(AGENT_ICONS).map(([name, Icon]) => (
                  <span
                    key={name}
                    className={`agent-chip ${agentsUsed.includes(name) ? 'active' : ''}`}
                    data-agent={AGENT_KEYS[name]}
                  >
                    <span className="chip-dot" />
                    <Icon size={12} />
                    {name.replace('Agent', '')}
                  </span>
                ))}
              </div>
              <div className="stats-row">
                <div className="stat-item">
                  <div className="stat-value">
                    {results?.swarm?.total_candidates ?? 0}
                  </div>
                  <div className="stat-label">Candidates</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">
                    {results?.swarm?.filtered_count ?? 0}
                  </div>
                  <div className="stat-label">Passed Oracle</div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Collections */}
          {collections.length > 0 && (
            <div className="panel">
              <div className="panel-title">
                <Database size={16} /> Collections
              </div>
              {collections.map((c) => (
                <div key={c.name} className="collection-item">
                  <div className="collection-name">{c.name}</div>
                  <div className="collection-meta">
                    {c.count} chunks
                    {c.modalities &&
                      Object.entries(c.modalities).length > 0 &&
                      ` · ${Object.entries(c.modalities).map(([k, v]) => `${k}: ${v}`).join(', ')}`}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Results Area ────────────────── */}
        <div>
          {/* Search Bar */}
          <div className="search-container">
            <div className="search-input-wrapper">
              <Search size={18} />
              <input
                className="search-input"
                placeholder="Ask anything... e.g. 'How does swarm RAG compare to traditional RAG?'"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={loading || !query.trim()}
            >
              {loading ? (
                <Loader2 size={16} className="spinner" />
              ) : (
                <Search size={16} />
              )}
              Compare
            </button>
          </div>

          {/* Pipeline Visualization */}
          {pipelineStage && (
            <motion.div
              className="pipeline-flow"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              {PIPELINE_STAGES.map((stage, i) => {
                const Icon = stage.icon;
                const stageIdx = PIPELINE_STAGES.findIndex(
                  (s) => s.key === pipelineStage
                );
                const isDone =
                  pipelineStage === 'done' ||
                  i < stageIdx;
                const isActive = stage.key === pipelineStage;

                return (
                  <React.Fragment key={stage.key}>
                    {i > 0 && (
                      <ChevronRight
                        size={16}
                        className="pipeline-arrow"
                      />
                    )}
                    <div
                      className={`pipeline-stage ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
                    >
                      <Icon
                        size={20}
                        className="pipeline-stage-icon"
                      />
                      <span className="pipeline-stage-label">
                        {stage.label}
                      </span>
                      {isDone && (
                        <CheckCircle2
                          size={12}
                          style={{ color: 'var(--color-success)' }}
                        />
                      )}
                    </div>
                  </React.Fragment>
                );
              })}
            </motion.div>
          )}

          {/* Loading State */}
          <AnimatePresence>
            {loading && !results && (
              <motion.div
                className="loading-container"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <div className="spinner" />
                <div className="loading-text">
                  Dispatching swarm agents and running multi-stage
                  retrieval...
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Empty State */}
          {!results && !loading && (
            <div className="empty-state">
              <Search size={48} />
              <h3>Search Your Knowledge Base</h3>
              <p>
                Ingest documents and enter a query to compare swarm
                multi-agent retrieval against traditional single-retriever RAG.
              </p>
            </div>
          )}

          {/* Results */}
          {results && !loading && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
            >
              {/* Tabs */}
              <div className="tabs">
                <button
                  className={`tab ${tab === 'compare' ? 'active' : ''}`}
                  onClick={() => setTab('compare')}
                >
                  <BarChart3 size={14} /> Comparison
                </button>
                <button
                  className={`tab ${tab === 'vectors' ? 'active' : ''}`}
                  onClick={() => setTab('vectors')}
                >
                  <Eye size={14} /> Vector Space
                </button>
                <button
                  className={`tab ${tab === 'oracle' ? 'active' : ''}`}
                  onClick={() => setTab('oracle')}
                >
                  <Shield size={14} /> Oracle
                  <span className="tab-count">{verdicts.length}</span>
                </button>
              </div>

              {/* Tab Content */}
              <AnimatePresence mode="wait">
                {tab === 'compare' && (
                  <motion.div
                    key="compare"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <MetricsComparison
                      swarmMetrics={results.swarm_metrics}
                      traditionalMetrics={results.traditional_metrics}
                      improvement={results.improvement}
                    />
                    <div className="results-split">
                      <div>
                        <div className="results-column-header">
                          <span className="approach-badge swarm">
                            Swarm RAG
                          </span>
                          <h3>{swarmResults.length} results</h3>
                        </div>
                        {swarmResults.map((r) => (
                          <ResultCard
                            key={r.chunk_id}
                            result={r}
                            showVerdict
                            verdict={verdictMap[r.chunk_id]}
                          />
                        ))}
                        {!swarmResults.length && (
                          <p
                            style={{
                              color: 'var(--color-text-tertiary)',
                              fontSize: 'var(--text-sm)',
                            }}
                          >
                            No results passed oracle threshold
                          </p>
                        )}
                      </div>
                      <div>
                        <div className="results-column-header">
                          <span className="approach-badge traditional">
                            Traditional RAG
                          </span>
                          <h3>{tradResults.length} results</h3>
                        </div>
                        {tradResults.map((r) => (
                          <ResultCard key={r.chunk_id} result={r} />
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}

                {tab === 'vectors' && (
                  <motion.div
                    key="vectors"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <VectorViz
                      swarmResults={swarmResults}
                      traditionalResults={tradResults}
                      query={query}
                    />
                  </motion.div>
                )}

                {tab === 'oracle' && (
                  <motion.div
                    key="oracle"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <OracleVerdicts verdicts={verdicts} />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}