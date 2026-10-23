import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { BookOpen } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../store/auth'
import { Button, Field, inputCls } from '../components/ui'

export default function Login() {
  const { token, login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  const { register, handleSubmit, formState: { isSubmitting } } = useForm()

  if (token) return <Navigate to="/" replace />

  const onSubmit = async ({ email, password }) => {
    setError(null)
    try {
      const res = await api.login(email, password)
      login(res.access_token, res.user)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-navy px-4"
      style={{ backgroundImage: 'radial-gradient(rgba(231,162,27,0.35) 1.2px, transparent 1.3px)', backgroundSize: '18px 18px' }}>
      <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm rounded-lg border-t-4 border-marigold bg-white p-7 shadow-2xl">
        <p className="flex items-center gap-2 text-[22px] font-bold text-navy-deep"><BookOpen className="text-marigold" /> Help Desk admin</p>
        <p className="mb-6 mt-1 text-sm text-slate2">Sign in with your college staff account.</p>
        <div className="grid gap-4">
          <Field label="Email">
            <input type="email" autoComplete="username" required className={inputCls} {...register('email')} />
          </Field>
          <Field label="Password">
            <input type="password" autoComplete="current-password" required className={inputCls} {...register('password')} />
          </Field>
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          <Button type="submit" disabled={isSubmitting} className="justify-center py-2.5">{isSubmitting ? 'Signing in…' : 'Sign in'}</Button>
        </div>
      </form>
    </div>
  )
}
