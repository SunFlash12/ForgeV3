import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import ForceGraph2D from 'react-force-graph-2d';
import type { ForceGraphMethods, NodeObject, LinkObject } from 'react-force-graph-2d';
import {
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Filter,
  RefreshCw,
  X,
  Database,
  GitBranch,
  Users,
  Loader2,
  ChevronDown,
  ChevronUp,
  Eye,
  Link2,
} from 'lucide-react';
import { api } from '../api/client';
import {
  Card,
  Button,
  Badge,
} from '../components/common';

// Types
interface GraphNode extends NodeObject {
  id: string;
  label: string;
  type: string;
  trust_level: number;
  pagerank_score: number;
  community_id: number;
  created_at: string;
  content_preview?: string;
  // Runtime properties added by force-graph
  x?: number;
  y?: number;
}

interface GraphEdge extends LinkObject {
  id: string;
  source: string | GraphNode;
  target: string | GraphNode;
  relationship_type: string;
  weight: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  communities: Community[];
  metrics: GraphMetrics;
}

interface Community {
  id: number;
  size: number;
  dominant_type: string;
  density: number;
}

interface GraphMetrics {
  total_nodes: number;
  total_edges: number;
  density: number;
  connected_components: number;
}

interface NodeDetails {
  id: string;
  title: string;
  type: string;
  content: string;
  trust_level: number;
  pagerank_score: number;
  community_id: number;
  neighbors: {
    node: GraphNode;
    relationship: string;
    direction: 'in' | 'out';
  }[];
}

// Color schemes
const typeColors: Record<string, string> = {
  KNOWLEDGE: '#3b82f6',   // blue
  DECISION: '#8b5cf6',    // purple
  CONTEXT: '#10b981',     // green
  REFERENCE: '#f59e0b',   // amber
  EXPERIENCE: '#ef4444',  // red
  INSIGHT: '#ec4899',     // pink
  DEFAULT: '#6b7280',     // gray
};

const relationshipColors: Record<string, string> = {
  DERIVED_FROM: '#94a3b8',
  SUPPORTS: '#22c55e',
  CONTRADICTS: '#ef4444',
  RELATED_TO: '#3b82f6',
  ELABORATES: '#a855f7',
  SUPERSEDES: '#f97316',
  REFERENCES: '#06b6d4',
};


