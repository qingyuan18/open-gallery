import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { useConfigs } from '@/contexts/configs'
import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'

const ModelSelector: React.FC = () => {
  const {
    textModel,
    imageModel,
    setTextModel,
    setImageModel,
    textModels,
    imageModels,
  } = useConfigs()

  // 多选图像模型状态
  const [selectedImageModels, setSelectedImageModels] = useState<string[]>([])

  // 从localStorage加载已选择的图像模型
  useEffect(() => {
    const saved = localStorage.getItem('selected_image_models')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        setSelectedImageModels(parsed)
      } catch (e) {
        console.error('Failed to parse selected image models:', e)
      }
    } else if (imageModel) {
      // 如果没有保存的多选数据，但有当前选中的模型，则初始化为该模型
      const modelKey = imageModel.provider + ':' + imageModel.model
      setSelectedImageModels([modelKey])
    }
  }, [imageModel])

  // 处理图像模型多选
  const handleImageModelToggle = (modelKey: string, checked: boolean) => {
    let newSelected: string[]
    if (checked) {
      newSelected = [...selectedImageModels, modelKey]
    } else {
      newSelected = selectedImageModels.filter((key) => key !== modelKey)
    }

    setSelectedImageModels(newSelected)
    localStorage.setItem('selected_image_models', JSON.stringify(newSelected))

    // 如果有选中的模型，将第一个设为当前imageModel（保持向后兼容）
    if (newSelected.length > 0) {
      const firstModel = imageModels?.find(
        (m) => m.provider + ':' + m.model === newSelected[0]
      )
      if (firstModel) {
        setImageModel(firstModel)
        localStorage.setItem('image_model', newSelected[0])
      }
    }
  }

  // 获取显示文本
  const getSelectedImageModelsText = () => {
    if (selectedImageModels.length === 0) return '选择图像模型'
    if (selectedImageModels.length === 1) {
      const model = imageModels?.find(
        (m) => m.provider + ':' + m.model === selectedImageModels[0]
      )
      return model?.model || selectedImageModels[0]
    }
    return `已选择 ${selectedImageModels.length} 个模型`
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
          {textModels?.map((model) => (
            <SelectItem
              key={model.provider + ':' + model.model}
              value={model.provider + ':' + model.model}
            >
              {model.model}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 多选图像模型下拉菜单 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="w-fit max-w-[40%] bg-background justify-between"
          >
            <span>🎨</span>
            <span className="ml-2">{getSelectedImageModelsText()}</span>
            <ChevronDown className="ml-2 h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-100">
          <DropdownMenuLabel>
            <div className="flex items-center gap-2">模型</div>
          </DropdownMenuLabel>
          {imageModels?.slice(0, 6).map((model) => {
            const modelKey = model.provider + ':' + model.model
            return (
              <DropdownMenuCheckboxItem
                key={modelKey}
                checked={selectedImageModels.includes(modelKey)}
                onCheckedChange={(checked) =>
                  handleImageModelToggle(modelKey, checked)
                }
              >
                {model.model}
              </DropdownMenuCheckboxItem>
            )
          })}
          <DropdownMenuSeparator />
          <div className="flex items-center gap-2">
            <img
              src={
                'https://framerusercontent.com/images/3cNQMWKzIhIrQ5KErBm7dSmbd2w.png'
              }
              alt={'ComfyUI'}
              className="w-6 h-6 rounded-full"
            />
            工作流
          </div>
          {imageModels?.slice(3).map((model) => {
            const modelKey = model.provider + ':' + model.model
            return (
              <DropdownMenuCheckboxItem
                key={modelKey}
                checked={selectedImageModels.includes(modelKey)}
                onCheckedChange={(checked) =>
                  handleImageModelToggle(modelKey, checked)
                }
              >
                {model.model}
              </DropdownMenuCheckboxItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}

export default ModelSelector
