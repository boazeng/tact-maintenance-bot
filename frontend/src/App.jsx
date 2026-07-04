import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import TactLogo from './components/TactLogo.jsx'
import HomePage from './pages/HomePage.jsx'
import BotFlowEditorPage from './pages/BotFlowEditor/BotFlowEditorPage.jsx'
import BotDiagnosticsPage from './pages/BotDiagnosticsPage.jsx'
import BotTesterPage from './pages/BotTester/BotTesterPage.jsx'

const NAV = [
  { to: '/', label: 'דף הבית', end: true },
  { to: '/editor', label: 'עורך זרימה' },
  { to: '/tester', label: 'בודק שיחות' },
  { to: '/diagnostics', label: 'אבחון שיחות' },
]

export default function App() {
  const location = useLocation()
  // The flow editor and the chat tester both need the full locked viewport.
  const fullBleed = location.pathname.startsWith('/editor') || location.pathname.startsWith('/tester')

  return (
    <div className={`tact-aurora app-shell${fullBleed ? ' app-shell--editor' : ''}`}>
      <header className="tact-bar">
        <NavLink to="/" className="brand">
          <TactLogo size={1.4} word="bots" />
        </NavLink>
        <nav className="tact-nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {fullBleed ? (
        <Routes>
          <Route path="/editor" element={<BotFlowEditorPage />} />
          <Route path="/tester" element={<BotTesterPage />} />
        </Routes>
      ) : (
        <main className="app-main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/diagnostics" element={<BotDiagnosticsPage />} />
          </Routes>
        </main>
      )}
    </div>
  )
}
