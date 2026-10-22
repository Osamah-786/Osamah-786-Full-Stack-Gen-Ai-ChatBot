function required(name: string, value: string | undefined): string {
  if (!value?.trim()) {
    throw new Error(`Missing required environment variable: ${name}`)
  }

  return value.trim()
}

function requiredUrl(name: string, value: string | undefined): string {
  const raw = required(name, value)

  try {
    const url = new URL(raw)
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error()
    return url.toString().replace(/\/$/, '')
  } catch {
    throw new Error(`${name} must be a valid URL`)
  }
}

export const env = {
  apiBaseUrl: requiredUrl('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL),
  supabaseUrl: requiredUrl('VITE_SUPABASE_URL', import.meta.env.VITE_SUPABASE_URL),
  supabaseAnonKey: required('VITE_SUPABASE_ANON_KEY', import.meta.env.VITE_SUPABASE_ANON_KEY),
}
