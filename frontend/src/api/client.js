const API = 'http://localhost:8000';

export async function ingestFiles(files, collection = 'default') {
  const form = new FormData();
  for (const f of files) form.append('files', f);
  const res = await fetch(`${API}/ingest?collection=${encodeURIComponent(collection)}`, {
    method: 'POST',
    body: form,
  });
  return res.json();
}

export async function ingestSample(collection = 'default') {
  const res = await fetch(`${API}/ingest-sample?collection=${encodeURIComponent(collection)}`, {
    method: 'POST',
  });
  return res.json();
}

export async function querySwarm(query, collection = 'default', topK = 10, threshold = 0.3) {
  const res = await fetch(`${API}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, collection, top_k: topK, threshold }),
  });
  return res.json();
}

export async function queryTraditional(query, collection = 'default', topK = 10) {
  const res = await fetch(`${API}/query-traditional`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, collection, top_k: topK }),
  });
  return res.json();
}

export async function compare(query, collection = 'default', topK = 10, threshold = 0.3) {
  const res = await fetch(`${API}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, collection, top_k: topK, threshold }),
  });
  return res.json();
}

export async function getCollections() {
  const res = await fetch(`${API}/collections`);
  return res.json();
}
