import { useState } from 'react'

const AGENT_COLORS = {
  '📊': { accent: '#6366f1', bg: 'rgba(99,102,241,0.06)'  },
  '🔎': { accent: '#6366f1', bg: 'rgba(99,102,241,0.06)'  },
  '⚖️': { accent: '#facc15', bg: 'rgba(250,204,21,0.06)'  },
  '📈': { accent: '#6366f1', bg: 'rgba(99,102,241,0.06)'  },
  '📋': { accent: '#6366f1', bg: 'rgba(99,102,241,0.06)'  },
}

export default function AgentCard({ title, icon, subtitle, isAvailable = true, children, defaultOpen = false, tag }) {
  const [open, setOpen] = useState(defaultOpen)
  const colors = AGENT_COLORS[icon] || { accent: '#6366f1', bg: 'rgba(99,102,241,0.06)' }

  return (
    <div style={{
      background: 'linear-gradient(145deg, #0d1117, #161b27)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 16,
      overflow: 'hidden',
      boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
      marginBottom: '0.75rem',
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: colors.bg,
          borderBottom: open ? '1px solid rgba(255,255,255,0.05)' : 'none',
          padding: '0.875rem 1.25rem',
          cursor: 'pointer',
          border: 'none',
          outline: 'none',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>{icon}</span>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            {title}
          </span>
          {tag && (
            <span style={{
              fontSize: '0.62rem', fontWeight: 700, padding: '0.15rem 0.45rem', borderRadius: 4,
              background: tag === 'NO LLM' ? 'rgba(250,204,21,0.15)' : 'rgba(99,102,241,0.15)',
              border: `1px solid ${tag === 'NO LLM' ? 'rgba(250,204,21,0.3)' : 'rgba(99,102,241,0.3)'}`,
              color: tag === 'NO LLM' ? '#facc15' : '#a78bfa',
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              {tag}
            </span>
          )}
          {subtitle && (
            <span style={{ fontSize: '0.72rem', color: colors.accent, fontStyle: 'italic', marginLeft: '0.25rem' }}>
              {subtitle}
            </span>
          )}
        </div>
        <svg
          style={{ width: 14, height: 14, color: '#64748b', transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'rotate(0)' }}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div style={{ padding: '1.25rem' }}>
          {isAvailable ? children : (
            <p style={{ fontSize: '0.825rem', color: '#475569', fontStyle: 'italic' }}>
              Not available — agent did not run or was skipped
            </p>
          )}
        </div>
      )}
    </div>
  )
}
