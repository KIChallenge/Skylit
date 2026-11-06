import type { Metadata } from "next";

import { ChatScreen } from "@/features/lotse";

export const metadata: Metadata = { title: "Ihr Gespräch" };

export default async function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ChatScreen key={id} conversationId={id} />;
}
