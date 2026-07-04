/* Paste or pick an image for the incoming voice-bot message (stored as a data URL). */

import { useRef } from 'react'

export default function ImagePaste({ image, onImage, onClear }) {
  const fileRef = useRef(null)

  function fromFile(file) {
    if (!file || !file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = () => onImage(reader.result)
    reader.readAsDataURL(file)
  }

  function onPaste(e) {
    const items = e.clipboardData?.items || []
    for (const it of items) {
      if (it.type.startsWith('image/')) {
        fromFile(it.getAsFile())
        e.preventDefault()
        return
      }
    }
  }

  if (image) {
    return (
      <div className="bt-imgprev">
        <img src={image} alt="תמונת ההודעה" />
        <button type="button" className="bt-img-x" onClick={onClear} title="הסר תמונה">✕</button>
      </div>
    )
  }

  return (
    <div className="bt-imgdrop" tabIndex={0} onPaste={onPaste}>
      <span>🖼️ לחץ כאן והדבק תמונה (Ctrl+V)</span>
      <button type="button" className="bt-img-pick" onClick={() => fileRef.current?.click()}>
        או בחר קובץ
      </button>
      <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }}
             onChange={e => fromFile(e.target.files?.[0])} />
    </div>
  )
}
