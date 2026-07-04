/* בודק שיחות — drives the real bot engine via /api/bot-test with a fully
   controlled opening condition, plus a saved-scenario regression suite.

   The backend uses a deterministic drive model (re-runs start + all inputs each
   turn), so every response carries the full transcript; we render it wholesale. */

import { useState, useEffect, useCallback } from 'react'
import ConditionsPanel from './ConditionsPanel'
import ChatWindow from './ChatWindow'
import SessionInspector from './SessionInspector'
import RegressionBar from './RegressionBar'
import './BotTester.css'

const TESTER_ID = 'test-001'
// Tests start from the main maintenance bot; it switch_scripts into the sub-bot.
const MAIN_SCRIPT_ID = 'flow_1772177781916'

const DEFAULT_COND = {
  script_id: MAIN_SCRIPT_ID,
  caller: { name: 'בדיקה', known: false, customer_name: '', customer_number: '' },
  inbound: { text: 'יש תקלה', format: 'free', image: '' },
  device: { sernum: '12345', exists: true, customer_name: 'חניון רוטשילד', location: 'רוטשילד 5' },
  openCall: false,
  llm_mode: 'manual',
  data_source: 'servicecall',
  write_target: 'dry',
  write_real: false,
}

// Parse a Mr.Bot voice message ("field:value" lines, Hebrew or ASCII colon)
// into a parsed_data dict the engine consumes.
function parseVoice(text) {
  const pd = {}
  for (const line of String(text || '').split('\n')) {
    const m = line.match(/^\s*([^:：]+)[:：](.*)$/)
    if (m) {
      const k = m[1].trim(), v = m[2].trim()
      if (k && v) pd[k] = v
    }
  }
  return pd
}

function buildScenario(c, forcedExits) {
  const sern = String(c.device.sernum || '').trim()
  const equipment = {}
  const open_calls = {}
  if (c.device.exists && sern) {
    equipment[sern] = {
      custname: c.caller.customer_number || 'C-TEST',
      cdes: c.device.customer_name || 'לקוח בדיקה',
      location: c.device.location || '',
    }
    open_calls[sern] = c.openCall ? [{ DOCNO: 'OPEN-1001', CALLSTATUSCODE: 'פתוחה' }] : []
  }
  let parsed_data = {}
  let device_number = ''
  if (c.inbound.format === 'voice') {
    parsed_data = parseVoice(c.inbound.text)
    device_number = parsed_data['מספר מכשיר'] || ''
  } else if (c.inbound.format === 'qr') {
    device_number = sern
  }
  return {
    script_id: c.script_id,
    caller: { phone: TESTER_ID, name: c.caller.name, known: c.caller.known,
              customer_name: c.caller.customer_name, customer_number: c.caller.customer_number },
    inbound: { text: c.inbound.text, format: c.inbound.format, device_number, parsed_data,
               has_media: !!c.inbound.image },
    equipment, open_calls,
    data_source: c.data_source || 'mock',
    write_target: c.write_target || 'dry',
    write_real: !!c.write_real,
    llm_mode: c.llm_mode, forced_exits: forcedExits || {},
  }
}

// Flatten a backend transcript into chat messages (bot admin-notifications
// become inline notes).
function mapTranscript(transcript) {
  const out = []
  for (const m of transcript || []) {
    if (m.from === 'bot') {
      if (m.text) out.push({ from: 'bot', text: m.text, buttons: m.buttons })
      if (m.notify) out.push({ from: 'note', text: `התראת מנהל → ${m.notify.phone}` })
    } else if (m.from === 'user') {
      out.push({ from: 'user', text: m.text })
    } else {
      out.push({ from: 'note', text: m.text })
    }
  }
  return out
}

async function postJSON(url, body) {
  try {
    const res = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    const text = await res.text()
    if (!text) return { ok: false, error: `השרת לא החזיר תשובה (${res.status}) — ודא שה-backend רץ` }
    try { return JSON.parse(text) }
    catch { return { ok: false, error: 'תגובה לא תקינה מהשרת' } }
  } catch {
    return { ok: false, error: 'השרת לא זמין — ודא שה-backend רץ (פורט 8020)' }
  }
}

