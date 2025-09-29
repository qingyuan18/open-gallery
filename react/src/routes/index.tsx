import { createCanvas } from '@/api/canvas'
import ChatTextarea from '@/components/chat/ChatTextarea'
import CanvasList from '@/components/home/CanvasList'
import HomeHeader from '@/components/home/HomeHeader'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useConfigs } from '@/contexts/configs'
import { useAuth } from '@/contexts/AuthContext'
import { DEFAULT_SYSTEM_PROMPT } from '@/constants'
import { useMutation } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { motion } from 'motion/react'
import { nanoid } from 'nanoid'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

export const Route = createFileRoute('/')({
  component: Home,
})

function Home() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { setInitCanvas, setShowLoginDialog } = useConfigs()
  const { authStatus, isLoading } = useAuth()

  // Check authentication status and show login dialog if needed
  useEffect(() => {
    if (!isLoading && !authStatus.is_logged_in) {
      setShowLoginDialog(true)
    }
  }, [authStatus.is_logged_in, isLoading, setShowLoginDialog])

  const { mutate: createCanvasMutation, isPending } = useMutation({
    mutationFn: createCanvas,
    onSuccess: (data) => {
      setInitCanvas(true)
      navigate({
        to: '/canvas/$id',
        params: { id: data.id },
      })
    },
    onError: (error) => {
      toast.error(t('common:messages.error'), {
        description: error.message,
      })
    },
  })

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <HomeHeader />
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      </div>
    )
  }

  // Don't render main content if not logged in
  if (!authStatus.is_logged_in) {
    return (
      <div className="flex flex-col h-screen">
        <HomeHeader />
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <h2 className="text-2xl font-bold mb-4">Welcome to Jaaz</h2>
            <p className="text-muted-foreground mb-4">Please login to continue</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen">
      <ScrollArea className="h-full">
        <HomeHeader />

        <div className="relative flex flex-col items-center justify-center h-fit min-h-[calc(100vh-460px)] pt-[60px] select-none">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-5xl font-bold mb-2 mt-8 text-center">
              {t('home:title')}
            </h1>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <p className="text-xl text-gray-500 mb-8 text-center">
              {t('home:subtitle')}
            </p>
          </motion.div>

          <ChatTextarea
            className="w-full max-w-xl"
            messages={[]}
            onSendMessages={(messages, configs) => {
              createCanvasMutation({
                name: t('home:newCanvas'),
                canvas_id: nanoid(),
                messages: messages,
                session_id: nanoid(),
                text_model: configs.textModel,
                image_model: configs.imageModel,
                video_model: configs.videoModel,
                auto_model_selection: configs.autoModelSelection,
                system_prompt:
                  localStorage.getItem('system_prompt') ||
                  DEFAULT_SYSTEM_PROMPT,
              })
            }}
            pending={isPending}
          />
        </div>

        <CanvasList />
      </ScrollArea>
    </div>
  )
}
