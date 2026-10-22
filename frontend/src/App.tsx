import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import type { Session } from '@supabase/supabase-js'

import SignInPage from '@/pages/SignInPage'
import SignUpPage from '@/pages/SignUpPage'
import ChatWorkspace from '@/pages/ChatWorkspace'
import { supabase } from '@/lib/supabase'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <SessionRoutes />
    </BrowserRouter>
  )
}

function SessionRoutes() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!loading && session && ['/signin', '/signup', '/'].includes(window.location.pathname)) {
      navigate('/chat', { replace: true })
    }
  }, [loading, navigate, session])

  if (loading) return <div className="route-loading">Loading…</div>

  return (
    <Routes>
      <Route path="/signin" element={<SignInPage />} />
      <Route path="/signup" element={<SignUpPage />} />
      <Route
        path="/chat"
        element={session ? <ChatWorkspace /> : <Navigate to="/signin" replace />}
      />
      <Route
        path="/chat/:threadId"
        element={session ? <ChatWorkspace /> : <Navigate to="/signin" replace />}
      />
      <Route path="*" element={<Navigate to={session ? '/chat' : '/signin'} replace />} />
    </Routes>
  )
}

export default App
