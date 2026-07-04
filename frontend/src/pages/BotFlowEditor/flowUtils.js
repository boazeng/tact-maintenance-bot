// ── Convert script JSON → react-flow nodes + edges ───────────

export function scriptToFlow(script) {
  const nodes = []
  const edges = []
  const NODE_W = 260
  const xCenter = 400
  let y = 50
  const yGap = 160

  // Restore saved node positions if available
  const savedPos = script._flow_positions || {}

  // Start node
  nodes.push({
    id: '__start__',
    type: 'startNode',
    position: savedPos['__start__'] || { x: xCenter - NODE_W / 2, y },
    data: {
      name: script.name || '',
      bot_instructions: script.bot_instructions || '',
      greeting_known: script.greeting_known || '',
      greeting_unknown: script.greeting_unknown || '',
    },
  })
  y += yGap

  if (script.first_step) {
    edges.push({
      id: `__start__->${script.first_step}`,
      source: '__start__',
      target: script.first_step,
      type: 'smoothstep',
    })
  }

  // Step nodes
  ;(script.steps || []).forEach((step) => {
    const isButtons = step.type === 'buttons'
    const isAction = step.type === 'action'
    const isInstructions = step.type === 'instructions'

    nodes.push({
      id: step.id,
      type: isButtons ? 'buttonsNode' : isAction ? 'actionNode' : isInstructions ? 'instructionsNode' : 'stepNode',
      position: savedPos[step.id] || { x: xCenter - NODE_W / 2, y },
      data: { ...step },
    })

    if (isButtons) {
      ;(step.buttons || []).forEach((btn, bi) => {
        if (btn.next_step) {
          edges.push({
            id: `${step.id}-btn${bi}->${btn.next_step}`,
            source: step.id,
            sourceHandle: `btn-${bi}`,
            target: btn.next_step,
            label: btn.title,
            type: 'smoothstep',
            labelStyle: { fontSize: 11, fill: '#4A5568' },
            labelBgStyle: { fill: '#EBF8FF', fillOpacity: 0.9 },
          })
        }
      })
      y += 30 * Math.max((step.buttons || []).length - 1, 0)
    } else if (isAction) {
      if (step.on_success) {
        edges.push({
          id: `${step.id}-success->${step.on_success}`,
          source: step.id,
          sourceHandle: 'success',
          target: step.on_success,
          label: '✓ הצלחה',
          type: 'smoothstep',
          style: { stroke: '#48BB78' },
          labelStyle: { fontSize: 11, fill: '#276749' },
          labelBgStyle: { fill: '#F0FFF4', fillOpacity: 0.9 },
        })
      }
      if (step.on_failure) {
        edges.push({
          id: `${step.id}-failure->${step.on_failure}`,
          source: step.id,
          sourceHandle: 'failure',
          target: step.on_failure,
          label: '✕ כישלון',
          type: 'smoothstep',
          style: { stroke: '#FC8181' },
          labelStyle: { fontSize: 11, fill: '#C53030' },
          labelBgStyle: { fill: '#FFF5F5', fillOpacity: 0.9 },
        })
      }
    } else if (isInstructions) {
      const hasExits = (step.exits || []).length > 0
      if (hasExits) {
        const exitColors = ['#805AD5', '#38B2AC', '#FC8181']
        ;(step.exits || []).forEach((exit, ei) => {
          if (exit.next_step) {
            edges.push({
              id: `${step.id}-exit${ei}->${exit.next_step}`,
              source: step.id,
              sourceHandle: `exit-${ei}`,
              target: exit.next_step,
              label: exit.title,
              type: 'smoothstep',
              style: { stroke: exitColors[ei % exitColors.length] },
              labelStyle: { fontSize: 11, fill: '#553C9A' },
              labelBgStyle: { fill: '#FAF5FF', fillOpacity: 0.9 },
            })
          }
        })
        y += 30 * Math.max((step.exits || []).length - 1, 0)
      } else if (step.next_step) {
        edges.push({
          id: `${step.id}->${step.next_step}`,
          source: step.id,
          target: step.next_step,
          type: 'smoothstep',
        })
      }
    } else {
      if (step.next_step) {
        edges.push({
          id: `${step.id}->${step.next_step}`,
          source: step.id,
          target: step.next_step,
          type: 'smoothstep',
        })
      }
    }

    // skip_if edge (dashed orange)
    if (step.skip_if?.goto) {
      edges.push({
        id: `${step.id}-skip->${step.skip_if.goto}`,
        source: step.id,
        target: step.skip_if.goto,
        label: `דלג אם ${step.skip_if.field}`,
        type: 'smoothstep',
        style: { strokeDasharray: '5,5', stroke: '#ED8936' },
        labelStyle: { fontSize: 11, fill: '#C05621' },
        labelBgStyle: { fill: '#FFFBEB', fillOpacity: 0.9 },
      })
    }

    y += yGap
  })

  // Done nodes — spread horizontally at bottom, or restore saved position
  const doneEntries = Object.entries(script.done_actions || {})
  const doneSpacing = 300
  const doneStartX = xCenter - ((doneEntries.length - 1) * doneSpacing) / 2 - NODE_W / 2
  doneEntries.forEach(([id, action], i) => {
    nodes.push({
      id,
      type: 'doneNode',
      position: savedPos[id] || { x: doneStartX + i * doneSpacing, y },
      data: { id, ...action },
    })
  })

  return { nodes, edges }
}

// ── Convert react-flow nodes + edges → script JSON ────────────

