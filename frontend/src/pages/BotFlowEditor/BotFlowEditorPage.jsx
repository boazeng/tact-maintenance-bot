import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import FlowCanvas from './FlowCanvas'
import { scriptToFlow, emptyFlow } from './flowUtils'
import './BotFlowEditor.css'

export default function BotFlowEditorPage() {
  const [view, setView] = useState('list') // 'list' | 'editor'
  const [scripts, setScripts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Current flow state
  const [flowNodes, setFlowNodes] = useState([])
  const [flowEdges, setFlowEdges] = useState([])
  const [originalScript, setOriginalScript] = useState(null)

  useEffect(() => { fetchScripts() }, [])

  async function fetchScripts() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/bot-scripts')
      const data = await res.json()
      if (data.ok) setScripts(data.scripts)
      else setError(data.error)
    } catch (e) { setError(e.message) }
    setLoading(false)
  }

  async function openScript(scriptId) {
    try {
      const res = await fetch(`/api/bot-scripts/${scriptId}`)
      const data = await res.json()
      if (data.ok) {
        const { nodes, edges } = scriptToFlow(data.script)
        setFlowNodes(nodes)
        setFlowEdges(edges)
        setOriginalScript(data.script)
        setView('editor')
      }
    } catch (e) { setError(e.message) }
  }

  function openNew() {
    const { nodes, edges } = emptyFlow()
    setFlowNodes(nodes)
    setFlowEdges(edges)
    setOriginalScript({
      script_id: `flow_${Date.now()}`,
      name: '',
      steps: [],
      done_actions: {},
      active: true,
    })
    setView('editor')
  }

  function onSaved(savedScript) {
    setOriginalScript(savedScript)
    fetchScripts()
  }

  // ── List View ─────────────────────────────────────────────

  if (view === 'list') {
    return (
      <div className="bfe-page">
        <div className="container">
          <Link to="/" className="bfe-back">→ דף הבית</Link>

          <div className="bfe-header">
            <div>
              <h1 className="bfe-title">עורך זרימה ויזואלי</h1>
              <p className="bfe-subtitle">בנה תסריטי בוט על ידי חיבור בין צמתים</p>
            </div>
            <button className="bfe-new-btn" onClick={openNew}>+ תסריט חדש</button>
          </div>

          {/* Explainer */}
          <div className="bfe-explainer">
            <div className="bfe-exp-item">
              <span className="bfe-exp-icon" style={{ background: '#EBF8FF', color: '#2B6CB0' }}>🚀</span>
              <span>פתיחת שיחה — הודעת הפתיחה</span>
            </div>
            <div className="bfe-exp-arrow">→</div>
            <div className="bfe-exp-item">
              <span className="bfe-exp-icon" style={{ background: '#F0FFF4', color: '#276749' }}>✏️</span>
              <span>שאלה פתוחה — תשובת טקסט</span>
            </div>
            <div className="bfe-exp-arrow">→</div>
            <div className="bfe-exp-item">
              <span className="bfe-exp-icon" style={{ background: '#FAF5FF', color: '#553C9A' }}>🔘</span>
              <span>שאלת בחירה — כפתורים לענפים</span>
            </div>
            <div className="bfe-exp-arrow">→</div>
            <div className="bfe-exp-item">
              <span className="bfe-exp-icon" style={{ background: '#FFFAF0', color: '#C05621' }}>⚡</span>
              <span>בדיקה אוטומטית — ענפים להצלחה/כישלון</span>
            </div>
            <div className="bfe-exp-arrow">→</div>
            <div className="bfe-exp-item">
              <span className="bfe-exp-icon" style={{ background: '#F0FFF4', color: '#276749' }}>✓</span>
              <span>סיום — פעולה וסגירת שיחה</span>
            </div>
          </div>

          {loading && <div className="bfe-loading">טוען...</div>}
          {error && <div className="bfe-error">{error}</div>}

          <div className="bfe-list">
            {scripts.map(s => (
              <div key={s.script_id} className="bfe-card" onClick={() => openScript(s.script_id)}>
                <div className="bfe-card-left">
                  <span className="bfe-card-icon">🗂️</span>
                  <div>
                    <h3 className="bfe-card-name">{s.name || s.script_id}</h3>
                    <span className="bfe-card-meta">{(s.steps || []).length} שלבים</span>
                    <span className="bfe-card-id">{s.script_id}</span>
                  </div>
                </div>
                <div className="bfe-card-right">
                  <span className={`bfe-badge ${s.active ? 'bfe-active' : 'bfe-inactive'}`}>
                    {s.active ? 'פעיל' : 'לא פעיל'}
                  </span>
                  <span className="bfe-open-btn">פתח עורך →</span>
                </div>
              </div>
            ))}
            {!loading && scripts.length === 0 && (
              <div className="bfe-empty">
                <p>אין תסריטים עדיין</p>
                <button className="bfe-new-btn" onClick={openNew} style={{ marginTop: 16 }}>
                  + צור תסריט ראשון
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── Editor View (full screen flow canvas) ─────────────────

  return (
    <FlowCanvas
      initialNodes={flowNodes}
      initialEdges={flowEdges}
      originalScript={originalScript}
      onSave={onSaved}
      onBack={() => setView('list')}
    />
  )
}
