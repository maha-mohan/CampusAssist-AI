import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { Globe, Upload } from 'lucide-react'
import { api } from '../api/client'
import { can, useAuth } from '../store/auth'
import { Badge, Button, Empty, ErrorNote, Field, Loading, Modal, PageHeader, Pager, Panel, Table, inputCls, filterCls } from '../components/ui'
import { fmtDate, titleCase } from '../lib/format'

const YEARS = ['2025-26', '2026-27', '2027-28']

export default function Documents() {
  const user = useAuth((s) => s.user)
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState({ q: '', status: '', doc_type: '' })
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(null) // 'upload' | 'url'
  const openId = params.get('open')

  const query = { ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), page }
  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', query],
    queryFn: () => api.documents(query),
    placeholderData: keepPreviousData,
    // Keep polling while something is still being processed.
    refetchInterval: (q) => (q.state.data?.items?.some((d) => ['pending', 'processing'].includes(d.status)) ? 2500 : false),
  })
  const { data: docTypes } = useQuery({ queryKey: ['doc-types'], queryFn: api.docTypes })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['documents'] })
    qc.invalidateQueries({ queryKey: ['overview'] })
  }
  const act = useMutation({
    mutationFn: ({ fn, msg }) => fn().then(() => msg),
    onSuccess: (msg) => { toast.success(msg); refresh() },
    onError: (e) => toast.error(e.message),
  })

  const editable = can(user, 'manageContent')

  return (
    <>
      <PageHeader
        title="Documents"
        description="Circulars, fee sheets, syllabi and policies the assistant answers from. Only active documents within their valid dates are used."
        actions={editable && (
          <>
            <Button variant="ghost" onClick={() => setModal('url')}><Globe size={16} /> Add web page</Button>
            <Button onClick={() => setModal('upload')}><Upload size={16} /> Upload document</Button>
          </>
        )}
      />
      <Panel>
        <form className="flex flex-wrap gap-2 border-b border-line px-5 py-3" onSubmit={(e) => e.preventDefault()}>
          <input type="search" placeholder="Search by title" value={filters.q} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, q: e.target.value })) }} className={`${filterCls} w-64`} />
          <select aria-label="Status" value={filters.status} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, status: e.target.value })) }} className={filterCls}>
            <option value="">Any status</option>
            {['active', 'processing', 'pending', 'failed', 'archived'].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </select>
          <select aria-label="Type" value={filters.doc_type} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, doc_type: e.target.value })) }} className={filterCls}>
            <option value="">Any type</option>
            {docTypes?.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
          </select>
        </form>
        {isLoading && <Loading />}
        <ErrorNote error={error} />
        {data && !data.items.length && (
          <Empty title="No documents yet">Upload the admission notification, fee structure and exam circulars first. Those cover most questions.</Empty>
        )}
        {data?.items.length > 0 && (
          <Table head={['Document', 'Type', 'Year', 'Department', 'Status', 'Added']}>
            {data.items.map((d) => (
              <tr key={d.id} className="align-top hover:bg-mist/60">
                <td className="px-5 py-3">
                  <button type="button" className="text-left font-semibold text-navy hover:underline" onClick={() => setParams({ open: d.id })}>{d.title}</button>
                  <p className="text-[12.5px] text-slate2">{d.source_url ? d.source_url : d.filename}{d.num_chunks ? ` · ${d.num_chunks} section${d.num_chunks === 1 ? '' : 's'}` : ''}</p>
                  {d.status === 'failed' && <p className="mt-1 max-w-sm text-[12.5px] text-danger">{d.error}</p>}
                  {editable && (
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
                      {d.status === 'active' && <Button variant="link" className="!text-[13px]" onClick={() => act.mutate({ fn: () => api.updateDocument(d.id, { status: 'archived' }), msg: 'Archived. The assistant no longer uses it.' })}>Archive</Button>}
                      {d.status === 'archived' && <Button variant="link" className="!text-[13px]" onClick={() => act.mutate({ fn: () => api.updateDocument(d.id, { status: 'active' }), msg: 'Restored' })}>Restore</Button>}
                      {['failed', 'active'].includes(d.status) && <Button variant="link" className="!text-[13px]" onClick={() => act.mutate({ fn: () => api.reprocessDocument(d.id), msg: 'Reprocessing started' })}>Reprocess</Button>}
                      <Button variant="link" className="!text-[13px] !text-danger" onClick={() => window.confirm(`Delete "${d.title}" permanently?`) && act.mutate({ fn: () => api.deleteDocument(d.id), msg: 'Document deleted' })}>Delete</Button>
                    </div>
                  )}
                </td>
                <td className="whitespace-nowrap px-5 py-3">{titleCase(d.doc_type)}</td>
                <td className="whitespace-nowrap px-5 py-3">{d.academic_year || '—'}</td>
                <td className="whitespace-nowrap px-5 py-3 text-slate2">{d.department?.name || '—'}</td>
                <td className="px-5 py-3"><Badge value={d.status} /></td>
                <td className="whitespace-nowrap px-5 py-3 text-slate2">{fmtDate(d.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
        {data && <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      </Panel>

      {modal === 'upload' && <UploadModal docTypes={docTypes} existing={data?.items || []} onClose={() => setModal(null)} onDone={refresh} />}
      {modal === 'url' && <UrlModal docTypes={docTypes} onClose={() => setModal(null)} onDone={refresh} />}
      {openId && <ChunksModal id={openId} onClose={() => setParams({})} />}
    </>
  )
}

function MetaFields({ meta, setMeta, docTypes, departments, user }) {
  const set = (k) => (e) => setMeta((m) => ({ ...m, [k]: e.target.value }))
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Type">
          <select className={inputCls} value={meta.doc_type} onChange={set('doc_type')}>
            {docTypes?.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
          </select>
        </Field>
        <Field label="Academic year" hint="Answers prefer the current year.">
          <select className={inputCls} value={meta.academic_year} onChange={set('academic_year')}>
            <option value="">Not year-specific</option>
            {YEARS.map((y) => <option key={y}>{y}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Department">
        <select className={inputCls} value={meta.department_id} onChange={set('department_id')} disabled={user?.role === 'dept_admin'}>
          <option value="">General</option>
          {departments?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </Field>
    </>
  )
}

function UploadModal({ docTypes, existing, onClose, onDone }) {
  const user = useAuth((s) => s.user)
  const { data: departments } = useQuery({ queryKey: ['departments'], queryFn: api.departments })
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [progress, setProgress] = useState(0)
  const [meta, setMeta] = useState({
    doc_type: 'circular', academic_year: '', department_id: user?.role === 'dept_admin' ? user.department_id : '', valid_from: '', valid_to: '', replaces_document_id: '',
  })
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    multiple: false,
    maxSize: 25 * 1024 * 1024,
    accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'], 'text/plain': ['.txt'], 'text/markdown': ['.md'], 'text/html': ['.html', '.htm'] },
    onDrop: (files, rejected) => {
      if (rejected.length) toast.error('Use a PDF, Word (.docx), text or HTML file under 25 MB.')
      if (files[0]) {
        setFile(files[0])
        if (!title) setTitle(files[0].name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '))
      }
    },
  })

  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('title', title)
      Object.entries(meta).forEach(([k, v]) => v !== '' && v != null && fd.append(k, v))
      return api.uploadDocument(fd, (e) => setProgress(Math.round((e.loaded / (e.total || 1)) * 100)))
    },
    onSuccess: () => { toast.success('Uploaded. Processing usually takes under a minute.'); onDone(); onClose() },
    onError: (e) => toast.error(e.message),
  })

  return (
    <Modal title="Upload document" onClose={onClose}>
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); if (file) upload.mutate() }}>
        <div {...getRootProps()} className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-8 text-center ${isDragActive ? 'border-marigold bg-marigold-soft' : 'border-line bg-mist'}`}>
          <input {...getInputProps()} />
          {file ? (
            <p className="font-semibold">{file.name} <span className="font-normal text-slate2">({(file.size / 1024 / 1024).toFixed(1)} MB)</span></p>
          ) : (
            <>
              <p className="font-semibold">Drop a file here, or click to choose</p>
              <p className="mt-1 text-[13px] text-slate2">PDF, Word, text or HTML, up to 25 MB. Scanned PDFs are read with OCR.</p>
            </>
          )}
        </div>
        <Field label="Title" hint="Students see this as the source of an answer.">
          <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} required />
        </Field>
        <MetaFields meta={meta} setMeta={setMeta} docTypes={docTypes} departments={departments} user={user} />
        <div className="grid grid-cols-2 gap-3">
          <Field label="Valid from (optional)"><input type="date" className={inputCls} value={meta.valid_from} onChange={(e) => setMeta((m) => ({ ...m, valid_from: e.target.value }))} /></Field>
          <Field label="Valid until (optional)" hint="Stops being used after this date."><input type="date" className={inputCls} value={meta.valid_to} onChange={(e) => setMeta((m) => ({ ...m, valid_to: e.target.value }))} /></Field>
        </div>
        <Field label="Replaces an older document (optional)" hint="The older version is archived so answers don't mix the two.">
          <select className={inputCls} value={meta.replaces_document_id} onChange={(e) => setMeta((m) => ({ ...m, replaces_document_id: e.target.value }))}>
            <option value="">None</option>
            {existing.filter((d) => d.status === 'active').map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
          </select>
        </Field>
        <div className="flex items-center justify-end gap-2">
          {upload.isPending && <span className="mr-auto text-sm text-slate2">Uploading {progress}%</span>}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={!file || upload.isPending}>Upload</Button>
        </div>
      </form>
    </Modal>
  )
}

function UrlModal({ docTypes, onClose, onDone }) {
  const user = useAuth((s) => s.user)
  const { data: departments } = useQuery({ queryKey: ['departments'], queryFn: api.departments })
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [meta, setMeta] = useState({ doc_type: 'website', academic_year: '', department_id: user?.role === 'dept_admin' ? user.department_id : '' })
  const add = useMutation({
    mutationFn: () => api.addUrl({ url, title: title || undefined, doc_type: meta.doc_type, academic_year: meta.academic_year || null, department_id: meta.department_id ? Number(meta.department_id) : null }),
    onSuccess: () => { toast.success('Web page added. Reprocess it whenever the page changes.'); onDone(); onClose() },
    onError: (e) => toast.error(e.message),
  })
  return (
    <Modal title="Add a web page" onClose={onClose}>
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
        <Field label="Page address" hint="A public page of the college website, e.g. the admissions page.">
          <input type="url" required placeholder="https://www.college.edu/admissions" className={inputCls} value={url} onChange={(e) => setUrl(e.target.value)} />
        </Field>
        <Field label="Title (optional)"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        <MetaFields meta={meta} setMeta={setMeta} docTypes={docTypes} departments={departments} user={user} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={add.isPending}>Add page</Button>
        </div>
      </form>
    </Modal>
  )
}

function ChunksModal({ id, onClose }) {
  const doc = useQuery({ queryKey: ['document', id], queryFn: () => api.document(id) })
  const chunks = useQuery({ queryKey: ['chunks', id], queryFn: () => api.documentChunks(id) })
  return (
    <Modal title={doc.data?.title || 'Document'} onClose={onClose} wide>
      <p className="mb-4 text-sm text-slate2">
        This is the text the assistant reads, split into sections. If a section looks garbled (common with scanned
        tables), fix the source file and upload it again.{' '}
        {doc.data?.status === 'active' && <a className="font-semibold text-navy underline" href={api.documentFileUrl(id)} target="_blank" rel="noreferrer">Open original</a>}
      </p>
      {chunks.isLoading && <Loading />}
      <ErrorNote error={chunks.error} />
      {chunks.data && !chunks.data.length && <Empty title="No text extracted yet" />}
      <ol className="max-h-[60vh] space-y-3 overflow-y-auto">
        {chunks.data?.map((c) => (
          <li key={c.id} className="rounded-md border border-line p-3">
            <p className="mb-1 text-[12.5px] text-slate2">Section {c.chunk_index + 1}{c.page_no ? `, page ${c.page_no}` : ''}</p>
            <pre className="whitespace-pre-wrap font-sans text-[14px] leading-relaxed">{c.content}</pre>
          </li>
        ))}
      </ol>
    </Modal>
  )
}
