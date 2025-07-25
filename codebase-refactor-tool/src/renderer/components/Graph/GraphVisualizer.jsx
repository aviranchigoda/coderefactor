import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { useGraph } from '../../hooks/useGraph';
import GraphControls from './GraphControls';
import NodeDetails from './NodeDetails';
import './GraphVisualizer.css';

const GraphVisualizer = () => {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [transform, setTransform] = useState(d3.zoomIdentity);
  const [simulation, setSimulation] = useState(null);
  const [filters, setFilters] = useState({
    nodeTypes: ['File', 'Class', 'Method', 'Function', 'LintError'],
    showErrors: true,
    showCalls: true,
    searchTerm: ''
  });

  const { graphData, loading, error, refreshGraph } = useGraph();

  // Node colors by type
  const nodeColors = {
    File: '#3182ce',
    Class: '#38a169', 
    Method: '#d69e2e',
    Function: '#e53e3e',
    LintError: '#9f1239'
  };

  // Node sizes by type
  const nodeSizes = {
    File: 12,
    Class: 10,
    Method: 8,
    Function: 8,
    LintError: 6
  };

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setDimensions({ width, height });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Filter graph data based on current filters
  const filteredData = useCallback(() => {
    if (!graphData) return { nodes: [], links: [] };

    let nodes = graphData.nodes.filter(node => {
      // Filter by node type
      if (!filters.nodeTypes.includes(node.type)) return false;
      
      // Filter by search term
      if (filters.searchTerm) {
        const searchLower = filters.searchTerm.toLowerCase();
        const nodeName = (node.properties?.name || '').toLowerCase();
        const nodePath = (node.properties?.path || '').toLowerCase();
        if (!nodeName.includes(searchLower) && !nodePath.includes(searchLower)) {
          return false;
        }
      }

      // Filter errors
      if (!filters.showErrors && node.type === 'LintError') return false;

      return true;
    });

    const nodeIds = new Set(nodes.map(n => n.id));

    let links = graphData.links.filter(link => {
      // Only include links between visible nodes
      if (!nodeIds.has(link.source.id || link.source) || 
          !nodeIds.has(link.target.id || link.target)) {
        return false;
      }

      // Filter call relationships
      if (!filters.showCalls && link.type === 'CALLS') return false;

      return true;
    });

    return { nodes, links };
  }, [graphData, filters]);

  // Initialize D3 force simulation
  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const { nodes, links } = filteredData();

    // Clear previous content
    svg.selectAll('*').remove();

    // Create container groups
    const g = svg.append('g').attr('class', 'graph-container');

    // Add zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        setTransform(event.transform);
      });

    svg.call(zoom);

    // Create force simulation
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links)
        .id(d => d.id)
        .distance(d => {
          // Vary link distance by relationship type
          if (d.type === 'CONTAINS') return 50;
          if (d.type === 'HAS_METHOD') return 40;
          if (d.type === 'CALLS') return 100;
          return 60;
        })
      )
      .force('charge', d3.forceManyBody()
        .strength(d => {
          // Stronger repulsion for larger nodes
          if (d.type === 'File') return -300;
          if (d.type === 'Class') return -200;
          return -100;
        })
      )
      .force('center', d3.forceCenter(dimensions.width / 2, dimensions.height / 2))
      .force('collision', d3.forceCollide()
        .radius(d => nodeSizes[d.type] * 1.5)
      );

    // Create link elements
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('class', d => `link link-${d.type}`)
      .attr('stroke', d => {
        if (d.type === 'CALLS') return '#e53e3e';
        if (d.type === 'HAS_ERROR') return '#dc2626';
        return '#94a3b8';
      })
      .attr('stroke-width', d => d.type === 'CALLS' ? 2 : 1)
      .attr('stroke-opacity', 0.6);

    // Create node group
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .enter().append('g')
      .attr('class', 'node')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
      );

    // Add circles for nodes
    node.append('circle')
      .attr('r', d => nodeSizes[d.type] || 8)
      .attr('fill', d => nodeColors[d.type] || '#718096')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedNode(d);
      })
      .on('mouseover', (event, d) => {
        setHoveredNode(d);
        // Highlight connected nodes
        highlightConnected(d);
      })
      .on('mouseout', () => {
        setHoveredNode(null);
        removeHighlight();
      });

    // Add labels
    node.append('text')
      .attr('dx', 12)
      .attr('dy', 4)
      .text(d => d.properties?.name || d.id)
      .attr('font-size', '12px')
      .attr('fill', '#1f2937');

    // Add icons for node types
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .attr('font-family', 'monospace')
      .attr('font-size', '10px')
      .attr('fill', '#fff')
      .text(d => {
        if (d.type === 'File') return 'F';
        if (d.type === 'Class') return 'C';
        if (d.type === 'Method') return 'M';
        if (d.type === 'Function') return 'f';
        if (d.type === 'LintError') return '!';
        return '';
      });

    // Update positions on simulation tick
    sim.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Drag functions
    function dragstarted(event, d) {
      if (!event.active) sim.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) sim.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    // Highlight connected nodes
    function highlightConnected(node) {
      const connectedNodeIds = new Set();
      
      links.forEach(link => {
        const sourceId = link.source.id || link.source;
        const targetId = link.target.id || link.target;
        
        if (sourceId === node.id) connectedNodeIds.add(targetId);
        if (targetId === node.id) connectedNodeIds.add(sourceId);
      });

      // Dim non-connected nodes
      g.selectAll('.node')
        .style('opacity', d => {
          if (d.id === node.id || connectedNodeIds.has(d.id)) return 1;
          return 0.3;
        });

      // Highlight connected links
      g.selectAll('.link')
        .style('opacity', d => {
          const sourceId = d.source.id || d.source;
          const targetId = d.target.id || d.target;
          if (sourceId === node.id || targetId === node.id) return 1;
          return 0.1;
        })
        .style('stroke-width', d => {
          const sourceId = d.source.id || d.source;
          const targetId = d.target.id || d.target;
          if (sourceId === node.id || targetId === node.id) return 3;
          return 1;
        });
    }

    function removeHighlight() {
      g.selectAll('.node').style('opacity', 1);
      g.selectAll('.link')
        .style('opacity', 0.6)
        .style('stroke-width', d => d.type === 'CALLS' ? 2 : 1);
    }

    setSimulation(sim);

    // Cleanup
    return () => {
      sim.stop();
    };
  }, [graphData, dimensions, filteredData]);

  // Handle node selection from external sources
  const focusOnNode = useCallback((nodeId) => {
    if (!simulation || !svgRef.current) return;

    const node = simulation.nodes().find(n => n.id === nodeId);
    if (!node) return;

    const svg = d3.select(svgRef.current);
    const g = svg.select('.graph-container');

    // Calculate transform to center the node
    const scale = 1.5;
    const x = dimensions.width / 2 - node.x * scale;
    const y = dimensions.height / 2 - node.y * scale;

    const transform = d3.zoomIdentity
      .translate(x, y)
      .scale(scale);

    svg.transition()
      .duration(750)
      .call(d3.zoom().transform, transform);

    setSelectedNode(node);
  }, [simulation, dimensions]);

  // Export graph as image
  const exportGraph = useCallback((format = 'png') => {
    if (!svgRef.current) return;

    const svg = svgRef.current;
    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svg);

    if (format === 'svg') {
      const blob = new Blob([svgStr], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'codebase-graph.svg';
      link.click();
      URL.revokeObjectURL(url);
    } else if (format === 'png') {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();

      img.onload = () => {
        canvas.width = dimensions.width;
        canvas.height = dimensions.height;
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);

        canvas.toBlob((blob) => {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = 'codebase-graph.png';
          link.click();
          URL.revokeObjectURL(url);
        });
      };

      img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgStr)));
    }
  }, [dimensions]);

  if (loading) {
    return (
      <div className="graph-visualizer-loading">
        <div className="spinner"></div>
        <p>Loading graph data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="graph-visualizer-error">
        <p>Error loading graph: {error}</p>
        <button onClick={refreshGraph}>Retry</button>
      </div>
    );
  }

  return (
    <div className="graph-visualizer" ref={containerRef}>
      <GraphControls 
        filters={filters}
        setFilters={setFilters}
        onExport={exportGraph}
        onRefresh={refreshGraph}
        transform={transform}
      />
      
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="graph-svg"
      />

      {hoveredNode && (
        <div className="node-tooltip" style={{
          left: hoveredNode.x + 20,
          top: hoveredNode.y - 10
        }}>
          <strong>{hoveredNode.type}</strong>
          <br />
          {hoveredNode.properties?.name || hoveredNode.id}
          {hoveredNode.properties?.path && (
            <>
              <br />
              <small>{hoveredNode.properties.path}</small>
            </>
          )}
        </div>
      )}

      {selectedNode && (
        <NodeDetails 
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onFocus={focusOnNode}
        />
      )}
    </div>
  );
};

export default GraphVisualizer;