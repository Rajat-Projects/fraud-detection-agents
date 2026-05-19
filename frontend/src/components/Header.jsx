export default function Header({ backendStatus }) {
  const statusConfig = {
    ready:      { dot: 'status-dot-ready',      text: 'Pipeline Ready',  color: '#4ade80' },
    connecting: { dot: 'status-dot-connecting', text: 'Connecting...',   color: '#facc15' },
    error:      { dot: 'status-dot-error',      text: 'Backend Offline', color: '#f87171' },
  }
  const s = statusConfig[backendStatus] || statusConfig.connecting

  return (
    <header style={{
      background: 'linear-gradient(135deg, #0d1117 0%, #161b27 100%)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderLeft: '3px solid #6366f1',
      borderRadius: 16,
      padding: '1.25rem 1.75rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      boxShadow: '0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)',
    }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '1.5rem' }}>🛡️</span>
          <span style={{ fontSize: '1.5rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.03em' }}>
            FraudShield
          </span>
          <span style={{
            background: 'rgba(99,102,241,0.15)',
            border: '1px solid rgba(99,102,241,0.3)',
            color: '#a78bfa',
            fontSize: '0.65rem',
            fontWeight: 600,
            padding: '0.15rem 0.5rem',
            borderRadius: 4,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}>
            v1.0.0
          </span>
        </div>
        <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.2rem', letterSpacing: '0.01em' }}>
          Multi-Agent Fraud Detection System · LangGraph + Gemini · 7 Specialized Agents
        </div>
      </div>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.07)',
        padding: '0.5rem 1rem',
        borderRadius: 8,
      }}>
        <div className={s.dot} />
        <span style={{ color: s.color, fontSize: '0.8rem', fontWeight: 500 }}>{s.text}</span>
      </div>
    </header>
  )
}
