import AddProviderDialog from '@/components/settings/AddProviderDialog'
import ComfyuiSetting from '@/components/settings/ComfyuiSetting'
import CommonSetting from '@/components/settings/CommonSetting'
import JaazSetting from '@/components/settings/JaazSetting'
import { Button } from '@/components/ui/button'
import { DEFAULT_PROVIDERS_CONFIG } from '@/constants'
import useConfigsStore from '@/stores/configs'
import { LLMConfig } from '@/types/types'
import { getConfig, updateConfig } from '@/api/config'
import { useRefreshModels } from '@/contexts/configs'
import { Plus, Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

const SettingProviders = () => {
  const { t } = useTranslation()
  const { providers, setProviders } = useConfigsStore()
  const refreshModels = useRefreshModels()
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [isAddProviderDialogOpen, setIsAddProviderDialogOpen] = useState(false)

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config: { [key: string]: LLMConfig } = await getConfig()

        const res: { [key: string]: LLMConfig } = {}

        // First, add custom providers that are not in DEFAULT_PROVIDERS_CONFIG
        for (const provider in config) {
          if (
            !(provider in DEFAULT_PROVIDERS_CONFIG) &&
            typeof config[provider] === 'object'
          ) {
            console.log('Adding custom provider:', provider, config[provider])
            res[provider] = config[provider]
          }
        }

        // Then, add providers from DEFAULT_PROVIDERS_CONFIG
        for (const provider in DEFAULT_PROVIDERS_CONFIG) {
          if (config[provider] && typeof config[provider] === 'object') {
            res[provider] = {
              ...DEFAULT_PROVIDERS_CONFIG[provider],
              ...config[provider],
              models: {
                ...DEFAULT_PROVIDERS_CONFIG[provider].models,
                ...config[provider].models,
              },
            }
          } else {
            res[provider] = DEFAULT_PROVIDERS_CONFIG[provider]
          }
        }

        setProviders(res)
      } catch (error) {
        console.error('Error loading configuration:', error)
        setErrorMessage(t('settings:messages.failedToLoad'))
      } finally {
        setIsLoading(false)
      }
    }

    loadConfig()
  }, [])

  const handleConfigChange = (key: string, newConfig: LLMConfig) => {
    setProviders({
      ...providers,
      [key]: newConfig,
    })
  }

  const handleAddProvider = (providerKey: string, newConfig: LLMConfig) => {
    setProviders({
      ...providers,
      [providerKey]: newConfig,
    })
  }

  const handleDeleteProvider = (providerKey: string) => {
    delete providers[providerKey]
    setProviders({
      ...providers,
    })
  }

  const handleSave = async () => {
    try {
      setErrorMessage('')

      const result = await updateConfig(providers)

      if (result.status === 'success') {
        toast.success(result.message)
        // Refresh models list after successful config update
        refreshModels()
      } else {
        throw new Error(result.message || 'Failed to save configuration')
      }
    } catch (error) {
      console.error('Error saving settings:', error)
      setErrorMessage(t('settings:messages.failedToSave'))
    }
  }

  return (
    <div className="flex flex-col items-center justify-center p-4 relative w-full sm:pb-0 pb-10">
      {isLoading && (
        <div className="flex justify-center items-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-zinc-500"></div>
        </div>
      )}

      <div className="w-full">
        <JaazSetting
          config={providers['jaaz']}
          onConfigChange={handleConfigChange}
        />

        <div className="my-6 border-t bg-border" />
      </div>

      {!isLoading &&
        Object.keys(providers).map((key, index) => (
          <div key={key} className="w-full">
            {key === 'comfyui' ? (
              <ComfyuiSetting
                config={providers[key]}
                onConfigChange={handleConfigChange}
              />
            ) : (
              <CommonSetting
                providerKey={key}
                config={providers[key]}
                onConfigChange={handleConfigChange}
                onDeleteProvider={handleDeleteProvider}
              />
            )}

            {index !== Object.keys(providers).length - 1 && (
              <div className="my-6 border-t bg-border" />
            )}
          </div>
        ))}

      <div className="flex justify-center fixed sm:bottom-2 sm:left-[calc(var(--sidebar-width)+0.45rem)] sm:translate-x-0 -translate-x-1/2 bottom-15 left-1/2 gap-1.5">
        <Button onClick={handleSave}>
          <Save className="mr-2 h-4 w-4" /> {t('settings:saveSettings')}
        </Button>

        <Button
          variant="outline"
          onClick={() => setIsAddProviderDialogOpen(true)}
        >
          <Plus className="h-4 w-4" />
          {t('settings:provider.addProvider')}
        </Button>
      </div>

      {errorMessage && (
        <div className="text-red-500 text-center mb-4">{errorMessage}</div>
      )}

      <AddProviderDialog
        open={isAddProviderDialogOpen}
        onOpenChange={setIsAddProviderDialogOpen}
        onSave={handleAddProvider}
      />
    </div>
  )
}

export default SettingProviders
