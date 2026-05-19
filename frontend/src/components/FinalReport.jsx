export default function FinalReport({ finalReport }) {
  if (!finalReport || Object.keys(finalReport).length === 0) return null

  const summary   = finalReport.executive_summary || finalReport.transaction_summary || ''
  const findings  = finalReport.key_findings || []
  const questions = finalReport.analyst_questions || []
  const steps     = finalReport.next_steps || []
  const rel       = finalReport.reliability || ''
  const missing   = finalReport.missing_analysis || []
  const action    = finalReport.recommended_action || ''

  const relColor = rel === 'COMPLETE' ? '#4ade80' : rel === 'DEGRADED' ? '#facc15' : '#f87171'

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
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>📋</span>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Agent 6 — Final Analyst Report
          </span>
          <span style={{ marginLeft: '0.25rem', fontSize: '0.72rem', color: '#6366f1', fontStyle: 'italic' }}>
            60-Second Summary
          </span>
        </div>

        {rel && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            fontSize: '0.72rem', fontWeight: 600, color: relColor,
            background: `${relColor}15`, border: `1px solid ${relColor}30`,
            padding: '0.2rem 0.6rem', borderRadius: 6,
          }}>
            {rel === 'COMPLETE' ? '✓' : '⚠'} {rel}
          </div>
        )}
      </div>

      <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>

        {/* Executive summary */}
        {summary && (
          <div style={{
            background: 'rgba(99,102,241,0.05)',
            borderLeft: '3px solid #6366f1',
            borderRadius: '0 8px 8px 0',
            padding: '0.875rem 1rem',
          }}>
            <div style={{ fontSize: '0.65rem', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.4rem' }}>
              Executive Summary
            </div>
            <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: 1.7, margin: 0 }}>{summary}</p>
          </div>
        )}

        {/* Two-column: findings + next steps */}
        {(findings.length > 0 || steps.length > 0) && (
          <div style={{ display: 'grid', gridTemplateColumns: steps.length > 0 ? '1fr 1fr' : '1fr', gap: '1rem' }}>

            {findings.length > 0 && (
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
                  Key Findings
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  {findings.map((f, i) => (
                    <div key={i} style={{
                      display: 'flex', gap: '0.5rem', fontSize: '0.8rem', color: '#94a3b8',
                      padding: '0.35rem 0.6rem', background: 'rgba(96,165,250,0.04)',
                      border: '1px solid rgba(96,165,250,0.1)', borderRadius: 6,
                    }}>
                      <span style={{ color: '#6366f1', fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
                      <span>{f}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {steps.length > 0 && (
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
                  Next Steps
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  {steps.map((s, i) => (
                    <div key={i} style={{
                      display: 'flex', gap: '0.5rem', fontSize: '0.8rem', color: '#94a3b8',
                      padding: '0.35rem 0.6rem', background: 'rgba(167,139,250,0.04)',
                      border: '1px solid rgba(167,139,250,0.1)', borderRadius: 6,
                    }}>
                      <span style={{ color: '#a78bfa', flexShrink: 0 }}>→</span>
                      <span>{s}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Analyst questions */}
        {questions.length > 0 && (
          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#facc15', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
              ❓ Questions for Analyst Review
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {questions.map((q, i) => (
                <div key={i} style={{
                  padding: '0.5rem 0.875rem',
                  background: 'rgba(250,204,21,0.04)',
                  borderLeft: '2px solid rgba(250,204,21,0.4)',
                  borderRadius: '0 6px 6px 0',
                  fontSize: '0.82rem', color: '#e2e8f0',
                }}>
                  {q}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Degraded reliability warning */}
        {rel && rel !== 'COMPLETE' && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
            background: `${relColor}10`, border: `1px solid ${relColor}30`,
            borderRadius: 8, padding: '0.75rem',
          }}>
            <span style={{ fontSize: '1rem', flexShrink: 0 }}>⚠️</span>
            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: relColor }}>
                Reliability: {rel} — Human review strongly recommended
              </div>
              {missing.length > 0 && (
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>
                  Missing analysis from: {missing.join(', ')}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
