import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Plus } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../store/auth'
import { Badge, Button, ErrorNote, Field, Loading, Modal, PageHeader, Panel, Table, inputCls } from '../components/ui'
import { timeAgo, titleCase } from '../lib/format'

const ROLE_HELP = {
  super_admin: 'Everything, including users and departments',
  dept_admin: "Their department's tickets, documents and FAQs",
  staff: "Their department's tickets",
}

export default function Users() {
  const me = useAuth((s) => s.user)
  const qc = useQueryClient()
  const [editing, setEditing] = useState(null)
  const { data, isLoading, error } = useQuery({ queryKey: ['users'], queryFn: api.users })
  const toggle = useMutation({
    mutationFn: (u) => api.updateUser(u.id, { is_active: !u.is_active }),
    onSuccess: () => { toast.success('User updated'); qc.invalidateQueries({ queryKey: ['users'] }) },
    onError: (e) => toast.error(e.message),
  })

  return (
    <>
      <PageHeader title="Users" description="Staff accounts for the admin dashboard. Each person sees tickets for their own department." actions={<Button onClick={() => setEditing('new')}><Plus size={16} /> Add user</Button>} />
      <Panel>
        {isLoading && <Loading />}
        <ErrorNote error={error} />
        {data && (
          <Table head={['Name', 'Role', 'Department', 'Last sign-in', 'Status', '']}>
            {data.map((u) => (
              <tr key={u.id}>
                <td className="px-5 py-3"><p className="font-semibold">{u.name}</p><p className="text-[13px] text-slate2">{u.email}</p></td>
                <td className="whitespace-nowrap px-5 py-3">{titleCase(u.role)}</td>
                <td className="whitespace-nowrap px-5 py-3 text-slate2">{u.department?.name || '—'}</td>
                <td className="whitespace-nowrap px-5 py-3 text-slate2">{timeAgo(u.last_login_at)}</td>
                <td className="px-5 py-3">{u.is_active ? <Badge value="active" /> : <Badge value="closed">Disabled</Badge>}</td>
                <td className="whitespace-nowrap px-5 py-3 text-right">
                  <div className="flex justify-end gap-3">
                    <Button variant="link" onClick={() => setEditing(u)}>Edit</Button>
                    {u.id !== me.id && <Button variant="link" onClick={() => toggle.mutate(u)}>{u.is_active ? 'Disable' : 'Enable'}</Button>}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
      {editing && <UserModal user={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </>
  )
}

function UserModal({ user, onClose }) {
  const qc = useQueryClient()
  const { data: departments } = useQuery({ queryKey: ['departments'], queryFn: api.departments })
  const { register, handleSubmit, watch, formState: { errors } } = useForm({
    defaultValues: { name: user?.name || '', email: user?.email || '', role: user?.role || 'staff', department_id: user?.department_id || '', password: '' },
  })
  const save = useMutation({
    mutationFn: (v) => {
      const body = { name: v.name, role: v.role, department_id: v.department_id ? Number(v.department_id) : null }
      if (v.password) body.password = v.password
      return user ? api.updateUser(user.id, body) : api.createUser({ ...body, email: v.email })
    },
    onSuccess: () => { toast.success(user ? 'User saved' : 'User added. Share the password with them securely.'); qc.invalidateQueries({ queryKey: ['users'] }); onClose() },
    onError: (e) => toast.error(e.message),
  })
  const role = watch('role')
  return (
    <Modal title={user ? 'Edit user' : 'Add user'} onClose={onClose}>
      <form onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
        <Field label="Name" error={errors.name && 'Enter a name.'}><input className={inputCls} {...register('name', { required: true, minLength: 2 })} /></Field>
        <Field label="Email"><input type="email" className={inputCls} disabled={!!user} {...register('email', { required: !user })} /></Field>
        <Field label="Role" hint={ROLE_HELP[role]}>
          <select className={inputCls} {...register('role')}>
            <option value="staff">Staff</option>
            <option value="dept_admin">Department admin</option>
            <option value="super_admin">Super admin</option>
          </select>
        </Field>
        <Field label="Department">
          <select className={inputCls} {...register('department_id')}>
            <option value="">None</option>
            {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label={user ? 'New password (leave blank to keep)' : 'Password'} hint="At least 8 characters." error={errors.password && 'Use at least 8 characters.'}>
          <input type="password" autoComplete="new-password" className={inputCls} {...register('password', { required: !user, minLength: 8 })} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={save.isPending}>{user ? 'Save user' : 'Add user'}</Button>
        </div>
      </form>
    </Modal>
  )
}
