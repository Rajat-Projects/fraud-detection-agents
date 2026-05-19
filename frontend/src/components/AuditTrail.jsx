export default function AuditTrail({ checkpoints, agentStatuses }) {
  const hasCheckpoints = checkpoints && Object.keys(checkpoints).length > 0
  const hasStatuses    = agentStatuses && Object.keys(agentStatuses).length > 0

  if (!hasCheckpoints && !hasStatuses) return null

  const statusColor = { SUCCESS: '#4ade80', FALLBACK: '#facc15', FAILED: '#f87171' }

  return (
    <div style={{
      background: 'linear-gradient(145deg, #0d1117, #161b27)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 16,
      overflow: 'hidden',
      boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
    }}>
      {/* Section header */}
      <div style={{
        background: 'rgba(99,102,241,0.06)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        padding: '0.875rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
      }}>
        <span>🔐</span>
        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Audit Trail
        </span>
        <span style={{ marginLeft: '0.25rem', fontSize: '0.72rem', color: '#6366f1', fontStyle: 'italic' }}>
          SHA-256 State Checkpoints
        </span>
      </div>

      <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>

        {/* Cryptographic checkpoints */}
        {hasCheckpoints && (
          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
              Tamper-Evident State Hashes
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {Object.entries(checkpoints).map(([agent, hash]) => (
                <div key={agent} style={{
                  display: 'flex', alignItems: 'center', gap: '1rem',
                  background: 'rgba(0,0,0,0.25)', borderRadius: 8,
                  padding: '0.5rem 0.875rem',
                  fontFamily: 'JetBrains Mono, Fira Code, monospace',
                }}>
                  <span style={{ fontSize: '0.75rem', color: '#6366f1', minWidth: 180, flexShrink: 0 }}>
                    {agent}
                  </span>
                  <span style={{ fontSize: '0.72rem', color: '#334155', letterSpacing: '0.04em' }}>
                    {hash.slice(0, 40)}...
                  </span>
                </div>
              ))}
            </div>
            <p style={{ fontSize: '0.72rem', color: '#334155', marginTop: '0.5rem', lineHeight: 1.5 }}>
              Each hash is computed from full pipeline state after that agent ran. Any post-hoc modification changes the hash — tamper-evident record of every agent's contribution.
            </p>
          </div>
        )}

        {/* Agent status grid */}
        {hasStatuses && (
          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
              Agent Status Summary
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem' }}>
              {Object.entries(agentStatuses).map(([agent, status]) => {
                const color = statusColor[status] || '#6366f1'
                return (
                  <div key={agent} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: 'rgba(0,0,0,0.2)', borderRadius: 6, padding: '0.4rem 0.75rem',
                  }}>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {agent.replace(/_/g, ' ')}
                    </span>
                    <span style={{
                      fontSize: '0.68rem', fontWeight: 700, padding: '0.1rem 0.45rem', borderRadius: 4,
                      background: `${color}15`, border: `1px solid ${color}30`, color,
                    }}>
                      {status}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
