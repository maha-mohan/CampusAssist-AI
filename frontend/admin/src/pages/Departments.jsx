import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Plus } from 'lucide-react'
import { api } from '../api/client'
import { Button, ErrorNote, Field, Loading, Modal, PageHeader, Panel, Table, inputCls } from '../components/ui'

export default function Departments() {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(null)
  const { data, isLoading, error } = useQuery({ queryKey: ['departments'], queryFn: api.departments })
  const del = useMutation({
    mutationFn: (id) => api.deleteDepartment(id),
    onSuccess: () => { toast.success('Department deleted'); qc.invalidateQueries({ queryKey: ['departments'] }) },
    onError: (e) => toast.error(e.message),
  })
  return (
    <>
      <PageHeader title="Departments" description="Tickets are routed here by topic. New-ticket alerts go to each department's email." actions={<Button onClick={() => setEditing('new')}><Plus size={16} /> Add department</Button>} />
      <Panel>
        {isLoading && <Loading />}
        <ErrorNote error={error} />
        {data && (
          <Table head={['Department', 'Short name', 'Alert email', '']}>
            {data.map((d) => (
              <tr key={d.id}>
                <td className="px-5 py-3 font-semibold">{d.name}</td>
                <td className="px-5 py-3 text-slate2">{d.slug}</td>
                <td className="px-5 py-3">{d.email || <span className="text-slate2">Not set</span>}</td>
                <td className="px-5 py-3 text-right">
                  <div className="flex justify-end gap-3">
                    <Button variant="link" onClick={() => setEditing(d)}>Edit</Button>
                    <Button variant="link" className="!text-danger" onClick={() => window.confirm(`Delete ${d.name}? Its tickets become unassigned.`) && del.mutate(d.id)}>Delete</Button>
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Panel>
      {editing && <DeptModal dept={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </>
  )
}

function DeptModal({ dept, onClose }) {
  const qc = useQueryClient()
  const { register, handleSubmit, formState: { errors } } = useForm({ defaultValues: { name: dept?.name || '', slug: dept?.slug || '', email: dept?.email || '', description: dept?.description || '' } })
  const save = useMutation({
    mutationFn: (v) => {
      const body = { ...v, email: v.email || null, description: v.description || null }
      return dept ? api.updateDepartment(dept.id, body) : api.createDepartment(body)
    },
    onSuccess: () => { toast.success('Department saved'); qc.invalidateQueries({ queryKey: ['departments'] }); onClose() },
    onError: (e) => toast.error(e.message),
  })
  return (
    <Modal title={dept ? 'Edit department' : 'Add department'} onClose={onClose}>
      <form onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
        <Field label="Name" error={errors.name && 'Enter a name.'}><input className={inputCls} {...register('name', { required: true, minLength: 2 })} /></Field>
        <Field label="Short name" hint="Lowercase letters, numbers and dashes, e.g. exam-cell. Ticket routing uses it." error={errors.slug && 'Use lowercase letters, numbers and dashes.'}>
          <input className={inputCls} {...register('slug', { required: true, pattern: /^[a-z0-9-]+$/ })} />
        </Field>
        <Field label="Alert email"><input type="email" className={inputCls} {...register('email')} /></Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={save.isPending}>Save department</Button>
        </div>
      </form>
    </Modal>
  )
}
