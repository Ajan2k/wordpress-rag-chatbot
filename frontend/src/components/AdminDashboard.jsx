// frontend/src/components/AdminDashboard.jsx
/**
 * Admin Dashboard Component
 *
 * Provides controls for:
 *  1. Triggering the WordPress data sync (ETL pipeline)
 *  2. Viewing live progress with an animated progress bar
 *  3. Checking system health (WordPress DB + Qdrant status)
 */
import { useState, useEffect, useCallback } from 'react';
import { useTaskPolling } from '../hooks/useTaskPolling';
import './AdminDashboard.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function AdminDashboard() {
    const {
        taskId,
        taskState,
        progress,
        statusMsg,
        result,
        error,
        isPolling,
        triggerSync,
    } = useTaskPolling();

    const [systemStatus, setSystemStatus] = useState(null);
    const [statusLoading, setStatusLoading] = useState(false);

    // Fetch system status
    const fetchStatus = useCallback(async () => {
        setStatusLoading(true);
        try {
            const res = await fetch(`${API_BASE}/api/admin/status`);
            const data = await res.json();
            setSystemStatus(data);
        } catch (err) {
            setSystemStatus({ error: err.message });
        } finally {
            setStatusLoading(false);
        }
    }, []);

    // Fetch status on mount
    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    // Refresh status after sync completes
    useEffect(() => {
        if (taskState === 'SUCCESS') {
            fetchStatus();
        }
    }, [taskState, fetchStatus]);

    const stateColor = {
        PENDING: 'badge-warning',
        STARTED: 'badge-info',
        PROGRESS: 'badge-info',
        SUCCESS: 'badge-success',
        FAILURE: 'badge-danger',
    };

    return (
        <div className="admin-container">
            <div className="admin-header animate-fade-in">
                <div>
                    <h1 className="admin-title">⚙️ Admin Dashboard</h1>
                    <p className="admin-subtitle">
                        Manage WordPress data synchronisation &amp; system health
                    </p>
                </div>
            </div>

            <div className="admin-grid stagger">
                {/* ── Sync Card ───────────────────────────────────────── */}
                <div className="admin-card glass-card animate-fade-in">
                    <div className="card-header">
                        <h2>🔄 WordPress Data Sync</h2>
                        {taskState && (
                            <span className={`badge ${stateColor[taskState] || 'badge-info'}`}>
                                {taskState}
                            </span>
                        )}
                    </div>

                    <p className="card-desc">
                        Extract, chunk, embed, and upsert all published WordPress content
                        into the Qdrant vector database for RAG retrieval.
                    </p>

                    <button
                        className="btn btn-primary btn-sync"
                        onClick={triggerSync}
                        disabled={isPolling}
                        id="sync-button"
                    >
                        {isPolling ? '⏳ Syncing …' : '🚀 Start Full Sync'}
                    </button>

                    {/* Progress */}
                    {(isPolling || taskState === 'SUCCESS' || taskState === 'FAILURE') && (
                        <div className="sync-progress">
                            <div className="progress-header">
                                <span className="progress-label">{statusMsg || 'Waiting …'}</span>
                                <span className="progress-pct">{progress}%</span>
                            </div>
                            <div className="progress-track">
                                <div
                                    className="progress-fill"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>

                            {taskId && (
                                <p className="task-id-display">
                                    Task ID: <code>{taskId}</code>
                                </p>
                            )}
                        </div>
                    )}

                    {/* Success result */}
                    {taskState === 'SUCCESS' && result && (
                        <div className="sync-result success">
                            <p>✅ <strong>Sync Complete!</strong></p>
                            <ul>
                                <li>Documents extracted: <strong>{result.documents_extracted}</strong></li>
                                <li>Chunks processed: <strong>{result.chunks_processed}</strong></li>
                            </ul>
                        </div>
                    )}

                    {/* Error */}
                    {taskState === 'FAILURE' && error && (
                        <div className="sync-result failure">
                            <p>❌ <strong>Sync Failed</strong></p>
                            <p className="error-text">{error}</p>
                        </div>
                    )}
                </div>

                {/* ── System Status Card ──────────────────────────────── */}
                <div className="admin-card glass-card animate-fade-in">
                    <div className="card-header">
                        <h2>📊 System Status</h2>
                        <button
                            className="btn btn-secondary btn-sm"
                            onClick={fetchStatus}
                            disabled={statusLoading}
                        >
                            {statusLoading ? '…' : '🔃 Refresh'}
                        </button>
                    </div>

                    {systemStatus ? (
                        <div className="status-grid">
                            {/* WordPress */}
                            <div className="status-item">
                                <div className="status-icon wp">📝</div>
                                <div>
                                    <h3>WordPress Database</h3>
                                    {typeof systemStatus.wordpress?.published_posts === 'number' ? (
                                        <p className="status-value">
                                            {systemStatus.wordpress.published_posts}
                                            <span className="status-unit"> published posts</span>
                                        </p>
                                    ) : (
                                        <p className="status-error">
                                            {String(systemStatus.wordpress?.published_posts || 'Not connected')}
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Qdrant */}
                            <div className="status-item">
                                <div className="status-icon qdrant">🔷</div>
                                <div>
                                    <h3>Qdrant Vector DB</h3>
                                    {systemStatus.qdrant?.error ? (
                                        <p className="status-error">{systemStatus.qdrant.error}</p>
                                    ) : (
                                        <>
                                            <p className="status-value">
                                                {systemStatus.qdrant?.points_count ?? 0}
                                                <span className="status-unit"> vectors stored</span>
                                            </p>
                                            <p className="status-meta">
                                                Collection: {systemStatus.qdrant?.name} —
                                                Status: <span className="badge badge-success">{systemStatus.qdrant?.status}</span>
                                            </p>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <p className="status-loading">Loading system status …</p>
                    )}
                </div>
            </div>
        </div>
    );
}
