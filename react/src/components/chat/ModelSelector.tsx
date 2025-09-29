import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  SelectGroup,
  SelectLabel,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { useConfigs } from '@/contexts/configs'
import { PROVIDER_NAME_MAPPING } from '@/constants'

const ModelSelector: React.FC = () => {
  const {
    textModel,
    imageModel,
    videoModel,
    comfyuiModel,
    setTextModel,
    setImageModel,
    setVideoModel,
    setComfyuiModel,
    textModels,
    imageModels,
    videoModels,
    comfyuiModels,
    autoModelSelection,
    setAutoModelSelection,
  } = useConfigs()

  // Group models by provider
  const groupModelsByProvider = (models: typeof textModels) => {
    const grouped: { [provider: string]: typeof textModels } = {}
    models?.forEach((model) => {
      if (!grouped[model.provider]) {
        grouped[model.provider] = []
      }
      grouped[model.provider].push(model)
    })
    return grouped
  }

  const groupedTextModels = groupModelsByProvider(textModels)
  const groupedImageModels = groupModelsByProvider(imageModels)
  const groupedVideoModels = groupModelsByProvider(videoModels)

  // Sort providers to put Jaaz first
  const sortProviders = (providers: [string, typeof textModels][]) => {
    return providers.sort(([providerA], [providerB]) => {
      if (providerA === 'jaaz') return -1
      if (providerB === 'jaaz') return 1
      return 0
    })
  }

  const getProviderDisplayName = (provider: string) => {
    const providerInfo = PROVIDER_NAME_MAPPING[provider]
    return {
      name: providerInfo?.name || provider,
      icon: providerInfo?.icon
    }
  }

  return (
    <>
      <Select
        value={textModel?.provider + ':' + textModel?.model}
        onValueChange={(value) => {
          localStorage.setItem('text_model', value)
          setTextModel(
            textModels?.find((m) => m.provider + ':' + m.model == value)
          )
        }}
      >
        <SelectTrigger className="w-fit max-w-[40%] bg-background">
          <SelectValue placeholder="Theme" />
        </SelectTrigger>
        <SelectContent>
          {sortProviders(Object.entries(groupedTextModels)).map(([provider, models]) => {
            const providerInfo = getProviderDisplayName(provider)
            return (
              <SelectGroup key={provider}>
                <SelectLabel className="flex items-center gap-2 select-none">
                  {providerInfo.icon && (
                    <img
                      src={providerInfo.icon}
                      alt={providerInfo.name}
                      className="w-4 h-4 rounded-sm"
                    />
                  )}
                  {providerInfo.name}
                </SelectLabel>
                {models.map((model) => (
                  <SelectItem
                    key={model.provider + ':' + model.model}
                    value={model.provider + ':' + model.model}
                  >
                    {model.model}
                  </SelectItem>
                ))}
              </SelectGroup>
            )
          })}
        </SelectContent>
      </Select>

      {/* 自动判断复选框 */}
      <div className="flex items-center space-x-2 min-w-[96px] px-1">
        <Checkbox
          id="auto-model-selection"
          checked={autoModelSelection}
          onCheckedChange={(checked) => setAutoModelSelection(!!checked)}
        />
        <label
          htmlFor="auto-model-selection"
          className="text-sm font-medium leading-none whitespace-nowrap peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
        >
          自动判断
        </label>
      </div>

      <Select
        value={comfyuiModel?.provider + ':' + comfyuiModel?.model}
        onValueChange={(value) => {
          localStorage.setItem('comfyui_model', value)
          const selectedModel = comfyuiModels?.find((m) => m.provider + ':' + m.model == value)
          setComfyuiModel(selectedModel)

          // 根据模型类型自动设置图像或视频模型
          if (selectedModel?.media_type === 'image') {
            localStorage.setItem('image_model', value)
            setImageModel(selectedModel)
            // 清除视频模型
            localStorage.removeItem('video_model')
            setVideoModel(undefined)
          } else if (selectedModel?.media_type === 'video') {
            localStorage.setItem('video_model', value)
            setVideoModel(selectedModel)
            // 清除图像模型
            localStorage.removeItem('image_model')
            setImageModel(undefined)
          }
        }}
      >
        <SelectTrigger className="w-fit max-w-[40%] bg-background">
          <span>🎨🎬</span>
          <SelectValue placeholder="ComfyUI Model" />
        </SelectTrigger>
        <SelectContent>
          {sortProviders(Object.entries(groupModelsByProvider(comfyuiModels))).map(([provider, models]) => {
            const providerInfo = getProviderDisplayName(provider)
            return (
              <SelectGroup key={provider}>
                <SelectLabel className="flex items-center gap-2 select-none">
                  {providerInfo.icon && (
                    <img
                      src={providerInfo.icon}
                      alt={providerInfo.name}
                      className="w-4 h-4 rounded-sm"
                    />
                  )}
                  {providerInfo.name}
                </SelectLabel>
                {models.map((model) => (
                  <SelectItem
                    key={model.provider + ':' + model.model}
                    value={model.provider + ':' + model.model}
                  >
                    {model.model} {model.media_type === 'image' ? '🎨' : '🎬'}
                  </SelectItem>
                ))}
              </SelectGroup>
            )
          })}
        </SelectContent>
      </Select>
    </>
  )
}

export default ModelSelector
