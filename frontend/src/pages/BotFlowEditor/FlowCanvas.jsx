import { useState, useCallback, useMemo, useRef } from 'react'
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  useReactFlow,
  addEdge,
  Background,
  Controls,
  MiniMap,
  Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { StartNode, StepNode, ButtonsNode, ActionNode, InstructionsNode, DoneNode } from './FlowNodes'
import SidePanel from './SidePanel'
import { flowToScript } from './flowUtils'

// Must render inside ReactFlow context to access fitView
function FitViewPanel({ onRecenter }) {
  const { fitView } = useReactFlow()
  function handleClick() {
    onRecenter()
    setTimeout(() => fitView({ padding: 0.3, duration: 400 }), 50)
  }
  return (
    <Panel position="top-left">
      <button className="fc-fitview-btn" onClick={handleClick}>
        ⬛ הצג הכל
      </button>
    </Panel>
  )
}

const nodeTypes = {
  startNode: StartNode,
  stepNode: StepNode,
  buttonsNode: ButtonsNode,
  actionNode: ActionNode,
  instructionsNode: InstructionsNode,
  doneNode: DoneNode,
}

export default function FlowCanvas({ initialNodes, initialEdges, scriptId, originalScript, onSave, onBack }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [pushMode, setPushMode] = useState(false)
  const dragStartY = useRef(null)

  // Connect two nodes by dragging
  const onConnect = useCallback(
    (params) => setEdges(eds => addEdge({ ...params, type: 'smoothstep' }, eds)),
    []
  )

  // Select node for editing
  function onNodeClick(_, node) {
    setSelectedNode(node)
  }

  function onPaneClick() {
    setSelectedNode(null)
  }

  // Update node data from side panel
  function updateNodeData(id, newData) {
    setNodes(nds => nds.map(n => n.id === id ? { ...n, data: newData } : n))
    setSelectedNode(prev => prev?.id === id ? { ...prev, data: newData } : prev)
  }

  // Edit script name directly from toolbar (synced to Start Node data)
  function handleNameChange(value) {
    setNodes(nds => nds.map(n =>
      n.id === '__start__' ? { ...n, data: { ...n.data, name: value } } : n
    ))
  }
  const scriptName = nodes.find(n => n.id === '__start__')?.data?.name || ''

  // Push-down drag handlers
  function onNodeDragStart(_, node) {
    dragStartY.current = { x: node.position.x, y: node.position.y }
  }

  function onNodeDragStop(_, node) {
    if (!pushMode || dragStartY.current === null) return
    const deltaX = node.position.x - dragStartY.current.x
    const deltaY = node.position.y - dragStartY.current.y
    dragStartY.current = null
    if (deltaX === 0 && deltaY === 0) return
    setNodes(nds => nds.map(n => {
      if (n.id === node.id) return n
      const belowOrRight =
        (deltaY > 0 && n.position.y > node.position.y - deltaY) ||
        (deltaX > 0 && n.position.x > node.position.x - deltaX)
      if (!belowOrRight) return n
      return {
        ...n,
        position: {
          x: deltaX !== 0 ? n.position.x + deltaX : n.position.x,
          y: deltaY !== 0 ? n.position.y + deltaY : n.position.y,
        },
      }
    }))
  }

  // Calculate position for new node — near existing nodes, not at origin
  function newNodePos(nds) {
    if (nds.length === 0) return { x: 400, y: 250 }
    const xs = nds.map(n => n.position.x)
    const ys = nds.map(n => n.position.y)
    const centerX = (Math.min(...xs) + Math.max(...xs)) / 2
    const bottomY = Math.max(...ys)
    return { x: centerX, y: bottomY + 220 }
  }

  // Move all nodes so the top-left corner starts at (100, 100)
  function recenterNodes() {
    setNodes(nds => {
      if (nds.length === 0) return nds
      const minX = Math.min(...nds.map(n => n.position.x))
      const minY = Math.min(...nds.map(n => n.position.y))
      return nds.map(n => ({
        ...n,
        position: { x: n.position.x - minX + 100, y: n.position.y - minY + 100 },
      }))
    })
  }

  // Delete nodes that have no edges at all (except the start node)
  function deleteOrphans() {
    const connectedIds = new Set(edges.flatMap(e => [e.source, e.target]))
    setNodes(nds => nds.filter(n => n.type === 'startNode' || n.id === '__start__' || connectedIds.has(n.id)))
    setSelectedNode(null)
  }

  // Delete a node + its edges
  function deleteNode(id) {
    setNodes(nds => nds.filter(n => n.id !== id))
    setEdges(eds => eds.filter(e => e.source !== id && e.target !== id))
    setSelectedNode(null)
  }

  // Add new step node
  function addStepNode() {
    const id = `STEP_${Date.now()}`
    setNodes(nds => [...nds, {
      id,
      type: 'stepNode',
      position: newNodePos(nds),
      data: { id, type: 'text_input', text: '', save_to: '' },
    }])
  }

  // Add new buttons node
  function addButtonsNode() {
    const id = `STEP_${Date.now()}`
    setNodes(nds => [...nds, {
      id,
      type: 'buttonsNode',
      position: newNodePos(nds),
      data: {
        id,
        type: 'buttons',
        text: '',
        buttons: [
          { id: 'btn_1', title: '', next_step: '' },
          { id: 'btn_2', title: '', next_step: '' },
        ],
      },
    }])
  }

  // Add new instructions node
  function addInstructionsNode() {
    const id = `INSTR_${Date.now()}`
    setNodes(nds => [...nds, {
      id,
      type: 'instructionsNode',
      position: newNodePos(nds),
      data: { id, text: '' },
    }])
  }

  // Add new action node
  function addActionNode() {
    const id = `ACTION_${Date.now()}`
    setNodes(nds => [...nds, {
      id,
      type: 'actionNode',
      position: newNodePos(nds),
      data: { id, action_type: 'check_equipment', field: 'device_number', on_success: '', on_failure: '' },
    }])
  }

  // Add new done node
  function addDoneNode() {
    const id = `DONE_${Date.now()}`
    setNodes(nds => [...nds, {
      id,
      type: 'doneNode',
      position: newNodePos(nds),
      data: { id, text: '', action: 'save_service_call' },
    }])
  }

  // Save — always PUT (server does upsert); avoids POST name-required validation
  async function handleSave() {
    setSaving(true)
    setSaveMsg('')
    try {
      const script = flowToScript(nodes, edges, originalScript)
      console.log('[FlowEditor] Saving script:', script.script_id, script)
      const res = await fetch(`/api/bot-scripts/${script.script_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(script),
      })
      const data = await res.json()
      console.log('[FlowEditor] Save response:', data)
      if (data.ok) {
        setSaveMsg('נשמר בהצלחה!')
        onSave?.(script)
      } else {
        setSaveMsg(`שגיאה: ${data.error}`)
        console.error('[FlowEditor] Save failed:', data.error)
      }
    } catch (e) {
      setSaveMsg(`שגיאה: ${e.message}`)
      console.error('[FlowEditor] Save exception:', e)
    }
    setSaving(false)
  }

  // Keep selected node in sync when nodes change
  const syncedSelectedNode = useMemo(
    () => selectedNode ? nodes.find(n => n.id === selectedNode.id) || null : null,
    [selectedNode, nodes]
  )

  const [copied, setCopied] = useState(false)
  const currentScriptId = originalScript?.script_id || ''
  function copyScriptId() {
    navigator.clipboard.writeText(currentScriptId).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="fc-wrapper">
      {/* Top toolbar */}
      <div className="fc-toolbar">
        <button className="fc-back-btn" onClick={onBack}>→ חזרה לרשימה</button>
        <input
          className="fc-title-input"
          value={scriptName}
          onChange={e => handleNameChange(e.target.value)}
          placeholder="שם התסריט..."
        />
        {currentScriptId && (
          <button className="fc-script-id-btn" onClick={copyScriptId} title="לחץ להעתקת מזהה התסריט">
            🔑 {currentScriptId} {copied ? '✓' : ''}
          </button>
        )}
        <div className="fc-toolbar-right">
          <button className="fc-add-btn" onClick={addStepNode}>+ שאלה פתוחה</button>
          <button className="fc-add-btn" onClick={addButtonsNode}>+ שאלת בחירה</button>
          <button className="fc-add-btn fc-add-action" onClick={addActionNode}>+ בדיקה</button>
          <button className="fc-add-btn fc-add-instr" onClick={addInstructionsNode}>+ הוראות לבוט</button>
          <button className="fc-add-btn" onClick={addDoneNode}>+ סיום</button>
          <button
            className={`fc-push-btn${pushMode ? ' fc-push-btn--active' : ''}`}
            onClick={() => setPushMode(v => !v)}
            title="כשפעיל — גרירת ריבוע למטה מזיזה גם את הריבועים שמתחתיו"
          >↕ הזזה קולקטיבית</button>
          <button className="fc-danger-btn" onClick={deleteOrphans} title="מחק צמתים שאין להם חיבורים">
            🗑 מחק בודדים
          </button>
          {saveMsg && (
            <span className={`fc-save-msg ${saveMsg.includes('שגיאה') ? 'fc-error' : 'fc-success'}`}>
              {saveMsg}
            </span>
          )}
          <button className="fc-save-btn" onClick={handleSave} disabled={saving}>
            {saving ? 'שומר...' : 'שמירה'}
          </button>
        </div>
      </div>

      {/* Canvas + side panel */}
      <div className="fc-body">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          onNodeDragStart={onNodeDragStart}
          onNodeDragStop={onNodeDragStop}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          deleteKeyCode="Delete"
          minZoom={0.05}
          maxZoom={2}
        >
          <Background color="#E2E8F0" gap={20} />
          <Controls />
          <FitViewPanel onRecenter={recenterNodes} />
          <MiniMap
            nodeColor={n => {
              if (n.type === 'startNode') return '#4299E1'
              if (n.type === 'doneNode') return '#48BB78'
              if (n.type === 'buttonsNode') return '#805AD5'
              if (n.type === 'actionNode') return '#DD6B20'
              if (n.type === 'instructionsNode') return '#6B46C1'
              return '#718096'
            }}
          />
          <Panel position="bottom-center">
            <div className="fc-hint">
              גרור צומת להזזה · גרור קו בין נקודות לחיבור · לחץ על צומת לעריכה
            </div>
          </Panel>
        </ReactFlow>

        {syncedSelectedNode && (
          <SidePanel
            node={syncedSelectedNode}
            onUpdate={updateNodeData}
            onDelete={deleteNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  )
}
