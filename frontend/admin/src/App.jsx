import { Navigate, Route, Routes } from 'react-router-dom'
import { can, useAuth } from './store/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Overview from './pages/Overview'
import Tickets from './pages/Tickets'
import TicketDetail from './pages/TicketDetail'
import Attention from './pages/Attention'
import Conversations from './pages/Conversations'
import Documents from './pages/Documents'
import Faqs from './pages/Faqs'
import Users from './pages/Users'
import Departments from './pages/Departments'
import Account from './pages/Account'

function RequireAuth({ children }) {
  const token = useAuth((s) => s.token)
  return token ? children : <Navigate to="/login" replace />
}

function RequireRole({ action, children }) {
  const user = useAuth((s) => s.user)
  return can(user, action) ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Overview />} />
        <Route path="tickets" element={<Tickets />} />
        <Route path="tickets/:id" element={<TicketDetail />} />
        <Route path="attention" element={<Attention />} />
        <Route path="conversations" element={<Conversations />} />
        <Route path="conversations/:id" element={<Conversations />} />
        <Route path="documents" element={<Documents />} />
        <Route path="faqs" element={<Faqs />} />
        <Route path="users" element={<RequireRole action="manageUsers"><Users /></RequireRole>} />
        <Route path="departments" element={<RequireRole action="manageDepartments"><Departments /></RequireRole>} />
        <Route path="account" element={<Account />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
