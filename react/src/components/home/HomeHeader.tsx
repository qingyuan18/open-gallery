import LanguageSwitcher from '@/components/common/LanguageSwitcher'
import { NotificationPanel } from '@/components/common/NotificationPanel'
import ThemeButton from '@/components/theme/ThemeButton'
import { Button } from '@/components/ui/button'
import { LOGO_URL } from '@/constants'
import { useConfigs } from '@/contexts/configs'
import { SettingsIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { UserMenu } from '@/components/auth/UserMenu'
import AgentSettings from '../agent_studio/AgentSettings'

function HomeHeader() {
  const { setShowSettingsDialog } = useConfigs()

  return (
    <motion.div
      className="sticky top-0 z-0 flex w-full h-12 bg-background px-4 justify-between items-center select-none"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-center gap-2">
        <img src={LOGO_URL} alt="logo" className="size-8" draggable={false} />
        <p className="text-xl font-bold">open gallary</p>
      </div>
      <div className="flex items-center gap-2">
        <NotificationPanel />
        <AgentSettings />
        <Button
          size={'sm'}
          variant="ghost"
          onClick={() => setShowSettingsDialog(true)}
        >
          <SettingsIcon size={30} />
        </Button>
        <LanguageSwitcher />
        <ThemeButton />
        {/* disable user login until cloud server is ready */}
        <UserMenu />
      </div>
    </motion.div>
  )
}

export default HomeHeader