export default function GraphExplorerPage() {
  const graphRef = useRef<ForceGraphMethods<GraphNode, GraphEdge> | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Filters
  const [filterType, setFilterType] = useState<string | null>(null);
  const [filterCommunity, setFilterCommunity] = useState<number | null>(null);
  const [minTrust, setMinTrust] = useState(0);
  const [colorBy, setColorBy] = useState<'type' | 'community' | 'trust'>('type');
  const [sizeBy, setSizeBy] = useState<'pagerank' | 'connections' | 'uniform'>('pagerank');

  // Fetch graph data
  const { data: graphData, isLoading, refetch } = useQuery<GraphData>({
    queryKey: ['graph-explorer', filterType, filterCommunity, minTrust],
    queryFn: () => api.get('/graph/explore', {
      type: filterType,
      community: filterCommunity,
      min_trust: minTrust,
    }),
  });

  // Fetch node details when selected
  const { data: nodeDetails } = useQuery<NodeDetails>({
    queryKey: ['graph-node', selectedNode?.id],
    queryFn: () => api.get(`/graph/node/${selectedNode?.id}/neighbors`),
    enabled: !!selectedNode,
  });

  // Handle container resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Node color based on selected mode
  const getNodeColor = useCallback((node: GraphNode) => {
    if (colorBy === 'type') {
      return typeColors[node.type] || typeColors.DEFAULT;
    } else if (colorBy === 'community') {
      const hue = (node.community_id * 137.5) % 360;
      return `hsl(${hue}, 70%, 50%)`;
    } else {
      // Trust level - map to gradient
      const trustColors = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e', '#8b5cf6'];
      const index = Math.min(Math.floor(node.trust_level / 25), 4);
      return trustColors[index];
    }
  }, [colorBy]);

  // Node size based on selected mode
  const getNodeSize = useCallback((node: GraphNode) => {
    if (sizeBy === 'pagerank') {
      return 5 + node.pagerank_score * 20;
    } else if (sizeBy === 'connections') {
      const nodeVal = (node as unknown as { val?: number }).val ?? 0;
      return 5 + Math.log(1 + nodeVal) * 3;
    }
    return 8;
  }, [sizeBy]);

  // Handle node click
  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    setShowDetails(true);

    // Center on node
    graphRef.current?.centerAt(node.x, node.y, 500);
    graphRef.current?.zoom(2, 500);
  }, []);

  // Handle node hover
  const handleNodeHover = useCallback((node: GraphNode | null) => {
    setHoveredNode(node);
    if (containerRef.current) {
      containerRef.current.style.cursor = node ? 'pointer' : 'default';
    }
  }, []);

  // Search and focus on node
  const handleSearch = useCallback(() => {
    if (!searchQuery || !graphData) return;

    const node = graphData.nodes.find(
      n => n.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
           n.id.toLowerCase().includes(searchQuery.toLowerCase())
    );

    if (node) {
      setSelectedNode(node);
      setShowDetails(true);
      graphRef.current?.centerAt(node.x, node.y, 500);
      graphRef.current?.zoom(2, 500);
    }
  }, [searchQuery, graphData]);

  // Zoom controls
  const zoomIn = () => graphRef.current?.zoom(graphRef.current.zoom() * 1.5, 300);
  const zoomOut = () => graphRef.current?.zoom(graphRef.current.zoom() / 1.5, 300);
  const resetView = () => {
    graphRef.current?.zoomToFit(400, 50);
  };

  // Prepare graph data with filtered nodes/edges
  const filteredData = graphData ? {
    nodes: graphData.nodes,
    links: graphData.edges.map(e => ({
      ...e,
      source: typeof e.source === 'string' ? e.source : e.source.id,
      target: typeof e.target === 'string' ? e.target : e.target.id,
    })),
  } : { nodes: [], links: [] };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <GitBranch className="w-6 h-6" />
            Knowledge Graph Explorer
          </h1>

          {/* Search */}
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search nodes..."
              className="pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white w-64 focus:ring-2 focus:ring-blue-500"
            />
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
            <Filter className="w-4 h-4 mr-2" />
            Filters
            {showFilters ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex flex-wrap gap-6">
            {/* Type Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Capsule Type
              </label>
              <select
                value={filterType || ''}
                onChange={(e) => setFilterType(e.target.value || null)}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
              >
                <option value="">All Types</option>
                <option value="KNOWLEDGE">Knowledge</option>
                <option value="DECISION">Decision</option>
                <option value="CONTEXT">Context</option>
                <option value="REFERENCE">Reference</option>
                <option value="EXPERIENCE">Experience</option>
                <option value="INSIGHT">Insight</option>
              </select>
            </div>

            {/* Community Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Community
              </label>
              <select
                value={filterCommunity ?? ''}
                onChange={(e) => setFilterCommunity(e.target.value ? parseInt(e.target.value) : null)}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
              >
                <option value="">All Communities</option>
                {graphData?.communities.map(c => (
                  <option key={c.id} value={c.id}>
                    Community {c.id} ({c.size} nodes)
                  </option>
                ))}
              </select>
            </div>

            {/* Min Trust */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Min Trust: {minTrust}
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={minTrust}
                onChange={(e) => setMinTrust(parseInt(e.target.value))}
                className="w-32"
              />
            </div>

            {/* Color By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Color By
              </label>
              <select
                value={colorBy}
                onChange={(e) => setColorBy(e.target.value as typeof colorBy)}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
              >
                <option value="type">Type</option>
                <option value="community">Community</option>
                <option value="trust">Trust Level</option>
              </select>
            </div>

            {/* Size By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Size By
              </label>
              <select
                value={sizeBy}
                onChange={(e) => setSizeBy(e.target.value as typeof sizeBy)}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-sm"
              >
                <option value="pagerank">PageRank</option>
                <option value="connections">Connections</option>
                <option value="uniform">Uniform</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Graph Canvas */}
        <div ref={containerRef} className="flex-1 relative bg-slate-900">
          <ForceGraph2D
            ref={graphRef}
            graphData={filteredData}
            width={dimensions.width - (showDetails ? 400 : 0)}
            height={dimensions.height}
            nodeLabel={(node: GraphNode) => `${node.label}\nType: ${node.type}\nTrust: ${node.trust_level}`}
            nodeColor={getNodeColor}
            nodeVal={getNodeSize}
            nodeCanvasObject={(node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const size = getNodeSize(node);
              const isSelected = selectedNode?.id === node.id;
              const isHovered = hoveredNode?.id === node.id;

              // Draw node circle
              ctx.beginPath();
              ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
              ctx.fillStyle = getNodeColor(node);
              ctx.fill();

              // Draw border for selected/hovered
              if (isSelected || isHovered) {
                ctx.strokeStyle = isSelected ? '#fff' : '#94a3b8';
                ctx.lineWidth = isSelected ? 3 : 2;
                ctx.stroke();
              }

              // Draw label if zoomed in enough
              if (globalScale > 1.5 || isSelected || isHovered) {
                const label = node.label.slice(0, 20);
                ctx.font = `${12 / globalScale}px Inter, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#fff';
                ctx.fillText(label, node.x!, node.y! + size + 10 / globalScale);
              }
            }}
            linkColor={(link: GraphEdge) => {
              const type = typeof link.relationship_type === 'string' ? link.relationship_type : 'RELATED_TO';
              return relationshipColors[type] || '#4b5563';
            }}
            linkWidth={1}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            backgroundColor="#0f172a"
            cooldownTicks={100}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
          />

          {/* Zoom Controls */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-2">
            <Button size="sm" variant="outline" onClick={zoomIn} className="bg-white dark:bg-gray-800">
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button size="sm" variant="outline" onClick={zoomOut} className="bg-white dark:bg-gray-800">
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button size="sm" variant="outline" onClick={resetView} className="bg-white dark:bg-gray-800">
              <Maximize2 className="w-4 h-4" />
            </Button>
          </div>

          {/* Hover Tooltip */}
          {hoveredNode && (
            <div className="absolute top-4 left-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 pointer-events-none">
              <p className="font-medium text-gray-900 dark:text-white">{hoveredNode.label}</p>
              <p className="text-sm text-gray-500">Type: {hoveredNode.type}</p>
              <p className="text-sm text-gray-500">Trust: {hoveredNode.trust_level}</p>
              <p className="text-sm text-gray-500">PageRank: {hoveredNode.pagerank_score.toFixed(4)}</p>
            </div>
          )}

          {/* Stats Badge */}
          {graphData && (
            <div className="absolute top-4 right-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 text-sm">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1">
                  <Database className="w-4 h-4 text-blue-500" />
                  <span className="text-gray-900 dark:text-white">{graphData.metrics.total_nodes} nodes</span>
                </div>
                <div className="flex items-center gap-1">
                  <Link2 className="w-4 h-4 text-purple-500" />
                  <span className="text-gray-900 dark:text-white">{graphData.metrics.total_edges} edges</span>
                </div>
                <div className="flex items-center gap-1">
                  <Users className="w-4 h-4 text-green-500" />
                  <span className="text-gray-900 dark:text-white">{graphData.communities.length} communities</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Details Panel */}
        {showDetails && selectedNode && (
          <div className="w-96 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-y-auto">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white">Node Details</h3>
              <button
                onClick={() => setShowDetails(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              {/* Basic Info */}
              <div>
                <h4 className="text-lg font-medium text-gray-900 dark:text-white">
                  {selectedNode.label}
                </h4>
                <div className="flex flex-wrap gap-2 mt-2">
                  <Badge className={`bg-opacity-20`} style={{ backgroundColor: typeColors[selectedNode.type] }}>
                    {selectedNode.type}
                  </Badge>
                  <Badge className="bg-gray-100 dark:bg-gray-700">
                    Trust: {selectedNode.trust_level}
                  </Badge>
                  <Badge className="bg-gray-100 dark:bg-gray-700">
                    Community: {selectedNode.community_id}
                  </Badge>
                </div>
              </div>

              {/* Metrics */}
              <Card className="p-3">
                <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Metrics</h5>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500">PageRank</span>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {selectedNode.pagerank_score.toFixed(6)}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500">Created</span>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {new Date(selectedNode.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </Card>

              {/* Content Preview */}
              {selectedNode.content_preview && (
                <Card className="p-3">
                  <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Preview</h5>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {selectedNode.content_preview}
                  </p>
                </Card>
              )}

              {/* Neighbors */}
              {nodeDetails && nodeDetails.neighbors.length > 0 && (
                <Card className="p-3">
                  <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Connections ({nodeDetails.neighbors.length})
                  </h5>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {nodeDetails.neighbors.map((neighbor, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded cursor-pointer"
                        onClick={() => {
                          const node = graphData?.nodes.find(n => n.id === neighbor.node.id);
                          if (node) handleNodeClick(node);
                        }}
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: typeColors[neighbor.node.type] || typeColors.DEFAULT }}
                          />
                          <span className="text-sm text-gray-900 dark:text-white truncate max-w-[150px]">
                            {neighbor.node.label}
                          </span>
                        </div>
                        <Badge
                          className="text-xs"
                          style={{ backgroundColor: relationshipColors[neighbor.relationship] + '20', color: relationshipColors[neighbor.relationship] }}
                        >
                          {neighbor.direction === 'in' ? '<-' : '->'} {neighbor.relationship}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="flex-1">
                  <Eye className="w-4 h-4 mr-1" />
                  View Capsule
                </Button>
                <Button variant="outline" size="sm" className="flex-1">
                  <GitBranch className="w-4 h-4 mr-1" />
                  Show Lineage
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="p-3 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="flex items-center gap-6 text-sm">
          <span className="text-gray-500 dark:text-gray-400">Legend:</span>
          {colorBy === 'type' && Object.entries(typeColors).filter(([k]) => k !== 'DEFAULT').map(([type, color]) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-gray-600 dark:text-gray-300">{type}</span>
            </div>
          ))}
          {colorBy === 'trust' && (
            <>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span className="text-gray-600 dark:text-gray-300">Low Trust</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-gray-600 dark:text-gray-300">Medium</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-gray-600 dark:text-gray-300">High Trust</span>
              </div>
            </>
          )}
          <div className="ml-auto flex items-center gap-4">
            {Object.entries(relationshipColors).slice(0, 4).map(([rel, color]) => (
              <div key={rel} className="flex items-center gap-1">
                <div className="w-4 h-0.5" style={{ backgroundColor: color }} />
                <span className="text-gray-500 dark:text-gray-400 text-xs">{rel}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
