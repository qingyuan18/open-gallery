import { useCanvas } from '@/contexts/canvas'
import { TCanvasAddImagesToChatEvent } from '@/lib/event'
import { ExcalidrawImageElement } from '@excalidraw/excalidraw/element/types'
import { AnimatePresence } from 'motion/react'
import { useRef, useState } from 'react'
import CanvasPopbar from './CanvasPopbar'

const CanvasPopbarWrapper = () => {
  const { excalidrawAPI } = useCanvas()

  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)

  const selectedImagesRef = useRef<TCanvasAddImagesToChatEvent>([])

  excalidrawAPI?.onChange((elements, appState, files) => {
    const selectedIds = appState.selectedElementIds
    if (Object.keys(selectedIds).length === 0) {
      setPos(null)
      return
    }

    const selectedImages = elements.filter(
      (element) => element.type === 'image' && selectedIds[element.id]
    ) as ExcalidrawImageElement[]
    if (selectedImages.length === 0) {
      setPos(null)
      return
    }

    selectedImagesRef.current = selectedImages
      .filter((image) => image.fileId)
      .map((image) => {
        const file = files[image.fileId!]
        const isBase64 = file.dataURL.startsWith('data:')
        const id = isBase64 ? file.id : file.dataURL.split('/').at(-1)!
        return {
          fileId: id,
          base64: isBase64 ? file.dataURL : undefined,
          width: image.width,
          height: image.height,
        }
      })

    const centerX =
      selectedImages.reduce(
        (acc, image) => acc + image.x + image.width / 2,
        0
      ) / selectedImages.length

    const bottomY = selectedImages.reduce(
      (acc, image) => Math.max(acc, image.y + image.height),
      0
    )

    const scrollX = appState.scrollX
    const scrollY = appState.scrollY
    const zoom = appState.zoom.value
    const offsetX = (scrollX + centerX) * zoom
    const offsetY = (scrollY + bottomY) * zoom
    setPos({ x: offsetX, y: offsetY })
  })

  return (
    <div className="absolute left-0 bottom-0 w-full h-full z-20 pointer-events-none">
      <AnimatePresence>
        {pos && (
          <CanvasPopbar pos={pos} selectedImages={selectedImagesRef.current} />
        )}
      </AnimatePresence>
    </div>
  )
}

export default CanvasPopbarWrapper
