import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

// Normalize LaTeX delimiters the reports use (\[ \], \( \)) into the $$ / $ that
// remark-math understands, and turn long decorative rules into a real <hr>.
// KaTeX (\boxed{}, \approx, \rightarrow, matrices, etc.) then renders natively.
export function preprocessMath(text) {
  if (!text) return '';
  let t = text;
  t = t.replace(/\\\[([\s\S]+?)\\\]/g, (_, e) => `\n\n$$\n${e.trim()}\n$$\n\n`);
  t = t.replace(/\\\(([\s\S]+?)\\\)/g, (_, e) => `$${e.trim()}$`);
  t = t.replace(/^[ \t]*[═=*─—_]{3,}[ \t]*$/gm, '\n\n---\n\n');
  return t;
}

export default function MarkdownView({ children, className }) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {preprocessMath(typeof children === 'string' ? children : '')}
      </ReactMarkdown>
    </div>
  );
}
