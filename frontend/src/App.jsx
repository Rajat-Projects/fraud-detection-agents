import { useState, useEffect } from 'react'
import { analyzeTransaction, checkHealth } from './api/fraudApi'
import Header from './components/Header'
import InputPanel from './components/InputPanel'
import RiskBanner from './components/RiskBanner'
import AgentPipeline from './components/AgentPipeline'
import CriticSection from './components/CriticSection'
import FinalReport from './components/FinalReport'
import AuditTrail from './components/AuditTrail'
import './index.css'

export default function App() {
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [backendStatus, setBackendStatus] = useState('connecting')

  useEffect(() => {
    checkHealth()
      .then(() => setBackendStatus('ready'))
      .catch(() => setBackendStatus('error'))
  }, [])

  const handleAnalyze = async (input) => {
    setIsLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await analyzeTransaction(input)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const isPipelineHalted = result?.pipeline_halted

  return (
    <div className="min-h-screen" style={{ background: '#070b14' }}>
      <div className="max-w-7xl mx-auto px-6 py-6">

        <Header backendStatus={backendStatus} />

        {/* Two-column layout: input + architecture */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-2">
            <InputPanel onAnalyze={handleAnalyze} isLoading={isLoading} />
          </div>
          <div className="lg:col-span-3">
            <PipelineArchitecture />
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mt-6 p-4 rounded-xl border border-red-800 text-red-400 text-sm animate-fade-in"
               style={{ background: 'rgba(28,5,5,0.6)' }}>
            ⚠️ {error}
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="mt-8 animate-fade-in">
            <LoadingPipeline />
          </div>
        )}

        {/* Results */}
        {result && !isLoading && (
          <div className="mt-8 space-y-5 animate-fade-in">
            {isPipelineHalted ? (
              <div className="security-halt-banner">
                <div className="text-2xl mb-2">🛑</div>
                <div className="font-bold text-lg">Pipeline Halted</div>
                <div className="text-sm opacity-80 mt-1">
                  Security violation detected. Transaction blocked pending review.
                </div>
              </div>
            ) : (
              <>
                <RiskBanner result={result} />
                <AgentPipeline result={result} />
                <CriticSection
                  criticReview={result.critic_review || {}}
                  originalScore={result.risk_score || 0}
                  finalScore={result.final_risk_score || 0}
                />
                <FinalReport finalReport={result.final_report || {}} />
                <AuditTrail
                  checkpoints={result.state_checkpoints || {}}
                  agentStatuses={result.agent_statuses || {}}
                />
              </>
            )}
          </div>
        )}

        <footer className="mt-12 pb-6 text-center">
          <p className="text-xs text-slate-600">
            ⚠️ AI-assisted analysis only. All decisions require human analyst review. No autonomous actions are taken.
          </p>
          <p className="text-xs text-slate-700 mt-1">
            FraudShield v1.0.0 · LangGraph + Gemini · Wipro WEGA FDE Assignment
          </p>
        </footer>
      </div>
    </div>
  )
}

/* ── Pipeline Architecture sidebar ──────────────────────────────────────── */
function PipelineArchitecture() {
  const steps = [
    { icon: '🔒', label: 'Guardrail',            desc: 'Injection & PII detection',    color: 'rgba(248,113,113,0.15)', border: 'rgba(248,113,113,0.3)' },
    { icon: '📊', label: 'Transaction Analyzer',  desc: 'Structures raw input',          color: 'rgba(99,102,241,0.15)',  border: 'rgba(99,102,241,0.3)' },
    { icon: '🔎', label: 'Anomaly Detection',     desc: 'Behavioral pattern analysis',   color: 'rgba(99,102,241,0.15)',  border: 'rgba(99,102,241,0.3)' },
    { icon: '⚖️', label: 'Rule Enforcement',      desc: 'Deterministic — No LLM',       color: 'rgba(250,204,21,0.15)', border: 'rgba(250,204,21,0.3)', tag: 'NO LLM' },
    { icon: '📈', label: 'Risk Scoring',          desc: 'Multi-signal synthesis',        color: 'rgba(99,102,241,0.15)',  border: 'rgba(99,102,241,0.3)' },
    { icon: '🔄', label: 'Critic Agent',          desc: 'Adversarial challenger',        color: 'rgba(74,222,128,0.15)', border: 'rgba(74,222,128,0.3)', tag: 'SHOWSTOPPER' },
    { icon: '📋', label: 'Report Generator',      desc: '60-second analyst report',      color: 'rgba(99,102,241,0.15)',  border: 'rgba(99,102,241,0.3)' },
  ]

  return (
    <div className="card h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Pipeline Architecture</h2>
        <span className="tag tag-purple">7 Agents</span>
      </div>

      <div className="space-y-1">
        {steps.map((step, i) => (
          <div key={i}>
            <div className="pipeline-step" style={{ background: step.color, borderColor: step.border }}>
              <div className="pipeline-step-icon" style={{ background: step.color, border: `1px solid ${step.border}` }}>
                {step.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-200">{step.label}</span>
                  {step.tag && (
                    <span className={`tag text-xs ${step.tag === 'NO LLM' ? 'tag-yellow' : 'tag-green'}`}>
                      {step.tag}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">{step.desc}</div>
              </div>
              {i < steps.length - 1 && <span className="text-slate-600 text-xs">↓</span>}
            </div>
            {i < steps.length - 1 && <div className="pipeline-connector" />}
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-white/5 grid grid-cols-2 gap-3">
        {[
          { title: 'Key Decisions', color: '#6366f1', items: ['Rule Enforcement has no LLM', 'Critic challenges every verdict', 'Score floor: 50 with violations'] },
          { title: 'Security Layers', color: '#4ade80', items: ['4-layer injection defence', 'PII tokenization at boundary', 'SHA-256 state checkpoints'] },
        ].map(({ title, color, items }) => (
          <div key={title}>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{title}</div>
            {items.map((d, i) => (
              <div key={i} className="text-xs text-slate-500 flex items-start gap-1.5 mb-1">
                <span style={{ color }} className="mt-0.5">•</span>{d}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Loading state with animated progress ────────────────────────────────── */
function LoadingPipeline() {
  const stages = [
    'Scanning for injection attempts...',
    'Structuring transaction data...',
    'Analyzing behavioral patterns...',
    'Checking compliance rules...',
    'Synthesizing risk signals...',
    'Critic challenging verdict...',
    'Generating analyst report...',
  ]
  const [currentStage, setCurrentStage] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStage(prev => prev < stages.length - 1 ? prev + 1 : prev)
    }, 6000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="card text-center py-10">
      <div className="flex justify-center mb-4">
        <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
      <div className="text-slate-300 font-medium mb-1">Running Multi-Agent Analysis</div>
      <div className="text-sm text-slate-500">{stages[currentStage]}</div>
      <div className="flex justify-center gap-1 mt-4">
        {stages.map((_, i) => (
          <div key={i} className="h-1 rounded-full transition-all duration-500"
               style={{ width: i <= currentStage ? 20 : 8, background: i <= currentStage ? '#6366f1' : '#1f2937' }} />
        ))}
      </div>
    </div>
  )
}
