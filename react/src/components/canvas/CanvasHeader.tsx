import LanguageSwitcher from '@/components/common/LanguageSwitcher'
import { NotificationPanel } from '@/components/common/NotificationPanel'
import ThemeButton from '@/components/theme/ThemeButton'
import { Input } from '@/components/ui/input'
import { LOGO_URL } from '@/constants'
import { useConfigs } from '@/contexts/configs'
import { useNavigate } from '@tanstack/react-router'
import { ChevronLeft, SettingsIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../ui/button'
import CanvasExport from './CanvasExport'

type CanvasHeaderProps = {
  canvasName: string
  canvasId: string
  onNameChange: (name: string) => void
  onNameSave: () => void
}

const CanvasHeader: React.FC<CanvasHeaderProps> = ({
  canvasName,
  canvasId,
  onNameChange,
  onNameSave,
}) => {
  const { t } = useTranslation()
  const [isLogoHovered, setIsLogoHovered] = useState(false)

  const navigate = useNavigate()
  const { setShowSettingsDialog } = useConfigs()

  return (
    <motion.div
      className="sticky top-0 z-0 flex w-full h-12 bg-background px-4 justify-between items-center select-none border-b border-border"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <motion.div
        className="flex items-center gap-2 cursor-pointer group"
        onHoverStart={() => setIsLogoHovered(true)}
        onHoverEnd={() => setIsLogoHovered(false)}
        onClick={() => navigate({ to: '/' })}
      >
        <ChevronLeft className="size-5 group-hover:-translate-x-0.5 transition-transform duration-300" />
        <img src={LOGO_URL} alt="logo" className="size-8" draggable={false} />
        <motion.div
          className="flex relative gap-10 flex-col overflow-hidden items-start h-7 text-xl font-bold"
          style={{
            justifyContent: isLogoHovered ? 'flex-end' : 'flex-start',
          }}
        >
          <motion.span className="flex items-center" layout>
            {t('canvas:back')}
          </motion.span>
          <motion.span className="flex items-center" layout aria-hidden>
            {t('canvas:back')}
          </motion.span>
        </motion.div>
      </motion.div>

      <div className="flex items-center gap-2">
        <Input
          className="text-sm text-muted-foreground text-center bg-transparent border-none shadow-none w-fit h-7 hover:bg-primary-foreground transition-all"
          value={canvasName}
          onChange={(e) => onNameChange(e.target.value)}
          onBlur={onNameSave}
        />
      </div>

      <div className="flex items-center gap-2">
        <NotificationPanel />
        <CanvasExport />
        <Button
          size={'sm'}
          variant="ghost"
          onClick={() => setShowSettingsDialog(true)}
        >
          <SettingsIcon size={30} />
        </Button>
        <LanguageSwitcher />
        <ThemeButton />
      </div>
    </motion.div>
  )
}

export default CanvasHeader
