import { useState, useEffect } from 'react'
import { getBalance, BalanceResponse } from '@/api/billing'
import { useAuth } from '@/contexts/AuthContext'

export function useBalance() {
  const [balance, setBalance] = useState<string>('0.00')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { authStatus } = useAuth()

  const fetchBalance = async () => {
    if (!authStatus.is_logged_in) {
      setBalance('0.00')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response: BalanceResponse = await getBalance()
      setBalance(response.balance)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch balance')
      console.error('Error fetching balance:', err)
    } finally {
      setLoading(false)
    }
  }

  return {
    balance,
    loading,
    error,
    refreshBalance: fetchBalance,
  }
}
