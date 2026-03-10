// frontend/src/components/Navbar.jsx
/**
 * Top navigation bar with page routing.
 * Provides links between Chat and Admin views.
 */
import { NavLink } from 'react-router-dom';
import './Navbar.css';

export default function Navbar() {
    return (
        <nav className="navbar glass-card" id="main-nav">
            <NavLink to="/" className="nav-brand">
                <span className="brand-emoji">🧬</span>
                <span className="brand-text">Herald Kitchen</span>
            </NavLink>

            <div className="nav-links">
                <NavLink
                    to="/"
                    end
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    id="nav-chat"
                >
                    💬 Chat
                </NavLink>
                <NavLink
                    to="/admin"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    id="nav-admin"
                >
                    ⚙️ Admin
                </NavLink>
            </div>
        </nav>
    );
}
