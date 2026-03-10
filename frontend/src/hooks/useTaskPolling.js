// frontend/src/hooks/useTaskPolling.js
/**
 * Custom hook for polling Celery task progress.
 *
 * After triggering a sync via POST /api/admin/sync, this hook
 * polls GET /api/admin/sync/{task_id} every 1.5 seconds to
 * retrieve real-time progress updates for the admin dashboard.
 */
import { useState, useCallback, useRef, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const POLL_INTERVAL = 1500; // ms

export function useTaskPolling() {
    const [taskId, setTaskId] = useState(null);
    const [taskState, setTaskState] = useState(null);
    const [progress, setProgress] = useState(0);
    const [statusMsg, setStatusMsg] = useState('');
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [isPolling, setPolling] = useState(false);
    const intervalRef = useRef(null);

    /**
     * Trigger a new WordPress sync and start polling.
     */
    const triggerSync = useCallback(async () => {
        setError(null);
        setResult(null);
        setProgress(0);
        setStatusMsg('Queuing sync job …');
        setTaskState('PENDING');

        try {
            const res = await fetch(`${API_BASE}/api/admin/sync`, {
                method: 'POST',
            });
            if (!res.ok) throw new Error(`Server error: ${res.status}`);

            const data = await res.json();
            setTaskId(data.task_id);
            setPolling(true);
        } catch (err) {
            setError(err.message);
            setTaskState('FAILURE');
        }
    }, []);

    /**
     * Poll the task status endpoint.
     */
    const pollStatus = useCallback(async (id) => {
        try {
            const res = await fetch(`${API_BASE}/api/admin/sync/${id}`);
            if (!res.ok) throw new Error(`Poll error: ${res.status}`);

            const data = await res.json();
            setTaskState(data.state);
            setProgress(data.progress);
            setStatusMsg(data.status_message);

            if (data.state === 'SUCCESS') {
                setResult(data.result);
                setPolling(false);
            }

            if (data.state === 'FAILURE') {
                setError(data.error || 'Task failed.');
                setPolling(false);
            }
        } catch (err) {
            setError(err.message);
            setPolling(false);
        }
    }, []);

    // Start / stop the polling interval
    useEffect(() => {
        if (isPolling && taskId) {
            intervalRef.current = setInterval(() => pollStatus(taskId), POLL_INTERVAL);
        }
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [isPolling, taskId, pollStatus]);

    return {
        taskId,
        taskState,
        progress,
        statusMsg,
        result,
        error,
        isPolling,
        triggerSync,
    };
}
