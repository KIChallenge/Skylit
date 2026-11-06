"use client";

import { MessageCircle, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { AppHeader } from "@/components/layout/app-header";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { AttachmentControl } from "@/features/attachments";
import { PersonaMenu } from "@/features/auth";
import { DepthSwitch } from "@/features/settings/depth-switch";
import { ResultCards } from "@/features/cards";
import { SamplerSessionCard } from "@/features/cards/sampler-session-card";
import { groupSamplerTurns } from "@/features/cards/sampler-session";
import { CalendarPanel, CalendarProvider } from "@/features/calendar";
import { CasePanel } from "@/features/case";
import { LocationDialog, LocationProvider, useLocation } from "@/features/location";
import { ConversationView, EmergencyBanner } from "@/features/chat";
import { createConversationController, type ConversationController } from "@/features/conversation/controller";
import { createConversationState } from "@/features/conversation/model";
import { AnswerFooter } from "@/features/transparency";
import { createUploadController, type UploadController, type UploadResult, type UploadState } from "@/features/upload/controller";
import { api, TransportError, type Conversation, type ConversationSummary, type Me, type MessageCreate } from "@/lib/api";
import { config } from "@/lib/config";
import { cn } from "@/lib/utils";

import { bridgeConversation } from "./bridge";
import { EntryFrame, sortConversations } from "./entry-screens";

type Loaded = { me: Me; conversation: Conversation; conversations: ConversationSummary[] };
type LoadResult = { id: string; attempt: number } & (
  | { status: "ready"; data: Loaded }
  | { status: "error" }
  | { status: "missing" }
);

export function ChatScreen({ conversationId }: { conversationId: string }) {
  const router = useRouter();
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<LoadResult | null>(null);
  useEffect(() => {
    const request = new AbortController();
    let active = true;
    void (async () => {
      try {
        const options = { signal: request.signal };
        const me = await api.getMe(options);
        if (!active) return;
        const [conversation, conversations] = await Promise.all([
          api.getConversation(conversationId, options), api.listConversations(options),
        ]);
        if (active) setResult({ id: conversationId, attempt, status: "ready", data: { me, conversation, conversations } });
      } catch (error) {
        if (!active) return;
        if (error instanceof TransportError && error.status === 401) router.replace("/login");
        else setResult({ id: conversationId, attempt, status: error instanceof TransportError && error.status === 404 ? "missing" : "error" });
      }
    })();
    return () => { active = false; request.abort(); };
  }, [conversationId, attempt, router]);

  const retry = () => setAttempt((value) => value + 1);
  if (result?.id !== conversationId || result.attempt !== attempt) {
    return <AppShell header={<AppHeader />} conversation={
      <ConversationView messages={[]} responseText="" sending={false} loading onSend={() => {}} onRetry={retry} />
    } casePanel={<CasePanel case={null} isLoading onRetry={retry} onCaseChange={() => {}} />} />;
  }
  if (result.status === "missing") {
    return <EntryFrame><EmptyState icon={MessageCircle} title="Dieses Gespräch wurde nicht gefunden."
      description="Öffnen Sie ein vorhandenes Gespräch oder starten Sie ein neues Gespräch."
      action={<Button asChild variant="secondary"><Link href="/">Zu meinen Gesprächen</Link></Button>} /></EntryFrame>;
  }
  if (result.status === "error") {
    return <EntryFrame><ErrorState title="Ihr Gespräch konnte nicht geladen werden." onRetry={retry} /></EntryFrame>;
  }
  return <LoadedChat key={`${conversationId}-${attempt}`} {...result.data} />;
}

type Attachment = { file: File; controller: UploadController; promise: Promise<UploadResult> };

function LoadedChat(props: Loaded) {
  return <LocationProvider><LoadedChatView {...props} /><LocationDialog /></LocationProvider>;
}

function LoadedChatView({ me, conversation, conversations }: Loaded) {
  const router = useRouter();
  const location = useLocation();
  const [state, setState] = useState(() => createConversationState(conversation));
  const [displayedCase, setDisplayedCase] = useState(conversation.case);
  const [conversationList, setConversationList] = useState(conversations);
  const alive = useRef(true);
  const controllerRef = useRef<ConversationController | null>(null);
  const attachment = useRef<Attachment | null>(null);
  const [uploadState, setUploadState] = useState<UploadState | null>(null);
  const [waitingForUpload, setWaitingForUpload] = useState(false);
  const sending = useRef(false);
  const lastRequest = useRef<MessageCreate | null>(null);
  const [unsent, setUnsent] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(false);
  const createRequest = useRef<AbortController | null>(null);

  // A finished answer can name the conversation (case title, first message). Refresh the list
  // quietly; on failure the previous list stays.
  const completedMessageId = state.completedMessageId;
  useEffect(() => {
    if (!completedMessageId) return;
    const request = new AbortController();
    api.listConversations({ signal: request.signal })
      .then((list) => { if (!request.signal.aborted) setConversationList(list); })
      .catch(() => {});
    return () => request.abort();
  }, [completedMessageId]);

  useEffect(() => {
    alive.current = true;
    let previousCase = conversation.case;
    let emergencyShown = false;
    const controller = createConversationController(api, (next) => {
      if (!alive.current) return;
      // The emergency banner must paint before any AI text. Commit it on its own, so a stream
      // chunk that carries the emergency event and the first text cannot render both at once.
      if (next.emergency && !emergencyShown) flushSync(() => setState(next));
      else setState(next);
      emergencyShown = next.emergency !== null;
      // Text events must not replace a case updated through CasePanel.
      if (next.case !== previousCase) {
        previousCase = next.case;
        setDisplayedCase(next.case);
      }
      if (next.error?.kind === "transport" && next.error.status === 401) router.replace("/login");
    }, conversation);
    controllerRef.current = controller;
    return () => {
      alive.current = false;
      controllerRef.current = null;
      controller.abort();
      attachment.current?.controller.cancel();
      createRequest.current?.abort();
    };
  }, [conversation, router]);

  function removeAttachment() {
    const previous = attachment.current;
    attachment.current = null;
    previous?.controller.cancel();
    setUploadState(null);
  }

  function selectFile(file: File) {
    removeAttachment();
    const upload = createUploadController({
      api,
      onProgress: (next) => {
        if (alive.current) setUploadState(next.status === "cancelled" ? null : next);
      },
      pollIntervalMs: 1000,
      totalTimeoutMs: config.streamIdleTimeoutMs,
      requestTimeoutMs: config.apiTimeoutMs,
    });
    attachment.current = { file, controller: upload, promise: upload.start(file, conversation.id) };
  }

  async function send(content: string, retry = false) {
    const controller = controllerRef.current;
    if (!controller || sending.current || controller.getState().status === "streaming") return;
    sending.current = true;
    setUnsent(null);
    const selected = attachment.current;
    try {
      let documentIds = retry ? lastRequest.current?.document_ids ?? [] : [];
      if (selected) {
        setWaitingForUpload(true);
        const result = await selected.promise;
        if (!alive.current || attachment.current !== selected) return;
        if (result.status !== "ready") {
          if (result.status === "failed") setUnsent(content);
          return;
        }
        documentIds = [result.documentId];
      }
      if (!alive.current) return;
      // The backend uses the location for distances only and never stores it.
      // Read the ref: the card's location search calls a `send` from before the permission.
      const coords = location?.current();
      const message: MessageCreate = coords
        ? { content, document_ids: documentIds, location: coords }
        : { content, document_ids: documentIds };
      lastRequest.current = message;
      const response = controller.send(message);
      if (attachment.current === selected) removeAttachment();
      setWaitingForUpload(false);
      await response;
    } finally {
      sending.current = false;
      if (alive.current) setWaitingForUpload(false);
    }
  }

  async function newConversation() {
    if (createRequest.current) return;
    const request = new AbortController();
    createRequest.current = request;
    setCreating(true);
    setCreateError(false);
    try {
      const created = await api.createConversation(undefined, { signal: request.signal });
      if (alive.current) router.push(`/chat/${created.id}`);
    } catch (error) {
      if (!alive.current) return;
      if (error instanceof TransportError && error.status === 401) router.replace("/login");
      else setCreateError(true);
    } finally {
      createRequest.current = null;
      if (alive.current) setCreating(false);
    }
  }

  const bridge = bridgeConversation(state);
  // One card per SAMPLER intake: later questions and their answers do not get own bubbles.
  const sampler = groupSamplerTurns(bridge.messages, (message) => bridge.details.get(message.id)?.cards, {
    streaming: state.status === "streaming",
    text: bridge.responseText,
    cards: state.currentAnswer?.cards,
  });
  const visibleMessages = bridge.messages.filter((message) => !sampler.hidden.has(message.id));
  const openSteps = displayedCase.steps.filter((step) => step.status !== "done").length;
  return <CalendarProvider conversationId={conversation.id}><AppShell
    header={<AppHeader actions={<PersonaMenu me={me} onLoggedOut={() => router.replace("/login")} />} />}
    casePanelLabel={`Mein Fall · ${openSteps} offen`}
    emergencyBanner={state.emergency ? <EmergencyBanner {...state.emergency} /> : null}
    navigation={<div className="flex min-w-0 flex-col gap-4 p-4">
      <h2 className="text-heading">Gespräche</h2>
      <Button variant="secondary" disabled={creating} onClick={() => void newConversation()}><Plus aria-hidden />Neues Gespräch</Button>
      <p role="status" className="text-caption text-text-secondary">{creating ? "Gespräch wird erstellt…" : ""}</p>
      {createError ? <ErrorState title="Das Gespräch konnte nicht erstellt werden." onRetry={() => void newConversation()} /> : null}
      <ul className="space-y-2">{sortConversations(conversationList).map((item) => <li key={item.id}>
        <Link href={`/chat/${item.id}`} aria-current={item.id === conversation.id ? "page" : undefined}
          className={cn("flex min-w-0 flex-col gap-2 rounded-md p-3 text-body hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring",
            item.id === conversation.id && "bg-accent-subtle text-accent-text")}>
          <span className="line-clamp-2 wrap-anywhere" title={item.title || undefined}>{item.title || "Neues Gespräch"}</span>
          <span className="text-caption text-text-secondary">{new Intl.DateTimeFormat("de-AT", { dateStyle: "medium" }).format(new Date(item.updated_at))}</span>
          <Badge variant="neutral" className="self-start tabular">{item.id === conversation.id ? openSteps : item.open_steps} offen</Badge>
        </Link>
      </li>)}</ul>
    </div>}
    casePanel={<CasePanel case={displayedCase} onRetry={() => {}} onCaseChange={setDisplayedCase} />}
    calendar={<CalendarPanel />}
    conversation={<>
      {unsent ? <div className="p-4"><ErrorState title="Ihre Nachricht wurde nicht gesendet."
        description="Versuchen Sie den Upload erneut oder entfernen Sie das Dokument."
        onRetry={() => void send(unsent)} /></div> : null}
      <ConversationView messages={visibleMessages} responseText={sampler.hideLiveText ? "" : bridge.responseText}
        headerActions={<DepthSwitch key={me.user_id} initial={me.profile.depth} />}
        sending={state.status === "streaming" || waitingForUpload}
        progressLabel={waitingForUpload ? "Dokument wird gelesen…" : state.progressLabel ?? undefined}
        error={state.error?.message}
        onSend={(content) => void send(content)}
        onRetry={() => { if (lastRequest.current) void send(lastRequest.current.content, true); }}
        renderMessageCards={(message) => {
          const session = sampler.sessions.get(message.id);
          if (session) return <SamplerSessionCard session={session} onAnswer={(content) => void send(content)} />;
          // ResultCards shows an empty state for an empty list. Messages without cards render nothing.
          const cards = bridge.details.get(message.id)?.cards ?? [];
          // Only the latest answer can hold the open SAMPLER question.
          const latest = message.id === bridge.messages.at(-1)?.id && state.status !== "streaming";
          return cards.length ? <ResultCards cards={cards} latest={latest} onSend={(content) => void send(content)} /> : null;
        }}
        renderAnswerFooter={(message) => {
          const detail = bridge.details.get(message.id);
          return <AnswerFooter messageId={detail?.transparencyMessageId ?? null} initialSources={detail?.sources} />;
        }}
        attachment={<AttachmentControl filename={uploadState?.filename}
          phase={uploadState?.status === "cancelled" ? null : uploadState?.status}
          documentId={uploadState?.documentId}
          error={uploadState?.status === "failed" ? uploadState.error.message : null}
          onFileSelected={selectFile} onRemove={removeAttachment}
          onRetry={() => { if (attachment.current) selectFile(attachment.current.file); }} />}
      />
    </>}
  /></CalendarProvider>;
}
