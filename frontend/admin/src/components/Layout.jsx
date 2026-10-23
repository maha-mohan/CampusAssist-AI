import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, Building2, CircleHelp, FileText, Inbox, LayoutDashboard, LogOut, Menu, MessagesSquare, TriangleAlert, UserCog, Users } from 'lucide-react'
import { can, useAuth } from '../store/auth'
import { api } from '../api/client'

export default function Layout() {
  const { user, logout } = useAuth()
  const [navOpen, setNavOpen] = useState(false)
  const { data: overview } = useQuery({ queryKey: ['overview', 14], queryFn: () => api.overview(14), refetchInterval: 60000 })

  const items = [
    { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/tickets', label: 'Tickets', icon: Inbox, count: overview?.open_tickets },
    { to: '/attention', label: 'Needs attention', icon: TriangleAlert },
    { to: '/conversations', label: 'Conversations', icon: MessagesSquare },
    { group: 'Knowledge base' },
    { to: '/documents', label: 'Documents', icon: FileText },
    { to: '/faqs', label: 'FAQs', icon: CircleHelp },
    ...(can(user, 'manageUsers')
      ? [{ group: 'Administration' }, { to: '/users', label: 'Users', icon: Users }, { to: '/departments', label: 'Departments', icon: Building2 }]
      : []),
  ]

  const nav = (
    <nav className="flex h-full flex-col bg-navy text-white">
      <div className="border-b border-white/10 px-5 py-5">
        <p className="flex items-center gap-2 text-[17px] font-bold"><BookOpen size={20} className="text-marigold" /> Help Desk</p>
        <p className="mt-0.5 text-[13px] text-white/70">College admin</p>
      </div>
      <ul className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {items.map((it, i) =>
          it.group ? (
            <li key={i} className="px-3 pb-1 pt-5 text-[12.5px] text-white/55">{it.group}</li>
          ) : (
            <li key={it.to}>
              <NavLink
                to={it.to}
                end={it.end}
                onClick={() => setNavOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md border-l-[3px] px-3 py-2 text-[15px] ${
                    isActive ? 'border-marigold bg-white/10 font-semibold' : 'border-transparent text-white/85 hover:bg-white/5'
                  }`
                }
              >
                <it.icon size={18} />
                <span className="flex-1">{it.label}</span>
                {it.count > 0 && <span className="rounded bg-marigold px-1.5 text-[12px] font-bold text-navy-deep">{it.count}</span>}
              </NavLink>
            </li>
          ),
        )}
      </ul>
      <div className="border-t border-white/10 px-4 py-4 text-sm">
        <p className="font-semibold">{user?.name}</p>
        <p className="text-[13px] text-white/65">{user?.role?.replace('_', ' ')}{user?.department ? `, ${user.department.name}` : ''}</p>
        <div className="mt-3 flex gap-3">
          <NavLink to="/account" onClick={() => setNavOpen(false)} className="inline-flex items-center gap-1.5 text-white/85 hover:text-white"><UserCog size={15} /> Account</NavLink>
          <button type="button" onClick={logout} className="inline-flex items-center gap-1.5 text-white/85 hover:text-white"><LogOut size={15} /> Sign out</button>
        </div>
      </div>
    </nav>
  )

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="sticky top-0 hidden h-screen lg:block">{nav}</aside>
      {navOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setNavOpen(false)}>
          <div className="h-full w-64" onClick={(e) => e.stopPropagation()}>{nav}</div>
        </div>
      )}
      <div className="min-w-0">
        <div className="flex items-center gap-3 border-b border-line bg-white px-4 py-3 lg:hidden">
          <button type="button" aria-label="Open menu" onClick={() => setNavOpen(true)} className="rounded p-1 hover:bg-mist"><Menu size={22} /></button>
          <span className="font-bold text-navy-deep">Help Desk</span>
        </div>
        <main className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8"><Outlet /></main>
      </div>
    </div>
  )
}
