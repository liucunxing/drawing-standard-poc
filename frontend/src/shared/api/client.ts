import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'

export interface ApiEnvelope<T> {
  code: number
  msg: string
  data: T | null
}

export class ApiError extends Error {
  readonly code?: number
  readonly httpStatus?: number

  constructor(message: string, options: { code?: number; httpStatus?: number } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = options.code
    this.httpStatus = options.httpStatus
  }
}

const apiBase = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')

export const apiClient = axios.create({
  baseURL: apiBase,
  timeout: 60_000,
  headers: { Accept: 'application/json' },
})

export function unwrapEnvelope<T>(payload: ApiEnvelope<T>): T {
  if (!payload || typeof payload.code !== 'number') throw new ApiError('服务返回格式不正确')
  if (payload.code !== 200) throw new ApiError(payload.msg || '请求失败', { code: payload.code })
  return payload.data as T
}

export function getErrorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  if (error instanceof ApiError) return error.message
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiEnvelope<unknown>>
    return axiosError.response?.data?.msg || axiosError.message || fallback
  }
  if (error instanceof Error) return error.message
  return fallback
}

export async function apiRequest<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await apiClient.request<ApiEnvelope<T>>(config)
    return unwrapEnvelope(response.data)
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError<ApiEnvelope<unknown>>
      throw new ApiError(getErrorMessage(error), {
        code: axiosError.response?.data?.code,
        httpStatus: axiosError.response?.status,
      })
    }
    throw error
  }
}

export function resolveApiFileUrl(path: string | null | undefined): string {
  const value = String(path || '').trim().replace(/\\/g, '/')
  if (!value) return ''
  if (/^https?:\/\//i.test(value) || value.startsWith('data:')) return value
  if (value.startsWith('/api/')) return value
  if (value.startsWith('/files/')) return `${apiBase}${value}`
  if (value.startsWith('files/')) return `${apiBase}/${value}`
  return value.startsWith('/') ? value : `${apiBase}/files/${value.replace(/^\/+/, '')}`
}
