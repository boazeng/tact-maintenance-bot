/* Regression toolbar: save current run as a scenario, list/replay/delete saved
   scenarios, and run the whole suite. */

import { useState } from 'react'

export default function RegressionBar({
  scenarios, started, canSave, onSave, onReplay, onDelete, onRunAll, runResult,
}) {
  const [listOpen, setListOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)

  async function handleRunAll() {
    await onRunAll()
    setModalOpen(true)
  }

  return (
    <div className="bt-regbar" style={{ position: 'relative' }}>
      <strong style={{ color: 'var(--color-primary)' }}>🧪 רגרסיה</strong>

      <button className="bt-regbtn" disabled={!canSave} onClick={onSave}
              title={canSave ? 'שמור את התנאים + רצף ההודעות כתרחיש' : 'סיים שיחה קודם'}>
        💾 שמור כתרחיש
      </button>

      <button className="bt-regbtn" onClick={() => setListOpen(o => !o)}>
        📋 תרחישים ({scenarios.length})
      </button>

      <button className="bt-regbtn bt-regbtn-primary" disabled={scenarios.length === 0}
              onClick={handleRunAll}>
        🏁 הרץ הכל
      </button>

      {runResult && (
        <span className="bt-reg-summary">
          <span className="bt-reg-pass">✓ {runResult.passed}</span>
          {' / '}
          <span className={runResult.failed ? 'bt-reg-fail' : ''}>✗ {runResult.failed}</span>
          {' מתוך '}{runResult.total}
        </span>
      )}

      <span className="sep" />

      {listOpen && (
        <div className="bt-reglist">
          {scenarios.length === 0 && <div className="bt-reg-empty">אין תרחישים שמורים עדיין</div>}
          {scenarios.map(s => (
            <div className="bt-reg-row" key={s.scenario_id}>
              <button className="bt-reg-icon" title="הרץ תרחיש זה"
                      onClick={() => { onReplay(s); setListOpen(false) }}>▶</button>
              <span className="nm">{s.name || s.scenario_id}</span>
              {s.steps?.length ? <span className="st">{s.steps.length} צעדים</span> : null}
              <button className="bt-reg-icon" title="מחק"
                      onClick={() => onDelete(s.scenario_id)}>🗑</button>
            </div>
          ))}
        </div>
      )}

      {modalOpen && runResult && (
        <div className="bt-modal-back" onClick={() => setModalOpen(false)}>
          <div className="bt-modal" onClick={e => e.stopPropagation()}>
            <div className="bt-modal-head">
              <h3>תוצאות רגרסיה — {runResult.passed}/{runResult.total} עברו</h3>
              <button className="bt-modal-close" onClick={() => setModalOpen(false)}>✕</button>
            </div>
            <div className="bt-modal-body">
              {runResult.results.map((r, i) => (
                <div className="bt-res-row" key={i}>
                  <span className="badge">{r.passed ? '✅' : '❌'}</span>
                  <span className="nm">{r.name}</span>
                  <span className="detail">
                    {r.error ? r.error
                      : (r.checks || []).map(c => `${c.pass ? '✓' : '✗'}${c.check}`).join('  ')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