export function flowToScript(nodes, edges, originalScript) {
  const startNode = nodes.find(n => n.type === 'startNode')
  const stepNodes = nodes.filter(n =>
    n.type === 'stepNode' || n.type === 'buttonsNode' || n.type === 'actionNode' || n.type === 'instructionsNode'
  )
  const doneNodes = nodes.filter(n => n.type === 'doneNode')

  // Build edge maps
  const simpleNext = {}       // sourceId → targetId
  const buttonNext = {}       // sourceId → { 'btn-0': targetId, ... }
  const actionNext = {}       // sourceId → { success: targetId, failure: targetId }
  const exitNext = {}         // sourceId → { 'exit-0': targetId, ... }

  edges.forEach(edge => {
    if (edge.source === '__start__') return
    if (edge.sourceHandle?.startsWith('btn-')) {
      if (!buttonNext[edge.source]) buttonNext[edge.source] = {}
      buttonNext[edge.source][edge.sourceHandle] = edge.target
    } else if (edge.sourceHandle === 'success' || edge.sourceHandle === 'failure') {
      if (!actionNext[edge.source]) actionNext[edge.source] = {}
      actionNext[edge.source][edge.sourceHandle] = edge.target
    } else if (edge.sourceHandle?.startsWith('exit-')) {
      if (!exitNext[edge.source]) exitNext[edge.source] = {}
      exitNext[edge.source][edge.sourceHandle] = edge.target
    } else {
      simpleNext[edge.source] = edge.target
    }
  })

  // Find first step from start edge
  const startEdge = edges.find(e => e.source === '__start__')
  const firstStep = startEdge?.target || stepNodes[0]?.id || ''

  // Sort steps by original order, then by Y position
  const originalOrder = (originalScript?.steps || []).map(s => s.id)
  const sortedSteps = [...stepNodes].sort((a, b) => {
    const ai = originalOrder.indexOf(a.id)
    const bi = originalOrder.indexOf(b.id)
    if (ai !== -1 && bi !== -1) return ai - bi
    if (ai !== -1) return -1
    if (bi !== -1) return 1
    return (a.position?.y || 0) - (b.position?.y || 0)
  })

  const steps = sortedSteps.map(node => {
    if (node.type === 'buttonsNode') {
      const btnMap = buttonNext[node.id] || {}
      return {
        id: node.id,
        type: 'buttons',
        text: node.data.text || '',
        buttons: (node.data.buttons || []).map((btn, bi) => ({
          ...btn,
          next_step: btnMap[`btn-${bi}`] || btn.next_step || '',
        })),
      }
    } else if (node.type === 'actionNode') {
      const aMap = actionNext[node.id] || {}
      return {
        id: node.id,
        type: 'action',
        action_type: node.data.action_type || 'check_equipment',
        field: node.data.field || '',
        description: node.data.description || '',
        on_success: aMap['success'] || node.data.on_success || '',
        on_failure: aMap['failure'] || node.data.on_failure || '',
      }
    } else if (node.type === 'instructionsNode') {
      const hasExits = (node.data.exits || []).length > 0
      if (hasExits) {
        const eMap = exitNext[node.id] || {}
        return {
          id: node.id,
          type: 'instructions',
          text: node.data.text || '',
          exits: (node.data.exits || []).map((exit, ei) => ({
            ...exit,
            next_step: eMap[`exit-${ei}`] || exit.next_step || '',
          })),
        }
      }
      return {
        id: node.id,
        type: 'instructions',
        text: node.data.text || '',
        next_step: simpleNext[node.id] || '',
      }
    } else {
      return {
        id: node.id,
        type: 'text_input',
        text: node.data.text || '',
        save_to: node.data.save_to || '',
        next_step: simpleNext[node.id] || '',
        ...(node.data.skip_if ? { skip_if: node.data.skip_if } : {}),
      }
    }
  })

  const done_actions = {}
  doneNodes.forEach(node => {
    done_actions[node.id] = {
      text: node.data.text || '',
      action: node.data.action || 'save_service_call',
      ...(node.data.target_script_id ? { target_script_id: node.data.target_script_id } : {}),
      ...(node.data.notify_phone ? { notify_phone: node.data.notify_phone } : {}),
      ...(node.data.notify_text ? { notify_text: node.data.notify_text } : {}),
    }
  })

  // Save node positions so they're restored on reload
  const _flow_positions = {}
  nodes.forEach(node => {
    if (node.position) _flow_positions[node.id] = node.position
  })

  const scriptId = originalScript?.script_id || `flow_${Date.now()}`
  const scriptName = startNode?.data?.name || originalScript?.name ||
    `תסריט ${new Date().toLocaleDateString('he-IL')}`

  return {
    script_id: scriptId,
    name: scriptName,
    bot_instructions: startNode?.data?.bot_instructions || '',
    greeting_known: startNode?.data?.greeting_known || '',
    greeting_unknown: startNode?.data?.greeting_unknown || '',
    first_step: firstStep,
    steps,
    done_actions,
    active: originalScript?.active ?? true,
    _flow_positions,
  }
}

// ── Initial empty flow for new scripts ───────────────────────

export function emptyFlow() {
  return {
    nodes: [
      {
        id: '__start__',
        type: 'startNode',
        position: { x: 170, y: 50 },
        data: { name: '', greeting_known: '', greeting_unknown: '' },
      },
      {
        id: 'DONE_1',
        type: 'doneNode',
        position: { x: 170, y: 400 },
        data: { id: 'DONE_1', text: '', action: 'save_service_call' },
      },
    ],
    edges: [],
  }
}
