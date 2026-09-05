import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './i18n'
import './index.css'
import App from './App.jsx'
import Login from './pages/Login.jsx'
import Credits from './pages/Credits.jsx'
import Admin from './pages/Admin.jsx'
import Legal from './pages/Legal.jsx'
import { AuthProvider } from './auth/AuthContext.jsx'
import RequireAuth from './auth/RequireAuth.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/legal" element={<Legal />} />
          <Route path="/" element={<RequireAuth><App /></RequireAuth>} />
          <Route path="/credits" element={<RequireAuth><Credits /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth adminOnly><Admin /></RequireAuth>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