export default function BotTesterPage() {
  const [scripts, setScripts] = useState([])
  const [cond, setCond] = useState(DEFAULT_COND)
  const [messages, setMessages] = useState([])
  const [needsRoute, setNeedsRoute] = useState(null)
  const [session, setSession] = useState(null)
  const [mock, setMock] = useState(null)
  const [started, setStarted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [sentInputs, setSentInputs] = useState([])
  const [forcedExits, setForcedExits] = useState({})
  const [incomingMsg, setIncomingMsg] = useState(null)   // voice-bot image+text preview
  const [scenarios, setScenarios] = useState([])
  const [runResult, setRunResult] = useState(null)

  const loadScenarios = useCallback(async () => {
    const d = await fetch('/api/bot-test/scenarios').then(r => r.json()).catch(() => null)
    if (d?.ok) setScenarios(d.scenarios)
  }, [])

  useEffect(() => {
    fetch('/api/bot-scripts').then(r => r.json()).then(d => {
      if (!d.ok) return
      const main = d.scripts.filter(s => s.script_id === MAIN_SCRIPT_ID)
      setScripts(main.length ? main : d.scripts)   // show only the main bot as entry point
    }).catch(() => {})
    loadScenarios()
  }, [loadScenarios])

  function apply(d, prefix) {
    if (!d.ok) { setError(d.error); return }
    setError(null)
    const pre = prefix !== undefined ? prefix : (incomingMsg ? [incomingMsg] : [])
    setMessages([...pre, ...mapTranscript(d.transcript)])
    setNeedsRoute(d.needs_route || null)
    setSession(d.session); setMock(d.mock)
  }

  async function start() {
    setBusy(true); setError(null); setSentInputs([]); setForcedExits({})
    // A voice-bot message arrives as an image + structured text — show it as the
    // incoming message at the top of the chat.
    const incoming = (cond.inbound.format === 'voice' && (cond.inbound.image || cond.inbound.text))
      ? [{ from: 'incoming', text: cond.inbound.text, image: cond.inbound.image }] : []
    setIncomingMsg(incoming[0] || null)
    try {
      const d = await postJSON('/api/bot-test/start', buildScenario(cond, {}))
      if (d.ok) setStarted(true)
      apply(d, incoming)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function send(sendText, displayText) {
    if (busy) return
    setBusy(true)
    setSentInputs(s => [...s, sendText])
    try {
      apply(await postJSON('/api/bot-test/message', { tester_id: TESTER_ID, text: sendText, display: displayText }))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function chooseRoute(step, exitIndex) {
    if (busy) return
    setBusy(true)
    setForcedExits(f => ({ ...f, [step]: exitIndex }))
    try {
      apply(await postJSON('/api/bot-test/route', { tester_id: TESTER_ID, step, exit_index: exitIndex }))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function reset() {
    await postJSON('/api/bot-test/reset', { tester_id: TESTER_ID }).catch(() => {})
    setStarted(false); setMessages([]); setNeedsRoute(null); setSession(null)
    setMock(null); setError(null); setSentInputs([]); setForcedExits({}); setIncomingMsg(null)
  }

  // ── Regression ──
  function deriveExpect() {
    if (!session) return {}
    const exp = { reach_step: session.step }
    const done = (session.log || []).find(e => e.event === 'session_done')
    if (done?.action) exp.final_action = done.action
    return exp
  }

  async function saveScenario() {
    const name = window.prompt('שם התרחיש:', `${cond.script_id} · ${session?.status === 'done' ? 'הושלם' : 'טיוטה'}`)
    if (!name) return
    const scenario = {
      ...buildScenario(cond, forcedExits),
      name,
      steps: sentInputs.map(s => ({ send: s })),
      expect: deriveExpect(),
    }
    const d = await postJSON('/api/bot-test/scenarios', scenario)
    if (d.ok) loadScenarios(); else setError(d.error)
  }

  async function replayScenario(s) {
    setBusy(true); setError(null)
    try {
      const d = await postJSON('/api/bot-test/replay', s)
      if (!d.ok) { setError(d.error); return }
      setStarted(true); setSession(d.session); setMock(d.mock)
      setNeedsRoute(null); setSentInputs([]); setForcedExits(s.forced_exits || {})
      const msgs = mapTranscript(d.transcript)
      if (d.verdict) {
        msgs.push({ from: 'note', text: (d.verdict.passed ? '✅ עבר' : '❌ נכשל') + ' — ' +
          d.verdict.checks.map(c => `${c.pass ? '✓' : '✗'} ${c.check}`).join(' · ') })
      }
      setMessages(msgs)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function deleteScenario(id) {
    await fetch(`/api/bot-test/scenarios/${id}`, { method: 'DELETE' }).catch(() => {})
    loadScenarios()
  }

  async function runAll() {
    const d = await postJSON('/api/bot-test/run-all', {})
    if (d.ok) { setRunResult(d); loadScenarios() } else setError(d.error)
  }

  const shownMessages = error ? [...messages, { from: 'note', text: 'שגיאה: ' + error }] : messages

  return (
    <div className="bt-wrap">
      <RegressionBar
        scenarios={scenarios} started={started} canSave={started}
        onSave={saveScenario} onReplay={replayScenario} onDelete={deleteScenario}
        onRunAll={runAll} runResult={runResult}
      />
      <div className="bt-page">
        <ConditionsPanel
          scripts={scripts} cond={cond} setCond={setCond}
          onStart={start} onReset={reset} started={started}
        />
        <ChatWindow
          messages={shownMessages} started={started} onSend={send} busy={busy}
          needsRoute={needsRoute} onRoute={chooseRoute}
        />
        <SessionInspector session={session} mock={mock} />
      </div>
    </div>
  )
}
