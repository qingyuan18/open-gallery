import { BASE_API_URL } from '../constants'
import i18n from '../i18n'
import { clearJaazApiKey } from './config'

export interface AuthStatus {
  status: 'logged_out' | 'pending' | 'logged_in'
  is_logged_in: boolean
  user_info?: UserInfo
}

export interface UserInfo {
  id: string
  username: string
  email: string
  image_url?: string
  provider?: string
  created_at?: string
  updated_at?: string
}

export interface DeviceAuthResponse {
  status: string
  code: string
  expires_at: string
  message: string
}

export interface DeviceAuthPollResponse {
  status: 'pending' | 'authorized' | 'expired' | 'error'
  message?: string
  token?: string
  user_info?: UserInfo
}

export interface ApiResponse {
  status: string
  message: string
}

export async function startDeviceAuth(): Promise<DeviceAuthResponse> {
  const response = await fetch(`${BASE_API_URL}/api/device/auth`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const data = await response.json()

  // Open browser for user authentication using Electron API
  const authUrl = `${BASE_API_URL}/auth/device?code=${data.code}`

  // Check if we're in Electron environment
  if (window.electronAPI?.openBrowserUrl) {
    try {
      await window.electronAPI.openBrowserUrl(authUrl)
    } catch (error) {
      console.error('Failed to open browser via Electron:', error)
      // Fallback to window.open if Electron API fails
      window.open(authUrl, '_blank')
    }
  } else {
    // Fallback for web environment
    window.open(authUrl, '_blank')
  }

  return {
    status: data.status,
    code: data.code,
    expires_at: data.expires_at,
    message: i18n.t('common:auth.browserLoginMessage'),
  }
}

export async function pollDeviceAuth(
  deviceCode: string
): Promise<DeviceAuthPollResponse> {
  const response = await fetch(
    `${BASE_API_URL}/api/device/poll?code=${deviceCode}`
  )

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  return await response.json()
}

export async function getAuthStatus(): Promise<AuthStatus> {
  // Get auth status from local storage
  const token = localStorage.getItem('jaaz_access_token')
  const userInfo = localStorage.getItem('jaaz_user_info')

  console.log('Getting auth status from localStorage:', {
    hasToken: !!token,
    hasUserInfo: !!userInfo,
    userInfo: userInfo ? JSON.parse(userInfo) : null,
  })

  if (token && userInfo) {
    const authStatus = {
      status: 'logged_in' as const,
      is_logged_in: true,
      user_info: JSON.parse(userInfo),
    }
    console.log('Returning logged in status:', authStatus)
    return authStatus
  }

  // Development mode: provide default user if no authentication
  const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  if (isDevelopment) {
    const devUser = {
      id: 'dev_user',
      username: 'Development User',
      email: 'dev_user@example.com',
      provider: 'development'
    }

    // Save development user to localStorage for consistency
    localStorage.setItem('jaaz_access_token', 'dev_token')
    localStorage.setItem('jaaz_user_info', JSON.stringify(devUser))

    const devAuthStatus = {
      status: 'logged_in' as const,
      is_logged_in: true,
      user_info: devUser,
    }
    console.log('Returning development mode auth status:', devAuthStatus)
    return devAuthStatus
  }

  const loggedOutStatus = {
    status: 'logged_out' as const,
    is_logged_in: false,
  }
  console.log('Returning logged out status:', loggedOutStatus)
  return loggedOutStatus
}

export async function logout(): Promise<{ status: string; message: string }> {
  // Clear local storage
  localStorage.removeItem('jaaz_access_token')
  localStorage.removeItem('jaaz_user_info')

  // Clear jaaz provider api_key
  await clearJaazApiKey()

  return {
    status: 'success',
    message: i18n.t('common:auth.logoutSuccessMessage'),
  }
}

export async function getUserProfile(): Promise<UserInfo> {
  const userInfo = localStorage.getItem('jaaz_user_info')
  if (!userInfo) {
    throw new Error(i18n.t('common:auth.notLoggedIn'))
  }

  return JSON.parse(userInfo)
}

// Helper function to save auth data to local storage
export function saveAuthData(token: string, userInfo: UserInfo) {
  localStorage.setItem('jaaz_access_token', token)
  localStorage.setItem('jaaz_user_info', JSON.stringify(userInfo))
}

// Helper function to get access token
export function getAccessToken(): string | null {
  return localStorage.getItem('jaaz_access_token')
}

// Helper function to make authenticated API calls
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getAccessToken()
  const userInfo = getUserInfoFromStorage()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Add user info header for development mode
  if (userInfo) {
    headers['X-User-Info'] = JSON.stringify(userInfo)
  }

  return fetch(url, {
    ...options,
    headers,
  })
}

// Helper function to get user info from storage
function getUserInfoFromStorage(): UserInfo | null {
  try {
    const userInfo = localStorage.getItem('jaaz_user_info')
    return userInfo ? JSON.parse(userInfo) : null
  } catch (error) {
    console.error('Failed to parse user info from storage:', error)
    return null
  }
}
