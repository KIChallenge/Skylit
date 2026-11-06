"use client";

import { ArrowDown, MessageCircle, Search } from "lucide-react";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/ui/state";
import type { Message } from "@/lib/api";

import { Composer } from "./composer";

export type ConversationViewProps = {
  messages: Message[];
  responseText: string;
  sending: boolean;
  progressLabel?: string;
  /** A readable, localized message supplied by the controller. */
  error?: string | null;
  loading?: boolean;
  onSend: (content: string) => void;
  onRetry: () => void;
  renderMessageCards?: (message: Message) => ReactNode;
  renderAnswerFooter?: (message: Message) => ReactNode;
  /** Upload control and current attachment, owned by the upload feature. */
  attachment?: ReactNode;
  /** Controls beside the heading, e.g. the answer length switch. */
  headerActions?: ReactNode;
};

function AnswerText({ content }: { content: string }) {
  return (
    <div className="max-w-answer text-answer text-pretty wrap-anywhere [&_p]:whitespace-pre-wrap [&_p+p]:mt-4 [&_ul]:list-disc [&_ul]:ps-6 [&_ol]:list-decimal [&_ol]:ps-6 [&_li]:mt-2 [&_a]:text-accent-text [&_a]:underline [&_a]:underline-offset-4 [&_h1]:text-heading [&_h2]:text-heading [&_h3]:text-heading [&_h1]:my-4 [&_h2]:my-4 [&_h3]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-subtle [&_pre]:p-4 [&_blockquote]:border-s-2 [&_blockquote]:ps-4 [&_table]:block [&_table]:overflow-x-auto [&_td]:border [&_td]:p-2 [&_th]:border [&_th]:p-2">
      <Markdown remarkPlugins={[remarkGfm]} skipHtml components={{ img: () => null }}>{content}</Markdown>
    </div>
  );
}

export function ConversationView({
  messages, responseText, sending, progressLabel, error, loading = false,
  onSend, onRetry, renderMessageCards, renderAnswerFooter, attachment, headerActions,
}: ConversationViewProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const contents = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const [atBottom, setAtBottom] = useState(true);

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && follow.current) element.scrollTop = element.scrollHeight;
  }, [messages, responseText, sending, progressLabel, error, loading]);

  // Cards and footers can grow after their own asynchronous data arrives.
  useLayoutEffect(() => {
    const element = scroller.current;
    const content = contents.current;
    if (!element || !content || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (follow.current) element.scrollTop = element.scrollHeight;
    });
    observer.observe(content);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <section aria-label="Gespräch mit dem Lotsen" className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 pt-4 pb-2 sm:px-8 sm:pt-6">
        <div className="min-w-0">
          <h1 className="text-title">Ihr Gespräch</h1>
          <p className="mt-1 text-body text-text-secondary">Gemeinsam die nächsten Schritte finden.</p>
        </div>
        {headerActions}
      </div>
      <div
        ref={scroller}
        role="region"
        aria-label="Nachrichten"
        tabIndex={0}
        className="fade-y relative min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 sm:px-8"
        onScroll={(event) => {
          const element = event.currentTarget;
          follow.current = element.scrollHeight - element.scrollTop - element.clientHeight <= 32;
          setAtBottom(follow.current);
        }}
      >
        <div ref={contents} className="mx-auto flex max-w-answer flex-col gap-10">
          {!loading && !messages.length && !responseText && !sending && !error ? (
            <EmptyState icon={MessageCircle} title="Was beschäftigt Sie gerade?" description="Beschreiben Sie Ihre Lage. Der Lotse hilft Ihnen, passende Leistungen und zuständige Stellen zu finden." />
          ) : null}
          {messages.map((message) => (
            <article key={message.id} aria-label={message.role === "user" ? "Ihre Nachricht" : "Antwort des Lotsen"} className="min-w-0">
              <p className={`mb-2 text-label text-text-secondary${message.role === "user" ? " text-end" : ""}`}>{message.role === "user" ? "Sie" : "Lotse (KI)"}</p>
              {message.role === "user" ? (
                <div className="ms-auto w-fit max-w-full rounded-xl rounded-br-sm border border-accent-border/40 bg-accent-subtle px-5 py-3">
                  <p className="whitespace-pre-wrap text-body wrap-anywhere">{message.content}</p>
                </div>
              ) : <AnswerText content={message.content} />}
              {renderMessageCards ? <div className="mt-4 space-y-4">{renderMessageCards(message)}</div> : null}
              {message.role === "assistant" ? (
                <div className="mt-4">{renderAnswerFooter ? renderAnswerFooter(message) : (
                  <p className="text-caption text-text-secondary">Quellen und Modell nicht verfügbar. Sicherheit nicht verfügbar.</p>
                )}</div>
              ) : null}
            </article>
          ))}
          {responseText ? (
            <article aria-label="Laufende Antwort des Lotsen">
              <p className="mb-2 text-label text-text-secondary">Lotse (KI)</p>
              <AnswerText content={responseText} />
            </article>
          ) : null}
          <div role="status" aria-live="polite" aria-atomic="true">
            {loading || sending ? (
              <p className="flex items-center gap-2 text-label text-text-secondary">
                <Search aria-hidden className="size-4 shrink-0" />
                {progressLabel || (loading ? "Gespräch wird geladen…" : "Der Lotse bereitet Ihre Antwort vor…")}
              </p>
            ) : null}
          </div>
          {error ? <ErrorState title="Die Antwort konnte nicht geladen werden." description={error} onRetry={sending ? undefined : onRetry} /> : null}
        </div>
      </div>
      {!atBottom ? (
        <div className="flex justify-center px-4 py-2">
          <Button variant="secondary" onClick={() => {
            follow.current = true;
            setAtBottom(true);
            if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
          }}><ArrowDown aria-hidden />Zu neuen Inhalten</Button>
        </div>
      ) : null}
      <Composer sending={sending || loading} onSend={onSend} attachment={attachment} />
    </section>
  );
}
