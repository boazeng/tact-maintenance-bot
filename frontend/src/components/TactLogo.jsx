import '../styles/TactLogo.css'

export default function TactLogo({
  tone = 'light',
  size = 1,
  word = 'bots',
  tagline = false,
  taglineText = '',
}) {
  const letters = ['T', 'A', 'C', 'T']
  return (
    <span className={`tact-logo tact-logo-${tone}`} style={{ '--tact-scale': size }}>
      <span className="tact-logo-lockup">
        <span className="tact-logo-row">
          <span className="tact-logo-mark">
            {letters.map((l, i) => (
              <span key={i} className="tact-logo-seg">
                <span className="tact-logo-letter">{l}</span>
                {i < letters.length - 1 && <span className="tact-logo-dot" />}
              </span>
            ))}
          </span>
          {word && <span className="tact-logo-word">{word}</span>}
        </span>
        {tagline && <span className="tact-logo-tagline">{taglineText}</span>}
      </span>
    </span>
  )
}
