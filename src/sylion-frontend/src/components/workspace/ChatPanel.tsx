"use client";

import React, { startTransition, useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import {
  Send,
  Paperclip,
  Loader2,
  Bot,
  User,
  HelpCircle,
  WifiOff,
  Plus,
  Sparkles,
} from "lucide-react";

interface ChatMessage {
  message_id: string;
  session_id: string;
  role: string;
  content: string;
  model_id: string;
  attachments: string;
  timestamp: number;
  created_at?: number;
}

interface ChatSession {
  session_id: string;
  title?: string;
}

export function ChatPanel() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";
  const searchParams = useSearchParams();
  const requestedSessionId = searchParams.get("session")?.trim() || "";

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Fetch sessions
  useEffect(() => {
    if (!backendLive) return;
    api.listChatSessions().then((d) => setSessions(d.sessions ?? [])).catch(() => {});
  }, [backendLive]);

  // Deep-link support: /workspace?session=<id> must open the persisted
  // discussion, otherwise Idea Vault creates real council output that the
  // operator cannot inspect through the dashboard.
  useEffect(() => {
    if (!backendLive || !requestedSessionId) return;
    startTransition(() => setActiveSessionId(requestedSessionId));
    api.getChatSession(requestedSessionId)
      .then((session) => {
        setSessions((prev) => {
          if (prev.some((item) => item.session_id === session.session_id)) return prev;
          return [session, ...prev];
        });
      })
      .catch(() => {});
  }, [backendLive, requestedSessionId]);

  // Fetch messages for active session
  useEffect(() => {
    if (!activeSessionId || !backendLive) return;
    startTransition(() => setLoading(true));
    api.listChatMessages(activeSessionId)
      .then((d) => { setMessages(d.messages ?? []); setLoading(false); scrollToBottom(); })
      .catch(() => setLoading(false));
  }, [activeSessionId, backendLive, scrollToBottom]);

  // Auto-refresh messages
  useEffect(() => {
    if (!activeSessionId || !backendLive) return;
    const interval = setInterval(() => {
      api.listChatMessages(activeSessionId)
        .then((d) => setMessages(d.messages ?? []))
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [activeSessionId, backendLive]);

  const createSession = async () => {
    if (!backendLive) return;
    try {
      const result = await api.createChatSession("New Chat", []);
      if (result.session_id) {
        setActiveSessionId(result.session_id);
        const d = await api.listChatSessions();
        setSessions(d.sessions ?? []);
      }
    } catch {}
  };

  const sendMessage = async () => {
    if (!input.trim() || !activeSessionId || sending) return;
    setSending(true);
    const text = input;
    setInput("");
    try {
      await api.sendChatMessage(activeSessionId, text);
      const d = await api.listChatMessages(activeSessionId);
      setMessages(d.messages ?? []);
      scrollToBottom();
    } catch {}
    setSending(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!backendLive) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <WifiOff className="w-8 h-8 text-sylion-red/50 mb-3" />
        <p className="text-xs text-muted-foreground">Backend nieosiągalny</p>
        <p className="text-[10px] text-muted-foreground mt-1">
          Start: <code className="text-primary">python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010</code>
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Session list */}
      <div className="w-48 shrink-0 border-r border-[rgba(148,163,184,0.06)] p-2 space-y-1 overflow-y-auto">
        <Button variant="ghost" size="sm" className="w-full justify-start text-[11px] h-7" onClick={createSession}>
          <Plus className="w-3 h-3 mr-1.5" /> Nowy czat
        </Button>
        {sessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => setActiveSessionId(s.session_id)}
            className={cn(
              "w-full text-left px-2.5 py-2 rounded-lg text-[11px] transition-colors",
              activeSessionId === s.session_id
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted/20"
            )}
          >
            <span className="truncate block">{s.title || s.session_id?.slice(0, 12)}</span>
          </button>
        ))}
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {!activeSessionId ? (
          <div className="flex-1 flex flex-col items-center justify-center">
            <Sparkles className="w-8 h-8 text-primary/30 mb-3" />
            <p className="text-xs text-muted-foreground">Wybierz lub utwórz sesję czatu</p>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((msg) => (
                <ChatBubble key={msg.message_id} message={msg} />
              ))}
              {loading && messages.length === 0 && (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="px-3 pb-3 pt-2 border-t border-[rgba(148,163,184,0.06)]">
              <div className="flex items-end gap-2">
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0" title="Dodaj plik">
                  <Paperclip className="w-3.5 h-3.5" />
                </Button>
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Wpisz wiadomość..."
                  rows={1}
                  className="flex-1 bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 resize-none min-h-[32px] max-h-[120px]"
                />
                <Button
                  size="sm"
                  className="h-8 w-8 p-0 shrink-0"
                  onClick={sendMessage}
                  disabled={!input.trim() || sending}
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isQuestion = message.role === "assistant_question";

  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className={cn(
          "w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5",
          isQuestion ? "bg-sylion-amber/15" : "bg-primary/10"
        )}>
          {isQuestion ? <HelpCircle className="w-3 h-3 text-sylion-amber" /> : <Bot className="w-3 h-3 text-primary" />}
        </div>
      )}
      <div className={cn(
        "max-w-[80%] rounded-xl px-3 py-2",
        isUser
          ? "bg-primary/10 border border-primary/15"
          : isQuestion
          ? "bg-sylion-amber/5 border border-sylion-amber/15"
          : "bg-muted/20 border border-[rgba(148,163,184,0.06)]"
      )}>
        {!isUser && message.model_id && (
          <p className="text-[9px] text-muted-foreground mb-1">{message.model_id}</p>
        )}
        <p className="text-xs leading-relaxed whitespace-pre-wrap">{message.content}</p>
        <p className="text-[9px] text-muted-foreground mt-1">
          {(message.timestamp || message.created_at) ? new Date((message.timestamp || message.created_at || 0) * 1000).toLocaleTimeString() : ""}
        </p>
      </div>
      {isUser && (
        <div className="w-6 h-6 rounded-full bg-muted/30 flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-3 h-3 text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
