import React, { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog'
import { startDeviceAuth, pollDeviceAuth, saveAuthData } from '../../api/auth'
import { updateJaazApiKey } from '../../api/config'
import { useAuth } from '../../contexts/AuthContext'
import { useConfigs, useRefreshModels } from '../../contexts/configs'

export function LoginDialog() {
  const [authMessage, setAuthMessage] = useState('')
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })
  const [registerForm, setRegisterForm] = useState({ username: '', email: '', password: '' })
  const [isLoading, setIsLoading] = useState(false)
  const { refreshAuth } = useAuth()
  const { showLoginDialog: open, setShowLoginDialog } = useConfigs()
  const refreshModels = useRefreshModels()
  const { t } = useTranslation()
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Clean up polling when dialog closes
  useEffect(() => {
    setAuthMessage('')

    if (!open) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [open])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
      }
    }
  }, [])

  const startPolling = (code: string) => {
    console.log('Starting polling for device code:', code)

    const poll = async () => {
      try {
        const result = await pollDeviceAuth(code)
        console.log('Poll result:', result)

        if (result.status === 'authorized') {
          // Login successful - save auth data to local storage
          if (result.token && result.user_info) {
            saveAuthData(result.token, result.user_info)

            // Update jaaz provider api_key with the access token
            await updateJaazApiKey(result.token)
          }

          setAuthMessage(t('common:auth.loginSuccessMessage'))
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }

          try {
            await refreshAuth()
            console.log('Auth status refreshed successfully')
            // Refresh models list after successful login and config update
            refreshModels()
          } catch (error) {
            console.error('Failed to refresh auth status:', error)
          }

          setTimeout(() => setShowLoginDialog(false), 1500)

        } else if (result.status === 'expired') {
          // Authorization expired
          setAuthMessage(t('common:auth.authExpiredMessage'))
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }

        } else if (result.status === 'error') {
          // Error occurred
          setAuthMessage(result.message || t('common:auth.authErrorMessage'))
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }

        } else {
          // Still pending, continue polling
          setAuthMessage(t('common:auth.waitingForBrowser'))
        }
      } catch (error) {
        console.error('Polling error:', error)
        setAuthMessage(t('common:auth.pollErrorMessage'))
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
      }
    }

    // Start polling immediately, then every 1 seconds
    poll()
    pollingIntervalRef.current = setInterval(poll, 1000)
  }

  const handleUsernameLogin = async () => {
    try {
      setIsLoading(true)
      setAuthMessage('')

      if (!loginForm.username || !loginForm.password) {
        setAuthMessage('Please enter username and password')
        return
      }

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      })

      const result = await response.json()

      if (response.ok && result.status === 'success') {
        // Save auth data to local storage
        saveAuthData(result.token, result.user_info)

        // Update jaaz provider api_key with the access token
        await updateJaazApiKey(result.token)

        setAuthMessage('Login successful!')

        // Refresh auth status
        await refreshAuth()
        refreshModels()

        setTimeout(() => setShowLoginDialog(false), 1500)
      } else {
        setAuthMessage(result.detail || 'Login failed')
      }

    } catch (error) {
      console.error('Login failed:', error)
      setAuthMessage('Login failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleRegister = async () => {
    try {
      setIsLoading(true)
      setAuthMessage('')

      if (!registerForm.username || !registerForm.email || !registerForm.password) {
        setAuthMessage('Please fill in all fields')
        return
      }

      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(registerForm)
      })

      const result = await response.json()

      if (response.ok && result.status === 'success') {
        setAuthMessage('Registration successful! You can now login.')
        // Clear register form
        setRegisterForm({ username: '', email: '', password: '' })
      } else {
        setAuthMessage(result.detail || 'Registration failed')
      }

    } catch (error) {
      console.error('Registration failed:', error)
      setAuthMessage('Registration failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeviceLogin = async () => {
    try {
      setAuthMessage(t('common:auth.preparingLoginMessage'))

      const result = await startDeviceAuth()
      setAuthMessage(result.message)

      // Start polling for authorization status
      startPolling(result.code)

    } catch (error) {
      console.error('登录请求失败:', error)
      setAuthMessage(t('common:auth.loginRequestFailed'))
    }
  }

  const handleCancel = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
    setAuthMessage('')
    setShowLoginDialog(false)
  }

  return (
    <Dialog open={open} onOpenChange={setShowLoginDialog}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Login to Jaaz</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="username" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="username">Username/Password</TabsTrigger>
            <TabsTrigger value="device">Device Auth</TabsTrigger>
          </TabsList>

          <TabsContent value="username" className="space-y-4">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  type="text"
                  placeholder="Enter username"
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                  disabled={isLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter password"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                  disabled={isLoading}
                  onKeyPress={(e) => e.key === 'Enter' && handleUsernameLogin()}
                />
              </div>
              <Button
                onClick={handleUsernameLogin}
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? 'Logging in...' : 'Login'}
              </Button>


            </div>
          </TabsContent>

          <TabsContent value="device" className="space-y-4">
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {t('common:auth.loginDescription')}
              </p>
              <Button
                onClick={handleDeviceLogin}
                disabled={!!authMessage}
                className="w-full"
              >
                {authMessage || t('common:auth.startLogin')}
              </Button>
            </div>
          </TabsContent>
        </Tabs>

        {authMessage && (
          <div className={`text-sm p-3 rounded-md ${
            authMessage.includes('successful') || authMessage.includes('✅')
              ? 'bg-green-50 text-green-700'
              : authMessage.includes('failed') || authMessage.includes('❌')
              ? 'bg-red-50 text-red-700'
              : 'bg-blue-50 text-blue-700'
          }`}>
            {authMessage}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
