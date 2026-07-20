import { useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage3.css';

/** Build a timestamped filename base like council-answer-2026-07-20-1432 */
function makeFilenameBase() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `council-answer-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}

/** Trigger a browser download of a Blob */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function Stage3({ finalResponse }) {
  const [copyStatus, setCopyStatus] = useState('');
  const renderedRef = useRef(null);

  if (!finalResponse) {
    return null;
  }

  const chairmanName = finalResponse.model.split('/')[1] || finalResponse.model;

  // --- Copy raw markdown text to clipboard ---
  const handleCopy = async () => {
    const text = finalResponse.response;
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus('ok');
    } catch {
      // Fallback for non-secure contexts (http://) or older browsers
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        setCopyStatus('ok');
      } catch {
        setCopyStatus('err');
      }
    }
    setTimeout(() => setCopyStatus(''), 2000);
  };

  // --- Export raw text as .txt ---
  const handleExportTxt = () => {
    const header = `Final Council Answer — Chairman: ${chairmanName}\nDate: ${new Date().toLocaleString()}\n${'='.repeat(60)}\n\n`;
    const blob = new Blob([header + finalResponse.response], {
      type: 'text/plain;charset=utf-8',
    });
    downloadBlob(blob, `${makeFilenameBase()}.txt`);
  };

  // --- Export as PDF via a styled print window (preserves tables) ---
  const handleExportPdf = () => {
    const renderedHtml = renderedRef.current ? renderedRef.current.innerHTML : '';
    const printWindow = window.open('', '_blank', 'width=900,height=700');
    if (!printWindow) {
      alert("Popup bloquée — autorisez les popups pour exporter en PDF.");
      return;
    }
    printWindow.document.write(`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>${makeFilenameBase()}</title>
<style>
  body {
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    color: #222;
    line-height: 1.7;
    font-size: 13px;
    max-width: 800px;
    margin: 0 auto;
    padding: 32px;
  }
  .pdf-header {
    border-bottom: 2px solid #2d8a2d;
    padding-bottom: 12px;
    margin-bottom: 24px;
  }
  .pdf-header h1 { font-size: 18px; margin: 0 0 4px 0; color: #2d8a2d; }
  .pdf-header .meta { font-size: 11px; color: #666; font-family: monospace; }
  h1, h2, h3, h4 { margin: 16px 0 8px 0; page-break-after: avoid; }
  p { margin: 0 0 10px 0; }
  ul, ol { margin: 0 0 10px 0; padding-left: 22px; }
  li { margin: 3px 0; }
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 0 0 12px 0;
    font-size: 11px;
    page-break-inside: avoid;
  }
  th, td {
    border: 1px solid #bbb;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }
  thead { background: #f0f0f0; }
  th { font-weight: 600; }
  tbody tr:nth-child(even) { background: #fafafa; }
  pre {
    background: #f5f5f5;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 11px;
    page-break-inside: avoid;
  }
  code { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
  pre code { background: none; padding: 0; }
  blockquote { margin: 0 0 10px 0; padding-left: 14px; border-left: 3px solid #ccc; color: #555; }
  hr { border: none; border-top: 1px solid #ccc; margin: 14px 0; }
  @media print {
    body { padding: 0; }
  }
</style>
</head>
<body>
  <div class="pdf-header">
    <h1>Final Council Answer</h1>
    <div class="meta">Chairman: ${chairmanName} — ${new Date().toLocaleString()}</div>
  </div>
  ${renderedHtml}
</body>
</html>`);
    printWindow.document.close();
    // Wait for content to render, then open the print dialog (Save as PDF)
    printWindow.onload = () => {
      printWindow.focus();
      printWindow.print();
    };
    // Fallback if onload already fired (document.write is synchronous)
    setTimeout(() => {
      try {
        printWindow.focus();
        printWindow.print();
      } catch {
        /* window may already be closed */
      }
    }, 400);
  };

  return (
    <div className="stage stage3">
      <div className="stage3-header">
        <h3 className="stage-title">Stage 3: Final Council Answer</h3>
        <div className="export-actions">
          <button
            className={`export-btn ${copyStatus === 'ok' ? 'copied' : ''}`}
            onClick={handleCopy}
            title="Copier le texte dans le presse-papiers"
          >
            {copyStatus === 'ok' ? '✓ Copié' : copyStatus === 'err' ? 'Erreur' : 'Copier'}
          </button>
          <button
            className="export-btn"
            onClick={handleExportTxt}
            title="Télécharger en fichier texte (.txt)"
          >
            TXT
          </button>
          <button
            className="export-btn"
            onClick={handleExportPdf}
            title="Exporter en PDF (via la boîte de dialogue d'impression)"
          >
            PDF
          </button>
        </div>
      </div>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {chairmanName}
        </div>
        <div className="final-text markdown-content" ref={renderedRef}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
