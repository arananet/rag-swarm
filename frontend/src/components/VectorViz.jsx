import React, { useRef, useEffect } from 'react';
import * as d3 from 'd3';

const MODALITY_COLORS = {
  text: '#6366f1',
  code: '#22d3ee',
  image: '#f472b6',
  table: '#facc15',
  pdf: '#fb923c',
};

const GRID_COLOR = '#2a2d3a';
const TEXT_COLOR = '#9399b2';
const ACCENT = '#6366f1';
const MUTED = '#4b5073';

export default function VectorViz({ swarmResults, traditionalResults, query }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth || 600;
    const height = svgRef.current.clientHeight || 400;
    const margin = 40;

    const allPoints = [];

    if (swarmResults?.length) {
      swarmResults.forEach((r) => {
        allPoints.push({
          ...r,
          type: 'swarm',
          x: r.score * 0.8 + Math.random() * 0.15,
          y: 0.3 + Math.random() * 0.4,
        });
      });
    }

    if (traditionalResults?.length) {
      traditionalResults.forEach((r) => {
        allPoints.push({
          ...r,
          type: 'traditional',
          x: r.score * 0.8 + Math.random() * 0.15,
          y: 0.55 + Math.random() * 0.4,
        });
      });
    }

    if (!allPoints.length) {
      svg.append('text')
        .attr('x', width / 2)
        .attr('y', height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', TEXT_COLOR)
        .attr('font-size', '14px')
        .text('Run a query to see vector space visualization');
      return;
    }

    allPoints.push({
      chunk_id: 'query',
      content: query,
      modality: 'query',
      score: 1.0,
      type: 'query',
      x: 0.95,
      y: 0.5,
    });

    const xScale = d3.scaleLinear().domain([0, 1.1]).range([margin, width - margin]);
    const yScale = d3.scaleLinear().domain([0, 1.1]).range([margin, height - margin]);

    // Grid
    svg.append('g')
      .selectAll('line.h')
      .data(d3.range(0, 1.1, 0.2))
      .join('line')
      .attr('x1', margin).attr('x2', width - margin)
      .attr('y1', (d) => yScale(d)).attr('y2', (d) => yScale(d))
      .attr('stroke', GRID_COLOR).attr('stroke-dasharray', '2,4');

    svg.append('g')
      .selectAll('line.v')
      .data(d3.range(0, 1.1, 0.2))
      .join('line')
      .attr('x1', (d) => xScale(d)).attr('x2', (d) => xScale(d))
      .attr('y1', margin).attr('y2', height - margin)
      .attr('stroke', GRID_COLOR).attr('stroke-dasharray', '2,4');

    svg.append('text')
      .attr('x', width / 2).attr('y', height - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', TEXT_COLOR).attr('font-size', '11px')
      .text('Similarity Score →');

    // Lines to query
    const queryPoint = allPoints.find((p) => p.type === 'query');
    allPoints.filter((p) => p.type !== 'query').forEach((p) => {
      svg.append('line')
        .attr('x1', xScale(p.x)).attr('y1', yScale(p.y))
        .attr('x2', xScale(queryPoint.x)).attr('y2', yScale(queryPoint.y))
        .attr('stroke', p.type === 'swarm' ? ACCENT : MUTED)
        .attr('stroke-width', 0.5)
        .attr('stroke-opacity', p.score * 0.4);
    });

    // Tooltip
    const tooltip = d3.select('body').selectAll('.d3-tooltip').data([0]).join('div')
      .attr('class', 'd3-tooltip')
      .style('position', 'absolute')
      .style('background', '#1e2130')
      .style('border', `1px solid ${GRID_COLOR}`)
      .style('border-radius', '10px')
      .style('padding', '8px 12px')
      .style('font-size', '12px')
      .style('color', '#f0f1f5')
      .style('pointer-events', 'none')
      .style('opacity', 0)
      .style('z-index', 1000);

    // Points
    svg.selectAll('circle.point')
      .data(allPoints)
      .join('circle')
      .attr('class', 'point')
      .attr('cx', (d) => xScale(d.x))
      .attr('cy', (d) => yScale(d.y))
      .attr('r', (d) => (d.type === 'query' ? 10 : 6))
      .attr('fill', (d) => {
        if (d.type === 'query') return '#fff';
        return MODALITY_COLORS[d.modality] || ACCENT;
      })
      .attr('stroke', (d) =>
        d.type === 'swarm' ? ACCENT : d.type === 'traditional' ? MUTED : '#fff'
      )
      .attr('stroke-width', (d) => (d.type === 'query' ? 3 : 2))
      .attr('opacity', (d) => (d.type === 'query' ? 1 : 0.8))
      .on('mouseover', (event, d) => {
        tooltip.style('opacity', 1)
          .html(
            `<strong>${d.type === 'query' ? 'Query' : d.modality}</strong><br/>` +
            `Score: ${d.score?.toFixed(3) || 'N/A'}<br/>` +
            `${d.content?.substring(0, 100) || ''}...`
          );
      })
      .on('mousemove', (event) => {
        tooltip.style('left', event.pageX + 12 + 'px')
          .style('top', event.pageY - 10 + 'px');
      })
      .on('mouseout', () => tooltip.style('opacity', 0));

    // Legends
    const legend = svg.append('g').attr('transform', `translate(${margin + 10}, ${margin + 10})`);
    [
      { label: 'Swarm results', color: ACCENT },
      { label: 'Traditional results', color: MUTED },
      { label: 'Query', color: '#fff' },
    ].forEach((item, i) => {
      legend.append('circle').attr('cx', 0).attr('cy', i * 18).attr('r', 5).attr('fill', item.color);
      legend.append('text')
        .attr('x', 12).attr('y', i * 18 + 4)
        .attr('fill', TEXT_COLOR).attr('font-size', '10px')
        .text(item.label);
    });

    const modLegend = svg.append('g')
      .attr('transform', `translate(${width - margin - 100}, ${margin + 10})`);
    Object.entries(MODALITY_COLORS).forEach(([mod, color], i) => {
      modLegend.append('rect')
        .attr('x', 0).attr('y', i * 16)
        .attr('width', 10).attr('height', 10)
        .attr('rx', 2).attr('fill', color);
      modLegend.append('text')
        .attr('x', 16).attr('y', i * 16 + 9)
        .attr('fill', TEXT_COLOR).attr('font-size', '10px')
        .text(mod);
    });
  }, [swarmResults, traditionalResults, query]);

  return (
    <div className="vector-viz-container">
      <svg ref={svgRef} />
    </div>
  );
}
