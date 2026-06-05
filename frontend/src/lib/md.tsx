import type { ReactNode } from 'react';

// Minimal markdown: **bold**, _italic_, blank-line paragraphs. No deps.
function inline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*([^*]+)\*\*|_([^_]+)_)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[2] != null) nodes.push(<strong key={`${keyPrefix}-b${i}`}>{m[2]}</strong>);
    else if (m[3] != null) nodes.push(<em key={`${keyPrefix}-i${i}`}>{m[3]}</em>);
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

interface MdInlineProps {
  text: ReactNode;
}

// Inline-only render (no paragraph wrapping) — for one-line bullets/labels.
export function MdInline({ text }: MdInlineProps) {
  return <>{inline(String(text || ''), 'il')}</>;
}

interface MarkdownProps {
  text: ReactNode;
}

export function Markdown({ text }: MarkdownProps) {
  const paras = String(text || '').split(/\n\s*\n/);
  return (
    <>
      {paras.map((p, i) => (
        <p key={i} className="fr-brief-p">
          {inline(p.replace(/\n/g, ' '), `p${i}`)}
        </p>
      ))}
    </>
  );
}
