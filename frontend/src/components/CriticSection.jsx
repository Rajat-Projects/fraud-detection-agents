import { useState } from 'react'

const VERDICT_CONFIG = {
  OVERTURNED: { class: 'verdict-overturned', emoji: '🔄', label: 'OVERTURNED', subtitle: 'Strong innocent explanation found',    scoreColor: '#4ade80' },
  UPHELD:     { class: 'verdict-upheld',     emoji: '✅', label: 'UPHELD',     subtitle: 'No innocent explanation found',         scoreColor: '#60a5fa' },
  MODIFIED:   { class: 'verdict-modified',   emoji: '📝', label: 'MODIFIED',   subtitle: 'Partial explanation — score adjusted',  scoreColor: '#facc15' },
  ESCALATED:  { class: 'verdict-escalated',  emoji: '⬆️', label: 'ESCALATED', subtitle: 'New concerns found — score increased',  scoreColor: '#f87171' },
}

export default function CriticSection({ criticReview, originalScore, finalScore }) {
  const [reasoningOpen, setReasoningOpen] = useState(false)

  if (!criticReview?.verdict) return null

  const verdict  = criticReview.verdict
  const original = criticReview.original_score ?? originalScore
  const revised  = criticReview.revised_score  ?? finalScore
  const scoreDiff = revised - original
  const constitutionalApplied = criticReview.reasoning?.includes('Constitutional policy')
  const vc = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.UPHELD

  const toList = v => Array.isArray(v) ? v : (v ? [v] : [])

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
        <span>🔄</span>
        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Agent 5 — Critic Agent
        </span>
        <span style={{ marginLeft: '0.25rem', fontSize: '0.72rem', color: '#6366f1', fontStyle: 'italic' }}>
          Challenge &amp; Debate
        </span>
      </div>

      <div style={{ padding: '1.25rem' }}>

        {/* Verdict banner */}
        <div className={vc.class}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                {vc.emoji} {vc.label}
              </div>
              <div style={{ fontSize: '0.8rem', opacity: 0.7, marginTop: '0.2rem' }}>{vc.subtitle}</div>
            </div>

            {/* Score change visualization */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              background: 'rgba(0,0,0,0.2)', padding: '0.75rem 1.25rem', borderRadius: 10,
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.65rem', opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Original</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, textDecoration: scoreDiff !== 0 ? 'line-through' : 'none', opacity: scoreDiff !== 0 ? 0.5 : 1 }}>
                  {original}
                </div>
              </div>
              <div style={{ fontSize: '1.2rem', opacity: 0.5 }}>→</div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '0.65rem', opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Final</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: vc.scoreColor }}>{revised}</div>
              </div>
              {scoreDiff !== 0 && (
                <div style={{
                  fontSize: '0.8rem', fontWeight: 600,
                  color: scoreDiff < 0 ? '#4ade80' : '#f87171',
                  background: scoreDiff < 0 ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)',
                  padding: '0.2rem 0.5rem', borderRadius: 6,
                }}>
                  {scoreDiff > 0 ? '+' : ''}{scoreDiff}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Constitutional policy note */}
        {constitutionalApplied && (
          <div style={{
            marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem',
            background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
            borderRadius: 8, padding: '0.5rem 0.75rem', fontSize: '0.78rem', color: '#a78bfa',
          }}>
            ⚖️ Constitutional policy applied — score floor at 50
          </div>
        )}

        {/* Two-column: explanations + concerns */}
        {(toList(criticReview.innocent_explanations).length > 0 || toList(criticReview.remaining_concerns).length > 0) && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            {toList(criticReview.innocent_explanations).length > 0 && (
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#4ade80', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
                  ✓ Innocent Explanations
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {toList(criticReview.innocent_explanations).map((exp, i) => (
                    <div key={i} style={{ fontSize: '0.8rem', color: '#94a3b8', padding: '0.4rem 0.6rem', background: 'rgba(74,222,128,0.05)', border: '1px solid rgba(74,222,128,0.1)', borderRadius: 6, display: 'flex', gap: '0.5rem' }}>
                      <span style={{ color: '#4ade80' }}>•</span>{exp}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {toList(criticReview.remaining_concerns).length > 0 && (
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#facc15', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
                  ⚠ Remaining Concerns
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {toList(criticReview.remaining_concerns).map((concern, i) => (
                    <div key={i} style={{ fontSize: '0.8rem', color: '#94a3b8', padding: '0.4rem 0.6rem', background: 'rgba(250,204,21,0.05)', border: '1px solid rgba(250,204,21,0.1)', borderRadius: 6, display: 'flex', gap: '0.5rem' }}>
                      <span style={{ color: '#facc15' }}>•</span>{concern}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Confidence + expandable reasoning */}
        <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          {criticReview.confidence_in_challenge != null && (
            <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
              Confidence in challenge:{' '}
              <span style={{ color: '#a78bfa', fontWeight: 600 }}>{criticReview.confidence_in_challenge}%</span>
            </div>
          )}
          {criticReview.reasoning && (
            <button
              onClick={() => setReasoningOpen(!reasoningOpen)}
              style={{ fontSize: '0.78rem', color: '#6366f1', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)', padding: '0.3rem 0.75rem', borderRadius: 6, cursor: 'pointer' }}
            >
              {reasoningOpen ? '▲' : '▼'} Critic Reasoning
            </button>
          )}
        </div>

        {reasoningOpen && criticReview.reasoning && (
          <div style={{ marginTop: '0.75rem', padding: '0.875rem', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: '0.825rem', color: '#94a3b8', lineHeight: 1.7 }}>
            {criticReview.reasoning}
          </div>
        )}
      </div>
    </div>
  )
}
