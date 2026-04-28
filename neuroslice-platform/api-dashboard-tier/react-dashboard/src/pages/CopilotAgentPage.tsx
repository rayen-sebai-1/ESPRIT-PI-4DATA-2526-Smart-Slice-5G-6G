import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Bot, Send, Sparkles, User } from "lucide-react";
import axios from "axios";

import { agentApi, type CopilotQueryResponse } from "@/api/agentApi";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  createdAt: number;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function buildSessionId(userId: number | undefined): string {
  const seed = userId ?? "anon";
  let cached = sessionStorage.getItem("copilotSessionId");
  if (!cached) {
    cached = `dashboard-${seed}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    sessionStorage.setItem("copilotSessionId", cached);
  }
  return cached;
}

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data;
    if (detail && typeof detail === "object") {
      const inner = (detail as { detail?: unknown }).detail;
      if (inner && typeof inner === "object") {
        const innerMessage = (inner as { message?: string }).message;
        if (typeof innerMessage === "string" && innerMessage.trim()) {
          return innerMessage;
        }
      }
      const maybeMessage = (detail as { message?: string }).message;
      if (typeof maybeMessage === "string" && maybeMessage.trim()) {
        return maybeMessage;
      }
    }
    if (error.message) {
      return error.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected copilot service error.";
}

export function CopilotAgentPage() {
  usePageTitle("Copilot Agent");

  const { user } = useAuth();
  const sessionId = useMemo(() => buildSessionId(user?.id), [user?.id]);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      content:
        "Bonjour, je suis le Copilot NeuroSlice. Demandez-moi un etat de slice, une investigation KPI ou un resume des dernieres anomalies.",
      createdAt: Date.now(),
    },
  ]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const mutation = useMutation<CopilotQueryResponse, unknown, string>({
    mutationFn: async (query) => agentApi.askCopilot({ session_id: sessionId, query }),
    onSuccess: (data) => {
      setMessages((current) => [
        ...current,
        {
          id: generateId(),
          role: "assistant",
          content: data.answer || "(reponse vide)",
          createdAt: Date.now(),
        },
      ]);
    },
    onError: (error) => {
      setMessages((current) => [
        ...current,
        {
          id: generateId(),
          role: "error",
          content: extractErrorMessage(error),
          createdAt: Date.now(),
        },
      ]);
    },
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, mutation.isPending]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || mutation.isPending) {
      return;
    }
    setMessages((current) => [
      ...current,
      { id: generateId(), role: "user", content: trimmed, createdAt: Date.now() },
    ]);
    setDraft("");
    mutation.mutate(trimmed);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Agentic AI"
        title="Copilot Agent"
        description="Assistant conversationnel NOC. Le copilot interroge la telemetrie InfluxDB, l'etat live Redis et les sorties AIOps avant de repondre. La memoire conversationnelle est rattachee a votre session."
      />

      <Card className="flex h-[640px] flex-col">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-auto p-6">
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))}
          {mutation.isPending ? (
            <ChatBubble
              message={{
                id: "pending",
                role: "assistant",
                content: "Analyse en cours... (interrogation Influx + Redis + Ollama)",
                createdAt: Date.now(),
              }}
              pulsing
            />
          ) : null}
        </div>

        <form className="border-t border-border p-4" onSubmit={handleSubmit}>
          <div className="flex items-end gap-3">
            <Input
              placeholder="Posez une question (ex: Etat de slice-embb-01-02 sur 30 min)"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={mutation.isPending}
              autoComplete="off"
            />
            <Button type="submit" disabled={mutation.isPending || draft.trim().length === 0}>
              <Send size={16} />
              Envoyer
            </Button>
          </div>
          <p className="mt-2 text-xs text-mutedText">
            Session: <span className="font-mono text-slate-300">{sessionId}</span>
          </p>
        </form>
      </Card>
    </div>
  );
}

function ChatBubble({ message, pulsing }: { message: ChatMessage; pulsing?: boolean }) {
  const isUser = message.role === "user";
  const isError = message.role === "error";

  const wrapperAlign = isUser ? "justify-end" : "justify-start";
  const bubbleStyles = isUser
    ? "bg-accent text-[#0D0906]"
    : isError
      ? "border border-red-500/40 bg-red-500/10 text-red-200"
      : "border border-border bg-cardAlt text-slate-100";
  const Icon = isUser ? User : isError ? Sparkles : Bot;

  return (
    <div className={`flex ${wrapperAlign}`}>
      <div className={`flex max-w-[85%] gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl ${
            isUser ? "bg-accent/80 text-[#0D0906]" : "bg-accentSoft text-accent"
          }`}
        >
          <Icon size={16} />
        </div>
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 shadow-panel ${bubbleStyles} ${
            pulsing ? "animate-pulse" : ""
          }`}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
}
