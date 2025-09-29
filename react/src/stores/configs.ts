import { DEFAULT_PROVIDERS_CONFIG } from '@/constants'
import { LLMConfig, Model } from '@/types/types'
import { create } from 'zustand'

type ConfigsStore = {
  initCanvas: boolean
  setInitCanvas: (initCanvas: boolean) => void

  textModels: Model[]
  imageModels: Model[]
  videoModels: Model[]
  comfyuiModels: Model[]
  setTextModels: (models: Model[]) => void
  setImageModels: (models: Model[]) => void
  setVideoModels: (models: Model[]) => void
  setComfyuiModels: (models: Model[]) => void

  textModel?: Model
  imageModel?: Model
  videoModel?: Model
  comfyuiModel?: Model
  setTextModel: (model?: Model) => void
  setImageModel: (model?: Model) => void
  setVideoModel: (model?: Model) => void
  setComfyuiModel: (model?: Model) => void

  // 自动判断模型配置
  autoModelSelection: boolean
  setAutoModelSelection: (auto: boolean) => void

  showInstallDialog: boolean
  setShowInstallDialog: (show: boolean) => void

  showUpdateDialog: boolean
  setShowUpdateDialog: (show: boolean) => void

  showSettingsDialog: boolean
  setShowSettingsDialog: (show: boolean) => void

  showLoginDialog: boolean
  setShowLoginDialog: (show: boolean) => void

  providers: {
    [key: string]: LLMConfig
  }
  setProviders: (providers: { [key: string]: LLMConfig }) => void
}

const useConfigsStore = create<ConfigsStore>((set) => ({
  initCanvas: false,
  setInitCanvas: (initCanvas) => set({ initCanvas }),

  textModels: [],
  imageModels: [],
  videoModels: [],
  comfyuiModels: [],
  setTextModels: (models) => set({ textModels: models }),
  setImageModels: (models) => set({ imageModels: models }),
  setVideoModels: (models) => set({ videoModels: models }),
  setComfyuiModels: (models) => set({ comfyuiModels: models }),

  textModel: undefined,
  imageModel: undefined,
  videoModel: undefined,
  comfyuiModel: undefined,
  setTextModel: (model) => set({ textModel: model }),
  setImageModel: (model) => set({ imageModel: model }),
  setVideoModel: (model) => set({ videoModel: model }),
  setComfyuiModel: (model) => set({ comfyuiModel: model }),

  // 自动判断模型配置，默认开启
  autoModelSelection: true,
  setAutoModelSelection: (auto) => {
    set({ autoModelSelection: auto })
    localStorage.setItem('auto_model_selection', JSON.stringify(auto))
  },

  showInstallDialog: false,
  setShowInstallDialog: (show) => set({ showInstallDialog: show }),

  showUpdateDialog: false,
  setShowUpdateDialog: (show) => set({ showUpdateDialog: show }),

  showSettingsDialog: false,
  setShowSettingsDialog: (show) => set({ showSettingsDialog: show }),

  showLoginDialog: false,
  setShowLoginDialog: (show) => set({ showLoginDialog: show }),

  providers: DEFAULT_PROVIDERS_CONFIG,
  setProviders: (providers) => set({ providers }),
}))

export default useConfigsStore
