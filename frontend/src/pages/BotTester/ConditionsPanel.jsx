/* Opening-conditions panel — the five branch drivers + LLM routing mode. */

import ImagePaste from './ImagePaste'

const FORMATS = [
  { value: 'free', label: 'טקסט חופשי' },
  { value: 'qr', label: 'קוד QR (עם מספר מכשיר)' },
  { value: 'voice', label: 'בוט קולי' },
]

// A realistic Mr.Bot voice-bot message (key:value lines), used by "טען דוגמה".
export const VOICE_SAMPLE = `מתקני חניה- לקוח קיים

מספר מנוי:5828
שעת שיחה:16:47:15
תאריך שיחה:2026-06-30
שם הלקוח:יעל בלפר
סוג הלקוח:לקוח קיים
נושא פניה:מתקני חניה
מהות ההודעה:מערכת בירור האוטו עלה מהחנייה
מערכת מושבתת:כן
כתובת המתקן:פרופסור שור 4,תל אביב
טלפון:0547740422
מספר מזוהה:972547740422`

export default function ConditionsPanel({ scripts, cond, setCond, onStart, onReset, started }) {
  // helper to update a nested condition slice
  const set = (patch) => setCond({ ...cond, ...patch })
  const setCaller = (patch) => set({ caller: { ...cond.caller, ...patch } })
  const setInbound = (patch) => set({ inbound: { ...cond.inbound, ...patch } })
  const setDevice = (patch) => set({ device: { ...cond.device, ...patch } })
  const isMock = (cond.data_source || 'mock') === 'mock'

  return (
    <div className="bt-col bt-col-conditions">
      <div className="bt-col-header">
        <span>⚙️ תנאי פתיחה</span>
        {started && <button className="bt-reset-btn" onClick={onReset}>נקה</button>}
      </div>
      <div className="bt-col-body">
        {/* 1 — script */}
        <div className="bt-field">
          <label>1 · תסריט לבדיקה</label>
          <select className="bt-select" value={cond.script_id}
                  onChange={e => set({ script_id: e.target.value })}>
            {scripts.map(s => (
              <option key={s.script_id} value={s.script_id}>{s.name || s.script_id}</option>
            ))}
          </select>
        </div>

        {/* data source */}
        <div className="bt-field">
          <label>מקור נתונים</label>
          <select className="bt-select" value={cond.data_source || 'mock'}
                  onChange={e => set({ data_source: e.target.value })}>
            <option value="mock">Mock — נתונים מדומים (בטוח)</option>
            <option value="servicecall">האפליקציה שלי (Service-Call)</option>
          </select>
          {cond.data_source === 'servicecall' && (
            <div className="bt-hint">הזיהוי (לקוח/מכשיר/קריאה פתוחה) נשלף מ-Service-Call — הזן מספר מכשיר אמיתי בצ׳אט.</div>
          )}
        </div>

        {/* write target — where a NEW service call is opened */}
        <div className="bt-field">
          <label>יעד פתיחת קריאה</label>
          <select className="bt-select" value={cond.write_target || 'dry'}
                  onChange={e => set({ write_target: e.target.value })}>
            <option value="dry">לא לפתוח (בדיקה — dry-run)</option>
            <option value="servicecall">האפליקציה שלי (Service-Call)</option>
          </select>
          {cond.write_target === 'dry' && (
            <div className="bt-safe">✓ לא נפתחת קריאה — רק בדיקת הזרימה.</div>
          )}
          {cond.write_target === 'servicecall' && (
            <>
              <label className="bt-check" style={{ marginTop: 8 }}>
                <input type="checkbox" checked={!!cond.write_real}
                       onChange={e => set({ write_real: e.target.checked })} />
                שלח ופתח קריאה אמיתית ב-Service-Call
              </label>
              {cond.write_real ? (
                <div className="bt-safe">↗ בסיום השיחה תיפתח קריאה אמיתית באפליקציית Service-Call שלך.</div>
              ) : (
                <div className="bt-safe">✓ מצב בדיקה: הזרימה רצה עד הסוף אך <b>לא</b> נשלחת קריאה (dry-run).</div>
              )}
            </>
          )}
        </div>

        {/* 2 — caller identity */}
        <div className="bt-field">
          <label>2 · זהות הפונה</label>
          <input className="bt-input" placeholder="שם הפונה" value={cond.caller.name}
                 onChange={e => setCaller({ name: e.target.value })} />
          <label className="bt-check" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={cond.caller.known}
                   onChange={e => setCaller({ known: e.target.checked })} />
            לקוח מזוהה מראש (חיפוש טלפון הצליח)
          </label>
          {cond.caller.known && (
            <div className="bt-subfields">
              <input className="bt-input" placeholder="שם לקוח" value={cond.caller.customer_name}
                     onChange={e => setCaller({ customer_name: e.target.value })} />
              <input className="bt-input" style={{ marginTop: 6 }} placeholder="מספר לקוח"
                     value={cond.caller.customer_number}
                     onChange={e => setCaller({ customer_number: e.target.value })} />
            </div>
          )}
        </div>

        {/* 3 — inbound message */}
        <div className="bt-field">
          <label>3 · הודעה נכנסת</label>
          <select className="bt-select" value={cond.inbound.format}
                  onChange={e => setInbound({ format: e.target.value })}>
            {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
          {cond.inbound.format === 'voice' ? (
            <>
              <ImagePaste image={cond.inbound.image}
                          onImage={url => setInbound({ image: url })}
                          onClear={() => setInbound({ image: '' })} />
              <textarea className="bt-input bt-textarea" rows={9} style={{ marginTop: 6 }}
                        placeholder="הדבק כאן את הודעת הבוט הקולי (שורות של שדה:ערך)…"
                        value={cond.inbound.text}
                        onChange={e => setInbound({ text: e.target.value })} />
              <button type="button" className="bt-reset-btn" style={{ marginTop: 6 }}
                      onClick={() => setInbound({ text: VOICE_SAMPLE })}>↧ טען דוגמה</button>
              <div className="bt-hint">השדות (שם לקוח, מהות ההודעה, מערכת מושבתת, כתובת, טלפון) יפוענחו אוטומטית.</div>
            </>
          ) : (
            <input className="bt-input" style={{ marginTop: 6 }} placeholder="טקסט ההודעה הראשונה"
                   value={cond.inbound.text} onChange={e => setInbound({ text: e.target.value })} />
          )}
        </div>

        <hr className="bt-divider" />

        {/* 4 — equipment */}
        <div className="bt-field">
          <label>4 · מכשיר בפריורטי</label>
          <input className="bt-input" placeholder="מספר מכשיר לבדיקה"
                 value={cond.device.sernum} onChange={e => setDevice({ sernum: e.target.value })} />
          {isMock && (
            <>
              <label className="bt-check" style={{ marginTop: 8 }}>
                <input type="checkbox" checked={cond.device.exists}
                       onChange={e => setDevice({ exists: e.target.checked })} />
                המכשיר קיים בפריורטי
              </label>
              {cond.device.exists && (
                <div className="bt-subfields">
                  <input className="bt-input" placeholder="שם הלקוח של המכשיר"
                         value={cond.device.customer_name}
                         onChange={e => setDevice({ customer_name: e.target.value })} />
                  <input className="bt-input" style={{ marginTop: 6 }} placeholder="כתובת המתקן"
                         value={cond.device.location}
                         onChange={e => setDevice({ location: e.target.value })} />
                </div>
              )}
            </>
          )}
          <div className="bt-hint">
            {cond.inbound.format === 'qr'
              ? 'פורמט QR — מספר המכשיר נכנס אוטומטית עם ההודעה'
              : 'טקסט חופשי — הקלד את מספר המכשיר בצ׳אט כשהבוט מבקש'}
          </div>
        </div>

        {/* 5 — open service call (mock only; Priority decides in live mode) */}
        {isMock && (
          <div className="bt-field">
            <label className="bt-check">
              <input type="checkbox" checked={cond.openCall}
                     onChange={e => set({ openCall: e.target.checked })} />
              5 · קיימת כבר קריאת שירות פתוחה
            </label>
            <div className="bt-hint">רלוונטי רק אם המכשיר קיים</div>
          </div>
        )}

        <hr className="bt-divider" />

        {/* LLM routing */}
        <div className="bt-field">
          <label>ניתוב LLM (צמתי הוראות)</label>
          <select className="bt-select" value={cond.llm_mode}
                  onChange={e => set({ llm_mode: e.target.value })}>
            <option value="manual">ידני — יציאה 0 כברירת מחדל</option>
            <option value="live">אמיתי — OpenAI</option>
          </select>
          <div className="bt-hint">
            במצב ידני הבוט לוקח את היציאה הראשונה; ראה במפקח מה נבחר.
          </div>
        </div>

        <button className="bt-start-btn" onClick={onStart}>▶ התחל בדיקה</button>
      </div>
    </div>
  )
}
