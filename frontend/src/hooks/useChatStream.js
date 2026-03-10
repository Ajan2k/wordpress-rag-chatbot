// frontend/src/hooks/useChatStream.js
/**
 * Custom hook for streaming chat answers via Server-Sent Events (SSE).
 *
 * Sends the user's question to POST /api/chat/stream and progressively
 * appends tokens to the answer state as they arrive from the Groq API
 * through the FastAPI backend.
 */
import { useState, useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function useChatStream() {
    const [messages, setMessages] = useState([]);
    const [isStreaming, setStreaming] = useState(false);
    const abortRef = useRef(null);

    /**
     * Send a question and stream the response.
     * Each token is appended to the last assistant message in real-time.
     */
    const sendMessage = useCallback(async (question) => {
        if (!question.trim() || isStreaming) return;

        // Append user message
        const userMsg = { role: 'user', content: question, id: Date.now() };
        const assistantMsg = {
            role: 'assistant',
            content: '',
            sources: [],
            id: Date.now() + 1,
            isStreaming: true,
        };

        setMessages((prev) => [...prev, userMsg, assistantMsg]);
        setStreaming(true);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const res = await fetch(`${API_BASE}/api/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question }),
                signal: controller.signal,
            });

            if (!res.ok) {
                throw new Error(`Server error: ${res.status}`);
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const jsonStr = line.slice(6).trim();
                    if (!jsonStr) continue;

                    try {
                        const event = JSON.parse(jsonStr);

                        if (event.type === 'token') {
                            setMessages((prev) => {
                                const updated = [...prev];
                                const last = updated[updated.length - 1];
                                updated[updated.length - 1] = {
                                    ...last,
                                    content: last.content + event.content,
                                };
                                return updated;
                            });
                        }

                        if (event.type === 'sources') {
                            setMessages((prev) => {
                                const updated = [...prev];
                                const last = updated[updated.length - 1];
                                updated[updated.length - 1] = {
                                    ...last,
                                    sources: event.content,
                                };
                                return updated;
                            });
                        }

                        if (event.type === 'done') {
                            setMessages((prev) => {
                                const updated = [...prev];
                                const last = updated[updated.length - 1];
                                updated[updated.length - 1] = {
                                    ...last,
                                    isStreaming: false,
                                };
                                return updated;
                            });
                        }
                    } catch {
                        // skip malformed JSON
                    }
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    updated[updated.length - 1] = {
                        ...last,
                        content: `⚠️ Error: ${err.message}`,
                        isStreaming: false,
                        isError: true,
                    };
                    return updated;
                });
            }
        } finally {
            setStreaming(false);
            abortRef.current = null;
        }
    }, [isStreaming]);

    const stopStreaming = useCallback(() => {
        if (abortRef.current) {
            abortRef.current.abort();
            setStreaming(false);
        }
    }, []);

    const clearMessages = useCallback(() => {
        setMessages([]);
    }, []);

    return { messages, isStreaming, sendMessage, stopStreaming, clearMessages };
}
