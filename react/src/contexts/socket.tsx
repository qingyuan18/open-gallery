import { socketManager } from '@/lib/socket'
import React, { createContext, useEffect, useState } from 'react'

interface SocketContextType {
  connected: boolean
  socketId?: string
  connecting: boolean
  error?: string
  isPolling: boolean
}

const SocketContext = createContext<SocketContextType>({
  connected: false,
  connecting: false,
  isPolling: false,
})

interface SocketProviderProps {
  children: React.ReactNode
}

export const SocketProvider: React.FC<SocketProviderProps> = ({ children }) => {
  const [connected, setConnected] = useState(false)
  const [socketId, setSocketId] = useState<string>()
  const [connecting, setConnecting] = useState(true)
  const [error, setError] = useState<string>()
  const [isPolling, setIsPolling] = useState(false)

  useEffect(() => {
    let mounted = true

    const initializeSocket = async () => {
      try {
        setConnecting(true)
        setError(undefined)

        await socketManager.connect()

        if (mounted) {
          setConnected(true)
          setSocketId(socketManager.getSocketId())
          setConnecting(false)
          console.log('🚀 Socket.IO initialized successfully')

          const socket = socketManager.getSocket()
          if (socket) {
            const handleConnect = () => {
              if (mounted) {
                setConnected(true)
                setSocketId(socketManager.getSocketId())
                setConnecting(false)
                setError(undefined)
              }
            }

            const handleDisconnect = () => {
              if (mounted) {
                setConnected(false)
                setSocketId(undefined)
                setConnecting(false)
              }
            }

            const handleConnectError = (error: Error) => {
              if (mounted) {
                setError(error.message || 'Connection error')
                setConnected(false)
                setConnecting(false)
              }
            }

            socket.on('connect', handleConnect)
            socket.on('disconnect', handleDisconnect)
            socket.on('connect_error', handleConnectError)

            return () => {
              socket.off('connect', handleConnect)
              socket.off('disconnect', handleDisconnect)
              socket.off('connect_error', handleConnectError)
            }
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          setConnected(false)
          setConnecting(false)
          console.error('❌ Failed to initialize Socket.IO:', err)
        }
      }
    }

    initializeSocket()

    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    console.log('📢 Notification manager initialized')

    // 定期检查轮询状态
    const checkPollingStatus = () => {
      setIsPolling(socketManager.isPolling())
    }

    const interval = setInterval(checkPollingStatus, 1000)

    return () => {
      clearInterval(interval)
    }
  }, [])

  const value: SocketContextType = {
    connected,
    socketId,
    connecting,
    error,
    isPolling,
  }

  return (
    <SocketContext.Provider value={value}>
      {children}

      {error && (
        <div className="fixed top-4 right-4 z-50 bg-red-500 text-white px-3 py-2 rounded-md shadow-lg">
          Connection error: {error}
        </div>
      )}

      {isPolling && !connected && (
        <div className="fixed top-4 right-4 z-50 bg-yellow-500 text-white px-3 py-2 rounded-md shadow-lg">
          🔄 Using HTTP polling mode (WebSocket unavailable)
        </div>
      )}
    </SocketContext.Provider>
  )
}
