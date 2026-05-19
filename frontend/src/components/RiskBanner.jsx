export default function RiskBanner({ result }) {
  const level       = result?.final_risk_level || ''
  const score       = result?.final_risk_score ?? 0
  const action      = result?.final_report?.recommended_action || 'REVIEW'
  const reliability = result?.final_report?.reliability || 'UNKNOWN'

  const levelConfig = {
    LOW:    { class: 'badge-low',    emoji: '✅', accent: '#4ade80', bg: 'rgba(5,46,22,0.3)' },
    MEDIUM: { class: 'badge-medium', emoji: '⚠️', accent: '#facc15', bg: 'rgba(28,21,2,0.3)' },
    HIGH:   { class: 'badge-high',   emoji: '🚨', accent: '#f87171', bg: 'rgba(28,5,5,0.3)'  },
  }
  const cfg = levelConfig[level] || levelConfig.MEDIUM
  const relColor = reliability === 'COMPLETE' ? '#4ade80' : '#facc15'

  return (
    <div style={{
      background: cfg.bg,
      border: `1px solid ${cfg.accent}30`,
      borderLeft: `4px solid ${cfg.accent}`,
      borderRadius: 16,
      padding: '1.5rem',
      boxShadow: `0 0 40px ${cfg.accent}10`,
    }}>
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
        Analysis Complete
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

        <div className="metric-card" style={{ '--accent-color': cfg.accent }}>
          <div className="metric-label">Risk Level</div>
          <div className="mt-1"><span className={cfg.class}>{cfg.emoji} {level}</span></div>
        </div>

        <div className="metric-card" style={{ '--accent-color': cfg.accent }}>
          <div className="metric-label">Risk Score</div>
          <div className="metric-value" style={{ color: cfg.accent }}>
            {score}<span style={{ fontSize: '1rem', color: '#475569' }}>/100</span>
          </div>
        </div>

        <div className="metric-card" style={{ '--accent-color': '#6366f1' }}>
          <div className="metric-label">Action</div>
          <div className="metric-value" style={{ fontSize: '1.1rem' }}>{action}</div>
        </div>

        <div className="metric-card" style={{ '--accent-color': relColor }}>
          <div className="metric-label">Reliability</div>
          <div className="metric-value" style={{ fontSize: '1rem', color: relColor }}>{reliability}</div>
        </div>
      </div>
    </div>
  )
}
