import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

export class ApiError extends Error {
  readonly status: number | null
  readonly isNetworkError: boolean

  constructor(
    message: string,
    status: number | null,
    isNetworkError: boolean,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

export async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    throw new ApiError('Unable to read the current session', null, false)
  }

  const headers = new Headers({ Accept: 'application/json' })
  if (body !== undefined) headers.set('Content-Type', 'application/json')
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  const url = new URL(path, `${env.apiBaseUrl}/`)
  if (url.origin !== new URL(env.apiBaseUrl).origin) {
    throw new ApiError('API requests must use the configured API origin', null, false)
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    })
  } catch (error) {
    const message = error instanceof DOMException && error.name === 'TimeoutError'
      ? 'The request timed out'
      : 'Unable to reach the API'
    throw new ApiError(message, null, true)
  }

  const result: unknown = response.status === 204
    ? undefined
    : await response.json().catch(() => undefined)

  if (!response.ok) {
    const detail =
      typeof result === 'object' && result !== null && 'detail' in result
        ? result.detail
        : undefined
    const message = typeof detail === 'string'
      ? detail
      : `API request failed (${response.status})`
    throw new ApiError(message, response.status, false)
  }

  return result as T
}
