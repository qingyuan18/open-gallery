import { authenticatedFetch } from './auth'

export async function listModels(): Promise<
  {
    provider: string
    model: string
    type: string
    url: string
    media_type?: string
  }[]
> {
  const response = await authenticatedFetch('/api/list_models')
  if (!response.ok) {
    throw new Error(`Failed to list models: ${response.status}`)
  }
  return await response.json()
}
