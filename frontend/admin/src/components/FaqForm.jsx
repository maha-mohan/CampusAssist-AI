import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '../api/client'
import { useAuth } from '../store/auth'
import { Button, Field, inputCls } from './ui'

/** Create or edit an FAQ. Used on the FAQs page and as "Answer this" from Needs attention. */
export default function FaqForm({ faq, initialQuestion = '', onDone }) {
  const qc = useQueryClient()
  const user = useAuth((s) => s.user)
  const { data: departments } = useQuery({ queryKey: ['departments'], queryFn: api.departments })
  const { register, handleSubmit, formState: { errors } } = useForm({
    defaultValues: {
      question: faq?.question || initialQuestion,
      answer: faq?.answer || '',
      department_id: faq?.department_id ?? (user?.role === 'dept_admin' ? user.department_id : ''),
      is_active: faq?.is_active ?? true,
    },
  })

  const save = useMutation({
    mutationFn: (body) => (faq ? api.updateFaq(faq.id, body) : api.createFaq(body)),
    onSuccess: () => {
      toast.success(faq ? 'FAQ saved' : 'FAQ added. The assistant uses it right away.')
      qc.invalidateQueries({ queryKey: ['faqs'] })
      onDone?.()
    },
    onError: (e) => toast.error(e.message),
  })

  const onSubmit = (v) =>
    save.mutate({ ...v, department_id: v.department_id ? Number(v.department_id) : null })

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4">
      <Field label="Question" error={errors.question && 'Write the question as a student would ask it (5+ characters).'}>
        <input className={inputCls} {...register('question', { required: true, minLength: 5 })} />
      </Field>
      <Field label="Answer" hint="Write the verified answer. Include exact dates, amounts and who to contact." error={errors.answer && 'Add an answer.'}>
        <textarea rows={5} className={inputCls} {...register('answer', { required: true, minLength: 2 })} />
      </Field>
      <Field label="Department">
        <select className={inputCls} disabled={user?.role === 'dept_admin'} {...register('department_id')}>
          <option value="">General</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </Field>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-[#1f2a5c]" {...register('is_active')} /> Use this FAQ in answers
      </label>
      <div className="flex justify-end gap-2">
        {onDone && <Button variant="ghost" onClick={onDone}>Cancel</Button>}
        <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : faq ? 'Save FAQ' : 'Add FAQ'}</Button>
      </div>
    </form>
  )
}
