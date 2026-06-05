import { useMemo, useState, useRef, useEffect } from 'react';
import type { ReactElement } from 'react';
import { ask, buildIndex, SUGGESTED } from '../lib/ask.ts';
import { MdInline } from '../lib/md.tsx';
import type { AppData } from '../types.ts';

// an entity an answer can fly to / highlight (mirrors ask.ts EntityRef)
interface ChatEntity {
  portid: string;
  name: string;
}

// a question the user typed
interface UserMsg {
  role: 'user';
  text: string;
}

// a grounded answer the engine returned (spread of ask.ts Answer + role)
interface BotMsg {
  role: 'bot';
  text: string;
  cites: string[];
  entity: ChatEntity | null;
  kind: string;
  suggestions?: string[];
}

type ChatMsg = UserMsg | BotMsg;

interface BotTextProps {
  text: string;
}

interface ChatProps {
  data: AppData | null;
  onPickEntity?: (portid: string) => void;
}

// Ask Freight Radar — a grounded chat that runs entirely in the browser over the
// loaded sidecars. No backend, no key. Every answer cites the source file(s) it
// drew from, and the engine only states numbers it can trace (see lib/ask.js).
function BotText({ text }: BotTextProps): ReactElement {
  // answers may carry newline-separated bullets; render each line inline
  return (
    <>
      {String(text)
        .split('\n')
        .map((ln, i) => (
          <div key={i} className="fr-chat-line">
            <MdInline text={ln} />
          </div>
        ))}
    </>
  );
}

export default function Chat({ data, onPickEntity }: ChatProps) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const index = useMemo(() => (data ? buildIndex(data) : null), [data]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [msgs, open]);

  const send = (q?: string) => {
    const question = (q ?? input).trim();
    if (!question || !data) return;
    const a = ask(question, data, index);
    setMsgs((m) => [...m, { role: 'user', text: question }, { role: 'bot', ...a }]);
    setInput('');
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  if (!data) return null;

  return (
    <>
      <button
        className={`fr-chat-fab ${open ? 'is-open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        title="Ask Freight Radar"
      >
        {open ? '×' : '✦ Ask'}
      </button>

      {open && (
        <div className="fr-chat">
          <div className="fr-chat-head">
            <div>
              <span className="fr-chat-title">Ask Freight Radar</span>
              <span className="fr-chat-sub">grounded in this data · every number is cited</span>
            </div>
            <button className="fr-chat-x" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>

          <div className="fr-chat-body" ref={scrollRef}>
            {msgs.length === 0 && (
              <div className="fr-chat-intro">
                <p>
                  Ask about a chokepoint, the biggest risk, what's improving, your exposure, or the
                  market. I answer only with numbers I can trace to a source file.
                </p>
              </div>
            )}
            {msgs.map((m, i) =>
              m.role === 'user' ? (
                <div key={i} className="fr-chat-msg user">
                  {m.text}
                </div>
              ) : (
                <div key={i} className="fr-chat-msg bot">
                  <BotText text={m.text} />
                  {m.entity && onPickEntity && (
                    <button
                      className="fr-chat-jump"
                      onClick={() => m.entity && onPickEntity(m.entity.portid)}
                    >
                      ↳ show {m.entity.name} on the globe
                    </button>
                  )}
                  {m.cites?.length > 0 && (
                    <div className="fr-chat-cites">
                      {m.cites.map((c) => (
                        <span key={c} className="fr-chat-cite">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                  {(m.suggestions?.length ?? 0) > 0 && (
                    <div className="fr-chat-sugg">
                      {m.suggestions?.map((q) => (
                        <button key={q} className="fr-chat-chip sm" onClick={() => send(q)}>
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            )}
          </div>

          {msgs.length === 0 && (
            <div className="fr-chat-starter">
              {SUGGESTED.map((q) => (
                <button key={q} className="fr-chat-chip" onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}

          <div className="fr-chat-input">
            <input
              value={input}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask about ocean freight…"
            />
            <button onClick={() => send()} disabled={!input.trim()}>
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
}
