import { useState } from 'react'

const EXAMPLES = {
  suspicious: {
    label: '🚨 Suspicious Transaction',
    color: 'rgba(248,113,113,0.1)',
    border: 'rgba(248,113,113,0.25)',
    text: 'Transaction: 9500 dollars cash withdrawal at foreign ATM. Time: 3am local. Customer transacted in New York 2 hours ago. Distance from last transaction: 11000 km. Customer history: never withdrew more than 200 dollars cash, all transactions in home city for 3 years.',
  },
  legitimate: {
    label: '✅ Legitimate Transaction',
    color: 'rgba(74,222,128,0.1)',
    border: 'rgba(74,222,128,0.25)',
    text: 'Transaction: 47 dollars at regular grocery store. Location: customer home city New York. Time: Saturday 2pm. Customer history: weekly grocery purchase average 45 dollars, same store 2 years, no anomalies.',
  },
  falsePositive: {
    label: '🔄 False Positive — Traveler',
    color: 'rgba(250,204,21,0.1)',
    border: 'rgba(250,204,21,0.25)',
    text: 'Transaction: $3,200 USD jewelry store purchase.\nLocation: Paris, France. Time: 11:00 AM local.\nCard present: No (online/CNP).\nMerchant: Luxury Jewelers Paris.\n\nCustomer History:\n- Account age: 6 years, good standing\n- Annual Paris trip every June for 4 years\n- 3 prior jewelry purchases in Paris same merchant\n- Average transaction: $450\n- Home city: New York, USA\n- Last transaction: New York, 2 hours ago\n- Frequent international traveler',
  },
}

export default function InputPanel({ onAnalyze, isLoading }) {
  const [input, setInput] = useState('')

  return (
    <div className="card h-full flex flex-col gap-4">
      <div>
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Transaction Input
        </h2>
        <div className="space-y-2">
          {Object.entries(EXAMPLES).map(([key, ex]) => (
            <button
              key={key}
              className="btn-example"
              style={{
                background: input === ex.text ? ex.color : undefined,
                borderColor: input === ex.text ? ex.border : undefined,
                color: input === ex.text ? '#e2e8f0' : undefined,
              }}
              onClick={() => setInput(ex.text)}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Describe the transaction: amount, merchant, location, time, customer history..."
          style={{
            width: '100%',
            minHeight: 140,
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10,
            padding: '0.875rem',
            color: '#e2e8f0',
            fontSize: '0.875rem',
            lineHeight: 1.6,
            resize: 'vertical',
            outline: 'none',
            transition: 'border-color 0.2s',
            fontFamily: 'Inter, system-ui, sans-serif',
          }}
          onFocus={e => { e.target.style.borderColor = 'rgba(99,102,241,0.5)' }}
          onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.08)' }}
        />
      </div>

      <button
        className="btn-primary w-full flex items-center justify-center gap-2"
        onClick={() => input.trim() && onAnalyze(input)}
        disabled={isLoading || !input.trim()}
      >
        {isLoading ? (
          <><div className="spinner" /><span>Analyzing...</span></>
        ) : (
          <><span>🔍</span><span>Analyze Transaction</span></>
        )}
      </button>

      <p className="text-xs text-slate-600 text-center">
        Secured by 4-layer guardrails · No autonomous actions
      </p>
    </div>
  )
}
