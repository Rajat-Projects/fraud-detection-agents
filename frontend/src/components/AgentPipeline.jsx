import AgentCard from './AgentCard'

/* ── Shared primitives ───────────────────────────────────────────────────── */

function DataRow({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.825rem', marginBottom: '0.35rem' }}>
      <span style={{ color: '#475569', minWidth: 130, flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#cbd5e1' }}>{String(value)}</span>
    </div>
  )
}

function Chip({ text, color = '#6366f1' }) {
  return (
    <span style={{
      fontSize: '0.68rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: 4,
      background: `${color}22`, border: `1px solid ${color}44`, color,
      textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>
      {text}
    </span>
  )
}

function ScoreBar({ value }) {
  const pct = Math.min(100, Math.max(0, value))
  const color = pct >= 70 ? '#f87171' : pct >= 40 ? '#facc15' : '#4ade80'
  return (
    <div style={{ width: '100%', background: 'rgba(255,255,255,0.05)', borderRadius: 4, height: 6, marginTop: '0.5rem' }}>
      <div style={{ width: `${pct}%`, height: 6, borderRadius: 4, background: color, transition: 'width 0.6s ease' }} />
    </div>
  )
}

function InnerBox({ children, color }) {
  return (
    <div style={{
      background: color ? `${color}08` : 'rgba(255,255,255,0.02)',
      border: `1px solid ${color ? color + '20' : 'rgba(255,255,255,0.06)'}`,
      borderRadius: 8,
      padding: '0.75rem',
      fontSize: '0.825rem',
    }}>
      {children}
    </div>
  )
}

/* ── Agent 1: Transaction Analyzer ──────────────────────────────────────── */
function TransactionAnalyzer({ tx }) {
  if (!tx?.amount) return (
    <p style={{ fontSize: '0.825rem', color: '#475569', fontStyle: 'italic' }}>No transaction data</p>
  )

  const location = [tx.location_city, tx.location_country].filter(Boolean).join(', ')

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem 1.5rem' }}>
      <DataRow label="Amount"   value={`${tx.amount} ${tx.currency || ''}`.trim()} />
      <DataRow label="Merchant" value={tx.merchant_name} />
      <DataRow label="Category" value={tx.merchant_category} />
      <DataRow label="Location" value={location || undefined} />
      <DataRow label="Time"     value={tx.transaction_time || tx.transaction_timestamp} />
      <DataRow label="Channel"  value={tx.channel} />
      {tx.data_source && (
        <div style={{ gridColumn: 'span 2', marginTop: '0.5rem' }}>
          <Chip text={tx.data_source} color="#60a5fa" />
        </div>
      )}
      {tx.missing_fields?.length > 0 && (
        <div style={{ gridColumn: 'span 2', fontSize: '0.75rem', color: '#475569', marginTop: '0.35rem' }}>
          Inferred fields: {tx.missing_fields.join(', ')}
        </div>
      )}
    </div>
  )
}

/* ── Agent 2: Anomaly Detection ──────────────────────────────────────────── */
function AnomalyDetection({ anomaly }) {
  if (!anomaly) return null

  const flags = anomaly.anomalies_detected || anomaly.anomaly_flags || []
  const flagList = Array.isArray(flags) && flags.length > 0 && typeof flags[0] === 'object' ? flags : []
  const sevColor = { CRITICAL: '#f87171', HIGH: '#f87171', MEDIUM: '#facc15', LOW: '#4ade80' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
        {[
          { label: 'Anomalies',  value: flagList.length > 0 ? '⚠️ Detected' : '✅ None' },
          { label: 'Severity',   value: `${anomaly.severity_score ?? 0}/100` },
          { label: 'Confidence', value: `${anomaly.confidence ?? 0}%` },
        ].map(m => (
          <div key={m.label} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '0.6rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.65rem', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{m.label}</div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#e2e8f0', marginTop: '0.25rem' }}>{m.value}</div>
          </div>
        ))}
      </div>

      {anomaly.severity_score > 0 && <ScoreBar value={anomaly.severity_score} />}

      {flagList.map((f, i) => (
        <InnerBox key={i} color={sevColor[f.severity]}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <Chip text={f.severity || 'UNKNOWN'} color={sevColor[f.severity] || '#6366f1'} />
            <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.8rem' }}>
              {(f.dimension || f.anomaly_type || '').toUpperCase()}
            </span>
          </div>
          <p style={{ color: '#94a3b8', margin: 0 }}>{f.description}</p>
          {f.evidence && <p style={{ color: '#475569', fontSize: '0.75rem', marginTop: '0.3rem' }}>{f.evidence}</p>}
        </InnerBox>
      ))}

      {anomaly.behavioral_summary && (
        <InnerBox>
          <p style={{ color: '#94a3b8', margin: 0 }}>{anomaly.behavioral_summary}</p>
        </InnerBox>
      )}
    </div>
  )
}

/* ── Agent 3: Rule Enforcement ───────────────────────────────────────────── */
function RuleEnforcement({ rules }) {
  if (!rules) return null

  const violations = rules.violations || []
  const sevColor = { MANDATORY_ESCALATION: '#f87171', MANDATORY_REVIEW: '#f87171', ADVISORY: '#facc15' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
        {[
          { label: 'Rules Checked', value: rules.rules_checked ?? 0 },
          { label: 'Violations',    value: rules.violations_found ?? violations.length },
          { label: 'Source',        value: rules.source || '—' },
        ].map(m => (
          <div key={m.label} style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '0.6rem', textAlign: 'center' }}>
            <div style={{ fontSize: '0.65rem', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{m.label}</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#e2e8f0', marginTop: '0.25rem' }}>{m.value}</div>
          </div>
        ))}
      </div>

      {violations.length === 0 ? (
        <InnerBox color="#4ade80">
          <span style={{ color: '#4ade80', fontSize: '0.825rem' }}>✅ No rule violations detected</span>
        </InnerBox>
      ) : violations.map((v, i) => (
        <InnerBox key={i} color={sevColor[v.severity] || '#f87171'}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <Chip text={v.severity} color={sevColor[v.severity] || '#f87171'} />
            <span style={{ fontWeight: 600, color: '#fca5a5', fontSize: '0.8rem' }}>{v.rule_name}</span>
          </div>
          <p style={{ color: '#94a3b8', margin: 0 }}>{v.description}</p>
          {v.evidence && <p style={{ color: '#475569', fontSize: '0.75rem', marginTop: '0.3rem' }}>Evidence: {v.evidence}</p>}
        </InnerBox>
      ))}
    </div>
  )
}

/* ── Agent 4: Risk Scoring ───────────────────────────────────────────────── */
function RiskScoring({ result }) {
  const score   = result.risk_score ?? 0
  const level   = result.risk_level || ''
  const reasoning = result.risk_reasoning || ''
  const levelColor = { LOW: '#4ade80', MEDIUM: '#facc15', HIGH: '#f87171' }
  const color = levelColor[level] || '#94a3b8'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ fontSize: '3rem', fontWeight: 800, color, lineHeight: 1 }}>{score}</div>
        <div>
          <div style={{ fontSize: '0.65rem', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Initial Score</div>
          <div style={{ fontSize: '1rem', fontWeight: 700, color }}>{level}</div>
        </div>
      </div>
      <ScoreBar value={score} />
      {reasoning && (
        <InnerBox>
          <p style={{ color: '#94a3b8', margin: 0, lineHeight: 1.7 }}>{reasoning}</p>
        </InnerBox>
      )}
    </div>
  )
}

/* ── Agent 6: Execution summary ──────────────────────────────────────────── */
function ExecutionSummary({ agentStatuses }) {
  if (!agentStatuses || Object.keys(agentStatuses).length === 0) return null

  const statusColor = { SUCCESS: '#4ade80', FALLBACK: '#facc15', FAILED: '#f87171' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ fontSize: '0.72rem', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.25rem' }}>
        Agent Execution Summary
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem' }}>
        {Object.entries(agentStatuses).map(([agent, status]) => (
          <div key={agent} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: 'rgba(0,0,0,0.2)', borderRadius: 6, padding: '0.4rem 0.75rem',
          }}>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{agent.replace(/_/g, ' ')}</span>
            <span style={{
              fontSize: '0.68rem', fontWeight: 700, padding: '0.1rem 0.4rem', borderRadius: 4,
              background: `${statusColor[status] || '#6366f1'}22`,
              border: `1px solid ${statusColor[status] || '#6366f1'}44`,
              color: statusColor[status] || '#94a3b8',
            }}>
              {status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Main ────────────────────────────────────────────────────────────────── */
export default function AgentPipeline({ result }) {
  const tx      = result.structured_transaction || {}
  const anomaly = result.anomaly_report || {}
  const rules   = result.rule_violations || {}

  return (
    <div>
      <AgentCard
        title="Agent 1 — Transaction Analyzer"
        icon="📊"
        subtitle="Input Structuring"
        isAvailable={!!tx.amount}
        defaultOpen
      >
        <TransactionAnalyzer tx={tx} />
      </AgentCard>

      <AgentCard
        title="Agent 2 — Anomaly Detection"
        icon="🔎"
        subtitle="Behavioral Pattern Analysis"
        isAvailable={anomaly.severity_score != null}
        defaultOpen
      >
        <AnomalyDetection anomaly={anomaly} />
      </AgentCard>

      <AgentCard
        title="Agent 3 — Rule Enforcement"
        icon="⚖️"
        subtitle="Deterministic Compliance"
        tag="NO LLM"
        isAvailable={rules.rules_checked != null}
        defaultOpen
      >
        <RuleEnforcement rules={rules} />
      </AgentCard>

      <AgentCard
        title="Agent 4 — Risk Scoring"
        icon="📈"
        subtitle="Multi-Signal Synthesis"
        isAvailable={result.risk_score != null}
        defaultOpen
      >
        <RiskScoring result={result} />
      </AgentCard>

      <AgentCard
        title="Agent 6 — Report Generator"
        icon="📋"
        subtitle="60-Second Analyst Summary"
        isAvailable={!!result.agent_statuses}
      >
        <ExecutionSummary agentStatuses={result.agent_statuses} />
      </AgentCard>
    </div>
  )
}
