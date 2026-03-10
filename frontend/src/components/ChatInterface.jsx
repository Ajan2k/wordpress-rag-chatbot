// frontend/src/components/ChatInterface.jsx
/**
 * Chat Interface Component
 *
 * A premium, dark-mode chat UI that streams answers from the RAG backend
 * via Server-Sent Events. Features animated typing indicators, markdown
 * rendering, source document citations, and a floating input bar.
 */
import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { useChatStream } from '../hooks/useChatStream';
import './ChatInterface.css';

// ── Suggested starter questions ────────────────────────────────
const SUGGESTIONS = [
    '🩺 What are the symptoms of Type 2 Diabetes?',
    '💊 What are common treatments for hypertension?',
    '🥗 What foods help reduce cholesterol?',
    '🏥 When should I see a doctor for a headache?',
];

export default function ChatInterface() {
    const { messages, isStreaming, sendMessage, stopStreaming, clearMessages } =
        useChatStream();
    const [input, setInput] = useState('');
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    // Auto-scroll to latest message
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!input.trim()) return;
        sendMessage(input);
        setInput('');
    };

    const handleSuggestion = (text) => {
        sendMessage(text);
    };

    return (
        <div className="chat-container">
            {/* Header */}
            <div className="chat-header glass-card">
                <div className="chat-header-left">
                    <div className="chat-logo">
                        <span className="logo-icon">🧬</span>
                        <div>
                            <h1 className="chat-title">Herald Kitchen AI</h1>
                            <p className="chat-subtitle">Healthcare Knowledge Assistant</p>
                        </div>
                    </div>
                </div>
                <div className="chat-header-right">
                    {messages.length > 0 && (
                        <button
                            className="btn btn-secondary btn-sm"
                            onClick={clearMessages}
                            title="Clear conversation"
                        >
                            🗑️ Clear
                        </button>
                    )}
                    <span className={`status-dot ${isStreaming ? 'streaming' : 'idle'}`} />
                </div>
            </div>

            {/* Messages Area */}
            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="chat-welcome animate-fade-in">
                        <div className="welcome-icon">🏥</div>
                        <h2>Welcome to Herald Kitchen AI</h2>
                        <p>
                            Ask me anything about healthcare topics from our knowledge base.
                            I support <strong>multiple languages</strong> — just ask in your preferred language!
                        </p>
                        <div className="suggestions stagger">
                            {SUGGESTIONS.map((s, i) => (
                                <button
                                    key={i}
                                    className="suggestion-chip animate-fade-in"
                                    onClick={() => handleSuggestion(s)}
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`message-row ${msg.role} animate-fade-in`}
                    >
                        <div className={`message-bubble ${msg.role}`}>
                            {msg.role === 'user' ? (
                                <p>{msg.content}</p>
                            ) : (
                                <>
                                    <div className="markdown-content">
                                        {msg.content ? (
                                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                                        ) : (
                                            <div className="typing-dots">
                                                <span />
                                                <span />
                                                <span />
                                            </div>
                                        )}
                                    </div>
                                    {msg.isStreaming && msg.content && (
                                        <span className="cursor-blink">▊</span>
                                    )}
                                    {/* Source citations */}
                                    {!msg.isStreaming && msg.sources?.length > 0 && (
                                        <div className="sources-list">
                                            <p className="sources-title">📄 Sources</p>
                                            {msg.sources.map((src, i) => (
                                                <div key={i} className="source-chip">
                                                    <span className="source-num">{i + 1}</span>
                                                    <div>
                                                        <strong>{src.title}</strong>
                                                        <p>{src.content_preview?.slice(0, 120)}…</p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {msg.isError && (
                                        <span className="badge badge-danger">Error</span>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <form className="chat-input-bar glass-card" onSubmit={handleSubmit}>
                <input
                    ref={inputRef}
                    className="input chat-input"
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask a healthcare question in any language…"
                    disabled={isStreaming}
                    id="chat-input"
                />
                {isStreaming ? (
                    <button
                        type="button"
                        className="btn btn-danger btn-send"
                        onClick={stopStreaming}
                    >
                        ■ Stop
                    </button>
                ) : (
                    <button
                        type="submit"
                        className="btn btn-primary btn-send"
                        disabled={!input.trim()}
                        id="send-button"
                    >
                        Send ↗
                    </button>
                )}
            </form>
        </div>
    );
}
