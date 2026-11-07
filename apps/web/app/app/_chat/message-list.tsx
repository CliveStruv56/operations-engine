import { PulsingDots } from "@/components/activity";
import { AnswerMarkdown, stripCiteMarkers } from "@/components/markdown";
import AssistantMessage from "./assistant-message";
import type { Message } from "./types";
import type { useMessageActions } from "./use-message-actions";

/** The conversation: settled messages, then the reply still streaming in.
 *  Every callback must stay referentially stable — AssistantMessage is
 *  memoised and a fresh arrow here would re-render every settled answer on
 *  every streamed frame. The actions from useMessageActions already are. */
export default function MessageList({
  messages,
  streamText,
  scopes,
  coverages,
  actions,
  readOnly,
}: {
  messages: Message[];
  streamText: string | null;
  scopes: Record<string, string>;
  coverages: Record<string, string>;
  actions: ReturnType<typeof useMessageActions>;
  readOnly: boolean;
}) {
  return (
    <div className="space-y-4">
      {messages.map((m) =>
        m.role === "user" ? (
          <div key={m.id} className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-[4px] bg-accent-tint px-[18px] py-[13px] text-[14.5px] font-semibold whitespace-pre-wrap sm:max-w-[420px]">
              {m.content}
            </div>
          </div>
        ) : (
          <AssistantMessage
            key={m.id}
            m={m}
            scope={scopes[m.id]}
            onExport={actions.exportSlides}
            exporting={actions.exportingId === m.id}
            onSaveToVault={actions.saveToVault}
            saving={actions.savingId === m.id}
            onPdf={actions.exportPdf}
            pdfBusy={actions.pdfId === m.id}
            coverage={coverages[m.id]}
            onAddDocument={actions.addDocument}
            onAssertFact={actions.assertFact}
            readOnly={readOnly}
          />
        )
      )}
      {streamText !== null && (
        <article className="max-w-full rounded-2xl border border-edge bg-card px-5 py-4 shadow-card sm:px-6 sm:py-5">
          {streamText ? (
            <>
              <AnswerMarkdown content={stripCiteMarkers(streamText)} />
              <PulsingDots className="mt-1.5" />
            </>
          ) : (
            <PulsingDots className="py-1" />
          )}
        </article>
      )}
    </div>
  );
}
