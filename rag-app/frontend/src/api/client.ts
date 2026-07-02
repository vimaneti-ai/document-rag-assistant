import axios from 'axios'
import type { ChatResponse, Message, StatusResponse, UploadResponse } from '../types'

export interface AuthCredentials {
  username: string
  password: string
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000,
})

function authConfig(credentials: AuthCredentials) {
  return {
    auth: {
      username: credentials.username,
      password: credentials.password,
    },
  }
}

export async function uploadDocument(
  file: File,
  credentials: AuthCredentials,
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<UploadResponse>('/upload', formData, {
    ...authConfig(credentials),
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function sendMessage(
  question: string,
  history: Message[],
  credentials: AuthCredentials,
): Promise<ChatResponse> {
  const response = await api.post<ChatResponse>(
    '/chat',
    {
      question,
      conversation_history: history.map(({ role, content }) => ({ role, content })),
    },
    authConfig(credentials),
  )
  return response.data
}

export async function getStatus(credentials: AuthCredentials): Promise<StatusResponse> {
  const response = await api.get<StatusResponse>('/status', authConfig(credentials))
  return response.data
}

export async function clearIndex(credentials: AuthCredentials): Promise<void> {
  await api.delete('/clear', authConfig(credentials))
}
