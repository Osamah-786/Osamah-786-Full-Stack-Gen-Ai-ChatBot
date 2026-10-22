import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { supabase } from '@/lib/supabase'
import applicationIcon from '@/assets/icons/application.png'

function SignUpPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate('/chat', { replace: true })
    })
  }, [navigate])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')
    setError('')

    if (password !== confirmation) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/signup`,
        },
      })

      if (signUpError) throw signUpError

      setMessage(
        data.session
          ? 'Your account is ready and you are signed in.'
          : 'Account created. Check your email for a confirmation link.',
      )
      if (data.session) navigate('/chat', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to create your account.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="signup-title">
        <p className="auth-brand"><img src={applicationIcon} alt="" />Document Copilot</p>
        <h1 id="signup-title">Create your account</h1>
        <p className="auth-description">Sign up with your work email to get started.</p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <label htmlFor="confirmation">Confirm password</label>
          <input
            id="confirmation"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            required
          />

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        {message && <p className="auth-message" role="status">{message}</p>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <p className="auth-switch">
          Already have an account? <Link to="/signin">Sign in</Link>
        </p>
      </section>
    </main>
  )
}

export default SignUpPage
