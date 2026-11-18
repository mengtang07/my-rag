import type { ApiEnvelope } from '../types/api'

export class ApiError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

/**
 * 统一的请求封装：拆掉后端的 `{code, data, message}` 信封，
 * code 非 0 时抛 ApiError。
 */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)

  let envelope: ApiEnvelope<T>
  try {
    envelope = (await response.json()) as ApiEnvelope<T>
  } catch {
    throw new ApiError(String(response.status), `请求失败（HTTP ${response.status}）`)
  }

  if (envelope.code !== '0') {
    throw new ApiError(envelope.code, envelope.message || '请求失败')
  }

  return envelope.data
}
