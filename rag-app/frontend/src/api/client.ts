import axios from 'axios'
import type { ChatResponse, Message, StatusResponse, UploadResponse } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000,
})

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<UploadResponse>('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function sendMessage(
  question: string,
  history: Message[],
): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>('/chat', {
    question,
    conversation_history: history.map(({ role, content }) => ({ role, content })),
  })
  return response.data
}

export async function getStatus(): Promise<StatusResponse> {
  const response = await api.get<StatusResponse>('/status')
  return response.data
}

export async function clearIndex(): Promise<void> {
  await api.delete('/clear')
}
