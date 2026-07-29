import { apiRequest } from '../../../shared/api/client'
import type { StandardInput, StandardListResult, StandardRecord } from '../types'

export function listStandards(params: { keyword?: string; page?: number; pageSize?: number } = {}) {
  return apiRequest<StandardListResult>({
    method: 'GET',
    url: '/standard-data',
    params: { keyword: params.keyword || '', page: params.page || 1, page_size: params.pageSize || 20 },
  })
}

export function createStandard(payload: StandardInput) {
  return apiRequest<StandardRecord>({ method: 'POST', url: '/standard-data', data: payload })
}

export function updateStandard(id: number, payload: StandardInput) {
  return apiRequest<StandardRecord>({ method: 'PUT', url: `/standard-data/${id}`, data: payload })
}

export function deleteStandard(id: number) {
  return apiRequest<{ id: number }>({ method: 'DELETE', url: `/standard-data/${id}` })
}
