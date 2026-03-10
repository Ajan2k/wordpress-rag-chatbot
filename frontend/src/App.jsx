// frontend/src/App.jsx
/**
 * Root Application Component
 *
 * Sets up React Router with two pages:
 *  - /       → Chat Interface (user-facing)
 *  - /admin  → Admin Dashboard (data sync + system health)
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import ChatInterface from './components/ChatInterface';
import AdminDashboard from './components/AdminDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<ChatInterface />} />
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </BrowserRouter>
  );
}
