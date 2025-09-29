import { CanvasData, Message, Session } from '@/types/types'
import { authenticatedFetch } from './auth'

export type ListCanvasesResponse = {
  id: string
  name: string
  description?: string
  thumbnail?: string
  created_at: string
}

export async function listCanvases(): Promise<ListCanvasesResponse[]> {
  const response = await authenticatedFetch('/api/canvas/list')
  if (!response.ok) {
    throw new Error(`Failed to list canvases: ${response.status}`)
  }
  return await response.json()
}

export async function createCanvas(data: {
  name: string
  canvas_id: string
  messages: Message[]
  session_id: string
  text_model: {
    provider: string
    model: string
    url: string
  }
  image_model: {
    provider: string
    model: string
    url: string
  }
  video_model?: {
    provider: string
    model: string
    url: string
  }
  auto_model_selection?: boolean
  system_prompt: string
}): Promise<{ id: string }> {
  const response = await authenticatedFetch('/api/canvas/create', {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create canvas: ${response.status}`)
  }
  return await response.json()
}

export async function getCanvas(
  id: string
): Promise<{ data: CanvasData; name: string; sessions: Session[] }> {
  const response = await authenticatedFetch(`/api/canvas/${id}`)
  if (!response.ok) {
    throw new Error(`Failed to get canvas: ${response.status}`)
  }
  return await response.json()
}

export async function saveCanvas(
  id: string,
  payload: {
    data: CanvasData
    thumbnail: string
  }
): Promise<void> {
  const response = await authenticatedFetch(`/api/canvas/${id}/save`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Failed to save canvas: ${response.status}`)
  }
  return await response.json()
}

export async function renameCanvas(id: string, name: string): Promise<void> {
  const response = await authenticatedFetch(`/api/canvas/${id}/rename`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
  if (!response.ok) {
    throw new Error(`Failed to rename canvas: ${response.status}`)
  }
  return await response.json()
}

export async function deleteCanvas(id: string): Promise<void> {
  const response = await authenticatedFetch(`/api/canvas/${id}/delete`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete canvas: ${response.status}`)
  }
  return await response.json()
}
