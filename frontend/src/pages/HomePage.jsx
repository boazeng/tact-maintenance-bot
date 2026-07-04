import { Link } from 'react-router-dom'

const CARDS = [
  {
    to: '/editor',
    ico: '🎨',
    title: 'עורך זרימה ויזואלי',
    desc: 'בנייה של תסריט הבוט על ידי חיבור צמתים — שאלות, כפתורים, בדיקות, פעולות וסיום.',
  },
  {
    to: '/diagnostics',
    ico: '🔍',
    title: 'אבחון שיחות',
    desc: 'מעקב אחר שיחות פעילות וצפייה בלוג האירועים של כל שלב בתסריט.',
  },
]

export default function HomePage() {
  return (
    <>
      <div className="app-hero">
        <h1>פלטפורמת בוטים לוואטסאפ</h1>
        <p>בנו, ערכו והריצו תסריטי בוט עצמאיים — כל פעם בוט אחר.</p>
      </div>
      <div className="hub-grid">
        {CARDS.map((c) => (
          <Link key={c.to} to={c.to} className="hub-card">
            <div className="hub-card-ico">{c.ico}</div>
            <div className="hub-card-title">{c.title}</div>
            <div className="hub-card-desc">{c.desc}</div>
          </Link>
        ))}
      </div>
    </>
  )
}
