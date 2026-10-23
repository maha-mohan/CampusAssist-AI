import { useForm } from 'react-hook-form'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '../api/client'
import { useAuth } from '../store/auth'
import { Button, Field, PageHeader, Panel, inputCls } from '../components/ui'
import { titleCase } from '../lib/format'

export default function Account() {
  const user = useAuth((s) => s.user)
  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm()
  const change = useMutation({
    mutationFn: (v) => api.changePassword({ current_password: v.current_password, new_password: v.new_password }),
    onSuccess: () => { toast.success('Password changed'); reset() },
    onError: (e) => toast.error(e.message),
  })
  return (
    <>
      <PageHeader title="Account" />
      <div className="grid max-w-3xl gap-6">
        <Panel title="Profile">
          <dl className="grid grid-cols-[140px_1fr] gap-y-2 px-5 py-4 text-[15px]">
            <dt className="text-slate2">Name</dt><dd>{user?.name}</dd>
            <dt className="text-slate2">Email</dt><dd>{user?.email}</dd>
            <dt className="text-slate2">Role</dt><dd>{titleCase(user?.role)}</dd>
            <dt className="text-slate2">Department</dt><dd>{user?.department?.name || '—'}</dd>
          </dl>
        </Panel>
        <Panel title="Change password">
          <form onSubmit={handleSubmit((v) => change.mutate(v))} className="grid max-w-sm gap-4 px-5 py-4">
            <Field label="Current password"><input type="password" autoComplete="current-password" className={inputCls} {...register('current_password', { required: true })} /></Field>
            <Field label="New password" hint="At least 8 characters." error={errors.new_password && 'Use at least 8 characters.'}>
              <input type="password" autoComplete="new-password" className={inputCls} {...register('new_password', { required: true, minLength: 8 })} />
            </Field>
            <Field label="Repeat new password" error={errors.confirm && "The passwords don't match."}>
              <input type="password" autoComplete="new-password" className={inputCls} {...register('confirm', { validate: (v) => v === watch('new_password') })} />
            </Field>
            <Button type="submit" disabled={change.isPending}>Change password</Button>
          </form>
        </Panel>
      </div>
    </>
  )
}
