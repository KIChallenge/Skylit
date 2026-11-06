"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { AppHeader } from "@/components/layout/app-header";
import { ErrorState } from "@/components/ui/state";
import { PersonaLogin } from "@/features/auth";
import { api, TransportError, type CallOptions, type ConversationSummary } from "@/lib/api";

export function sortConversations(conversations: ConversationSummary[]) {
  return [...conversations].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
}

async function latestConversation(options: CallOptions) {
  const conversations = sortConversations(await api.listConversations(options));
  options.signal?.throwIfAborted();
  return conversations[0]?.id ?? (await api.createConversation(undefined, options)).id;
}

export function EntryFrame({ children }: { children: ReactNode }) {
  return <div className="min-h-dvh text-text">
    <header className="px-4 py-4 sm:px-6"><AppHeader /></header>
    <main className="mx-auto max-w-content px-4 py-10 sm:px-6 sm:py-16">{children}</main>
  </div>;
}

function ConversationRedirect({ checkSession }: { checkSession: boolean }) {
  const router = useRouter();
  const [attempt, setAttempt] = useState(0);
  const [failedAttempt, setFailedAttempt] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void (async () => {
      try {
        if (checkSession) await api.getMe({ signal: controller.signal });
        if (!active) return;
        const id = await latestConversation({ signal: controller.signal });
        if (active) {
          if (checkSession) router.replace(`/chat/${id}`);
          else router.push(`/chat/${id}`);
        }
      } catch (error) {
        if (!active) return;
        if (error instanceof TransportError && error.status === 401) router.replace("/login");
        else setFailedAttempt(attempt);
      }
    })();
    return () => { active = false; controller.abort(); };
  }, [attempt, checkSession, router]);

  return failedAttempt === attempt
    ? <ErrorState title="Ihr Gespräch konnte nicht geöffnet werden." onRetry={() => setAttempt((value) => value + 1)} />
    : <p role="status" className="text-body text-text-secondary">Ihr Gespräch wird geöffnet…</p>;
}

export function HomeRedirect() {
  return <EntryFrame><ConversationRedirect checkSession /></EntryFrame>;
}

export function LoginScreen() {
  const [authenticated, setAuthenticated] = useState(false);
  return <EntryFrame>{authenticated
    ? <ConversationRedirect checkSession={false} />
    : <PersonaLogin onAuthenticated={() => setAuthenticated(true)} />}</EntryFrame>;
}
