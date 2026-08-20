import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { jsPDF } from 'jspdf';
import './Stage3.css';

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke on the next tick so the download has started.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Stage3({ finalResponse }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  if (!finalResponse) {
    return null;
  }

  const reportText = finalResponse.response || '';

  const flashError = (msg) => {
    setError(msg);
    setTimeout(() => setError(''), 3000);
  };

  const handleCopy = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(reportText);
      } else {
        // Fallback for non-secure contexts where navigator.clipboard is unavailable.
        const ta = document.createElement('textarea');
        ta.value = reportText;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (!ok) throw new Error('execCommand copy failed');
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      flashError('Copie impossible dans ce navigateur.');
    }
  };

  const handleExportText = () => {
    try {
      const blob = new Blob([reportText], { type: 'text/plain;charset=utf-8' });
      downloadBlob(blob, `council-report-${timestamp()}.txt`);
    } catch {
      flashError('Échec de l’export texte.');
    }
  };

  const handleExportPdf = () => {
    try {
      const doc = new jsPDF({ unit: 'pt', format: 'a4' });
      const marginX = 40;
      const marginY = 48;
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const usableWidth = pageWidth - marginX * 2;
      const lineHeight = 16;

      // Header
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.text('LLM Council — Rapport final', marginX, marginY);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(120);
      const chairman = finalResponse.model?.split('/')[1] || finalResponse.model || '';
      doc.text(`Chairman: ${chairman}`, marginX, marginY + 16);
      doc.setTextColor(0);
      doc.setFontSize(11);

      let y = marginY + 44;
      const lines = doc.splitTextToSize(reportText, usableWidth);
      for (const line of lines) {
        if (y + lineHeight > pageHeight - marginY) {
          doc.addPage();
          y = marginY;
        }
        doc.text(line, marginX, y);
        y += lineHeight;
      }
      doc.save(`council-report-${timestamp()}.pdf`);
    } catch {
      flashError('Échec de la génération du PDF.');
    }
  };

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="final-response-header">
          <div className="chairman-label">
            Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
          </div>
          <div className="report-actions" data-testid="stage3-actions">
            <button
              type="button"
              className="report-action-btn"
              onClick={handleCopy}
              data-testid="stage3-copy-btn"
              title="Copier le rapport"
            >
              {copied ? 'Copié ✓' : 'Copier'}
            </button>
            <button
              type="button"
              className="report-action-btn"
              onClick={handleExportText}
              data-testid="stage3-export-txt-btn"
              title="Exporter en texte"
            >
              Exporter .txt
            </button>
            <button
              type="button"
              className="report-action-btn"
              onClick={handleExportPdf}
              data-testid="stage3-export-pdf-btn"
              title="Exporter en PDF"
            >
              Exporter .pdf
            </button>
          </div>
        </div>
        {error && (
          <div className="report-action-error" data-testid="stage3-action-error">
            {error}
          </div>
        )}
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
