import React, { useMemo, useCallback } from 'react';
import ReactFlow, { 
  Node, 
  Edge, 
  Background, 
  Controls,
  MiniMap,
  MarkerType,
  Position,
  NodeChange,
  applyNodeChanges,
  EdgeLabelRenderer,
  BaseEdge,
  getSmoothStepPath,
  EdgeProps
} from 'reactflow';
import 'reactflow/dist/style.css';
import type { FlowInfo, AgentInfo } from '../../generated/models';
import { CpuChipIcon, PlayIcon, FlagIcon, ArrowRightIcon } from '@heroicons/react/24/outline';

interface FlowDiagramProps {
  flow: FlowInfo | null;
  agents: AgentInfo[];
  selectedAgent: AgentInfo | null;
  onAgentSelect: (agent: AgentInfo) => void;
}

// Custom edge with sequence number
const SequenceEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style,
}: EdgeProps) => {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan"
        >
          {data?.sequence && (
            <div className="flex items-center gap-1.5 px-2 py-1 bg-brand text-on-brand rounded-full text-xs font-semibold shadow-1">
              <ArrowRightIcon className="h-3 w-3" />
              <span>{data.sequence}</span>
            </div>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

// Custom node component for agents
const AgentNode = ({ data }: any) => {
  const isSelected = data.isSelected;
  const isStart = data.type === 'start';
  const isEnd = data.type === 'end';
  const sequence = data.sequence;
  
  return (
    <div 
      onClick={data.onClick}
      className={`
        px-5 py-4 rounded-lg border-2 cursor-move transition-all relative
        ${isSelected 
          ? 'border-brand bg-brand/20 shadow-2' 
          : 'border-border bg-surface hover:border-brand/50 hover:shadow-1'
        }
        ${isStart || isEnd ? 'bg-surface-2' : ''}
        min-w-[180px]
      `}
    >
      {/* Sequence badge for agent nodes */}
      {!isStart && !isEnd && sequence && (
        <div className="absolute -top-2 -right-2 w-6 h-6 bg-brand rounded-full flex items-center justify-center text-xs font-bold text-on-brand shadow-1 border-2 border-surface">
          {sequence}
        </div>
      )}
      
      <div className="flex items-center gap-3 mb-2">
        {isStart && (
          <div className="p-1.5 rounded-md bg-green-500/20">
            <PlayIcon className="h-4 w-4 text-green-600" />
          </div>
        )}
        {isEnd && (
          <div className="p-1.5 rounded-md bg-blue-500/20">
            <FlagIcon className="h-4 w-4 text-blue-600" />
          </div>
        )}
        {!isStart && !isEnd && (
          <div className="p-1.5 rounded-md bg-brand/20">
            <CpuChipIcon className="h-4 w-4 text-brand" />
          </div>
        )}
        <div className="flex-1">
          <div className="text-sm font-semibold text-text">
            {data.label}
          </div>
        </div>
      </div>
      
      {data.description && (
        <div className="text-xs text-muted mb-2 line-clamp-2">
          {data.description}
        </div>
      )}
      
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">{data.model || 'Default Model'}</span>
        {data.toolCount > 0 && (
          <span className="px-1.5 py-0.5 rounded bg-brand/10 text-brand">
            {data.toolCount} tools
          </span>
        )}
      </div>
      
      {/* Drag indicator */}
      <div className="absolute bottom-1 right-1 opacity-30 hover:opacity-60 transition-opacity">
        <div className="text-xs text-muted">⋮⋮</div>
      </div>
    </div>
  );
};

const nodeTypes = {
  agent: AgentNode,
};

const edgeTypes = {
  sequence: SequenceEdge,
};

export const FlowDiagram: React.FC<FlowDiagramProps> = ({ 
  flow, 
  agents, 
  selectedAgent,
  onAgentSelect 
}) => {
  // State for nodes (to track positions when dragged)
  const [nodes, setNodes] = React.useState<Node[]>([]);
  
  // Store node positions per flow (persists across flow switches)
  const flowPositionsRef = React.useRef<Record<string, Record<string, { x: number; y: number }>>>({});
  
  // Store onAgentSelect in a ref to avoid triggering layout effect
  const onAgentSelectRef = React.useRef(onAgentSelect);
  React.useEffect(() => {
    onAgentSelectRef.current = onAgentSelect;
  }, [onAgentSelect]);
  
  // Track the last flow to detect actual flow changes
  const lastFlowIdRef = React.useRef<string | null>(null);
  
  // Handle node position changes (drag) and save to flow positions
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => {
        const updatedNodes = applyNodeChanges(changes, nds);
        
        // If this was a position change, save positions for this flow
        const positionChanges = changes.filter(c => c.type === 'position' && c.position);
        if (positionChanges.length > 0 && flow) {
          const newPositions: Record<string, { x: number; y: number }> = {};
          updatedNodes.forEach(node => {
            if (node.position) {
              newPositions[node.id] = { x: node.position.x, y: node.position.y };
            }
          });
          
          // Save to ref (doesn't trigger re-render)
          flowPositionsRef.current = {
            ...flowPositionsRef.current,
            [flow.flow_identifier]: newPositions
          };
        }
        
        return updatedNodes;
      });
    },
    [flow]
  );

  // Build initial nodes layout when flow/agents changes (NOT when selectedAgent changes)
  React.useEffect(() => {
    if (!flow || agents.length === 0) {
      setNodes([]);
      lastFlowIdRef.current = null;
      return;
    }

    // Only rebuild if the flow actually changed
    const flowChanged = lastFlowIdRef.current !== flow.flow_identifier;
    if (!flowChanged && nodes.length > 0) {
      // Flow didn't change, don't rebuild (preserves drag positions)
      return;
    }

    lastFlowIdRef.current = flow.flow_identifier;
    
    const nodeSpacing = 280;
    
    // Get saved positions for this flow (if any)
    const savedPositions = flowPositionsRef.current[flow.flow_identifier] || {};
    
    // Create start node (use saved position if available)
    const startNode: Node = {
      id: 'start',
      type: 'agent',
      position: savedPositions['start'] || { x: 400, y: 50 },
      data: {
        label: 'Start',
        type: 'start',
        isSelected: false,
      },
      sourcePosition: Position.Bottom,
    };

    // Create agent nodes in sequence with sequence numbers (use saved positions if available)
    const agentNodes: Node[] = agents.map((agent, index) => ({
      id: agent.agent_identifier,
      type: 'agent',
      position: savedPositions[agent.agent_identifier] || { 
        x: 200 + (index * nodeSpacing), 
        y: 200 
      },
      data: {
        label: agent.agent_name,
        description: agent.current_provider,
        model: agent.current_model,
        provider: agent.current_provider,
        toolCount: 0, // Tools count not available in AgentInfo
        sequence: index + 1, // Sequence number
        isSelected: false, // Will be updated separately
        onClick: () => onAgentSelectRef.current(agent),
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    }));

    // Create end node (use saved position if available)
    const endNode: Node = {
      id: 'end',
      type: 'agent',
      position: savedPositions['end'] || { 
        x: 200 + (agents.length * nodeSpacing), 
        y: 380 
      },
      data: {
        label: 'Complete',
        type: 'end',
        isSelected: false,
      },
      targetPosition: Position.Top,
    };

    setNodes([startNode, ...agentNodes, endNode]);
  }, [flow, agents]); // flowPositions accessed but not in deps to avoid rebuild loops

  // Update node selection state separately (preserves positions)
  React.useEffect(() => {
    setNodes((currentNodes) =>
      currentNodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          isSelected: 
            selectedAgent?.agent_identifier === node.id,
        },
      }))
    );
  }, [selectedAgent]);

  // Build edges
  const edges = useMemo(() => {
    if (!flow || agents.length === 0) {
      return [];
    }

    // Create edges (connections) with sequence numbers
    const allEdges: Edge[] = [
      // Start to first agent
      {
        id: 'start-to-first',
        source: 'start',
        target: agents[0]?.agent_identifier || 'end',
        type: 'sequence',
        animated: true,
        style: { stroke: 'var(--brand)', strokeWidth: 3 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: 'var(--brand)',
        },
        data: {
          sequence: 'START',
        },
      },
      // Agent to agent connections with sequence numbers
      ...agents.slice(0, -1).map((agent, index) => ({
        id: `${agent.agent_identifier}-to-${agents[index + 1].agent_identifier}`,
        source: agent.agent_identifier,
        target: agents[index + 1].agent_identifier,
        type: 'sequence',
        animated: false,
        style: { stroke: 'var(--brand)', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: 'var(--brand)',
        },
        data: {
          sequence: `${index + 1} → ${index + 2}`,
        },
      })),
      // Last agent to end
      {
        id: 'last-to-end',
        source: agents[agents.length - 1]?.agent_identifier || 'start',
        target: 'end',
        type: 'sequence',
        animated: true,
        style: { stroke: 'var(--ai-success)', strokeWidth: 3 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: 'var(--ai-success)',
        },
        data: {
          sequence: 'DONE',
        },
      },
    ];

    return allEdges;
  }, [agents]);

  if (!flow) {
    return (
      <div className="h-full flex items-center justify-center bg-surface">
        <div className="text-center text-muted">
          <CpuChipIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>Select a flow to visualize</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full bg-surface relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={true}
        fitView
        minZoom={0.5}
        maxZoom={1.5}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="var(--border)" gap={16} />
        <Controls 
          className="!bg-surface !border-border [&_button]:!bg-surface [&_button]:!border-border [&_button]:!text-text"
        />
        <MiniMap 
          nodeColor={(node) => {
            if (node.data.isSelected) return 'var(--brand)';
            if (node.data.type === 'start') return 'var(--ai-success)';
            if (node.data.type === 'end') return 'var(--ai-info)';
            return 'var(--surface-2)';
          }}
          maskColor="rgba(0, 0, 0, 0.2)"
          className="!bg-surface-2 !border-border"
        />
      </ReactFlow>
      
      {/* Flow title overlay */}
      <div className="absolute top-4 left-4 px-4 py-2 bg-surface/90 backdrop-blur-sm border border-border rounded-lg shadow-1">
        <div className="text-xs text-muted">Flow Visualization</div>
        <div className="text-sm font-semibold text-text">{flow.flow_name}</div>
      </div>
    </div>
  );
};

