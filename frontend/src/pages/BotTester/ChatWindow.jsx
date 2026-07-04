/* WhatsApp-style chat window: bot/user bubbles, clickable buttons, composer. */

import { useState, useRef, useEffect } from 'react'

export default function ChatWindow({ messages, started, onSend, busy, needsRoute, onRoute }) {
  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, needsRoute])

  const submit = () => {
    const t = draft.trim()
    if (!t || busy) return
    setDraft('')
    onSend(t, t) // free text — display text == sent text
  }

  // The most recent bot message may carry buttons; only that one is clickable.
  const lastBotIdx = [...messages].reverse().findIndex(m => m.from === 'bot')
  const lastBotRealIdx = lastBotIdx === -1 ? -1 : messages.length - 1 - lastBotIdx

  if (!started) {
    return (
      <div className="bt-col bt-col-chat">
        <div className="bt-col-header">💬 צ׳אט בדיקה</div>
        <div className="bt-empty-chat">
          <span className="ico">🤖</span>
          <p>הגדר תנאי פתיחה מימין ולחץ "התחל בדיקה"<br />כדי לפתוח שיחה עם הבוט.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bt-col bt-col-chat">
      <div className="bt-col-header">💬 צ׳אט בדיקה</div>
      <div className="bt-chat-scroll" ref={scrollRef}>
        {messages.map((m, i) => {
          if (m.from === 'note') {
            return <div key={i} className="bt-msg bt-msg-note">📢 {m.text}</div>
          }
          if (m.from === 'incoming') {
            return (
              <div key={i} className="bt-msg bt-msg-incoming">
                <div className="bt-incoming-h">📥 הודעה נכנסת · בוט קולי</div>
                {m.image && <img className="bt-incoming-img" src={m.image} alt="תמונת ההודעה" />}
                {m.text && <div className="bt-incoming-txt">{m.text}</div>}
              </div>
            )
          }
          const isBot = m.from === 'bot'
          const showButtons = isBot && i === lastBotRealIdx && m.buttons && m.buttons.length > 0
          return (
            <div key={i} className={`bt-msg ${isBot ? 'bt-msg-bot' : 'bt-msg-user'}`}>
              {m.text}
              {showButtons && (
                <div className="bt-btns">
                  {m.buttons.map(b => (
                    <button key={b.id} className="bt-chip" disabled={busy}
                            onClick={() => onSend(b.id, b.title)}>
                      {b.title}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {needsRoute && (
          <div className="bt-route-prompt">
            <div className="bt-route-q">🔀 הבוט צריך לבחור יציאה (צומת {needsRoute.step}):</div>
            <div className="bt-btns">
              {needsRoute.exits.map(ex => (
                <button key={ex.index} className="bt-chip bt-chip-route" disabled={busy}
                        onClick={() => onRoute(needsRoute.step, ex.index)}>
                  {ex.index + 1}. {ex.title}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="bt-composer">
        <input
          value={draft}
          placeholder={needsRoute ? 'בחר יציאה למעלה…' : 'הקלד תשובה…'}
          disabled={!!needsRoute}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') submit() }}
        />
        <button className="bt-send-btn" onClick={submit} disabled={busy || !!needsRoute || !draft.trim()}>➤</button>
      </div>
    </div>
  )
}
