/* Live session inspector — collected fields, current step, LLM routes, event log. */

const EVENT_LABEL = {
  session_start: 'התחלה', step_shown: 'הצגת שלב', user_input: 'קלט', button_matched: 'כפתור',
  skip_if_triggered: 'דילוג', action_executed: 'פעולה', llm_route: 'ניתוב AI',
  instructions_auto: 'הוראות', switch_script: 'מעבר תסריט', session_done: 'סיום', session_cancelled: 'ביטול',
}

// Fields worth surfacing (in order); the rest are engine bookkeeping.
const SHOW_FIELDS = [
  ['step', 'שלב'], ['script_id', 'תסריט'], ['customer_name', 'לקוח'],
  ['customer_number', 'מס׳ לקוח'], ['device_number', 'מכשיר'], ['location', 'כתובת'],
  ['description', 'תיאור'], ['is_system_down', 'מושבת'],
  ['equipment_check_result', 'בדיקת מכשיר'], ['open_service_call_result', 'קריאה פתוחה'],
]

function logDetail(e) {
  switch (e.event) {
    case 'action_executed': return `${e.action_type} (${e.field}=${e.value}) → ${e.result}`
    case 'button_matched': return `${e.button_title || e.button_id} → ${e.next_step}`
    case 'user_input': return `"${e.input}"`
    case 'step_shown': return `[${e.step}]`
    case 'session_done': return `${e.done_id} · ${e.action}`
    case 'skip_if_triggered': return `${e.field} → ${e.target}`
    default: return e.target || ''
  }
}

export default function SessionInspector({ session, mock }) {
  if (!session) {
    return (
      <div className="bt-col bt-col-inspector">
        <div className="bt-col-header">🔎 מפקח סשן</div>
        <div className="bt-col-body"><p style={{ color: '#A0AEC0', fontSize: 13 }}>אין סשן פעיל.</p></div>
      </div>
    )
  }

  const fields = session.fields || {}
  const done = session.status === 'done'
  const routes = session.llm_routes || []
  const created = (mock && mock.created_calls) || []
  const parsed = session.parsed_data || {}
  const parsedKeys = Object.keys(parsed)

  return (
    <div className="bt-col bt-col-inspector">
      <div className="bt-col-header">
        <span>🔎 מפקח סשן</span>
        <span className={`bt-badge ${done ? 'bt-badge-done' : 'bt-badge-active'}`}>
          {done ? '✓ הסתיים' : '● פעיל'}
        </span>
      </div>
      <div className="bt-col-body">
        {/* collected fields */}
        <div className="bt-insp-section">
          <div className="bt-insp-title">שדות שנאספו</div>
          {SHOW_FIELDS.map(([k, label]) => (
            fields[k] !== undefined && fields[k] !== '' ? (
              <div className="bt-kv" key={k}><span className="k">{label}</span><span className="v">{String(fields[k])}</span></div>
            ) : null
          ))}
        </div>

        {/* parsed voice-bot message */}
        {parsedKeys.length > 0 && (
          <div className="bt-insp-section">
            <div className="bt-insp-title">הודעת בוט קולי (מפוענח)</div>
            {parsedKeys.map(k => (
              <div className="bt-kv" key={k}><span className="k">{k}</span><span className="v">{String(parsed[k])}</span></div>
            ))}
          </div>
        )}

        {/* created service calls (mock / dry-run / real) */}
        {created.length > 0 && (
          <div className="bt-insp-section">
            <div className="bt-insp-title">
              קריאות שנפתחו {
                mock?.target === 'service-call'
                  ? (mock.dry_write ? '(Service-Call · dry-run · לא נשלח)' : '(Service-Call שלך)')
                  : mock?.live ? (mock.dry_write ? '(dry-run · לא נכתב)' : '(פריורטי חי!)')
                  : '(mock)'
              }
            </div>
            {created.map((c, i) => (
              <div className="bt-kv" key={i}>
                <span className="k">DOCNO</span>
                <span className="v">{c.DOCNO}{c.dry ? ' · dry' : ''}</span>
              </div>
            ))}
          </div>
        )}

        {/* LLM routes */}
        {routes.length > 0 && (
          <div className="bt-insp-section">
            <div className="bt-insp-title">ניתובי LLM</div>
            {routes.map((r, i) => (
              <div className="bt-route" key={i}>
                <span className="src">[{r.source}]</span> {r.step} → יציאה {r.index} ({r.title || '—'})
              </div>
            ))}
          </div>
        )}

        {/* event log */}
        <div className="bt-insp-section">
          <div className="bt-insp-title">לוג אירועים</div>
          <div className="bt-log">
            {(session.log || []).map((e, i) => (
              <div key={i} className={`bt-log-row${e.result === 'failure' ? ' bt-log-fail' : ''}`}>
                <span className="ev">{EVENT_LABEL[e.event] || e.event}</span>
                <span className="dt">{logDetail(e)}</span>
              </div>
            ))}
            {(session.log || []).length === 0 && <span style={{ color: '#A0AEC0', fontSize: 12 }}>—</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
