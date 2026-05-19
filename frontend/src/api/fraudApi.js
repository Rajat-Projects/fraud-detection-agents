const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const analyzeTransaction = async (transactionInput, apiKey = 'demo-key-001') => {
  const response = await fetch(`${API_URL}/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transaction_input: transactionInput, api_key: apiKey }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Analysis failed')
  }

  return response.json()
}

export const checkHealth = async () => {
  const response = await fetch(`${API_URL}/v1/health`)
  return response.json()
}
