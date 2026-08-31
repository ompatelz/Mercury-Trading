import { MessageSquarePlus } from "lucide-react";

export type ResearchMessage = { role: "user" | "assistant"; content: string };

export function ResearchSessionToolbar({ messageCount, onNewConversation }: { messageCount: number; onNewConversation: () => void }) {
  const turns = Math.ceil(messageCount / 2);
  return <div className="researchSessionToolbar"><span aria-live="polite">{turns ? `${turns} research turn${turns === 1 ? "" : "s"}` : "New conversation"}</span><button type="button" onClick={onNewConversation} aria-label="Start a new research conversation"><MessageSquarePlus size={14} /> New conversation</button></div>;
}
