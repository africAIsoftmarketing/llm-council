import { useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { jsPDF } from 'jspdf';
import html2canvas from 'html2canvas';
import './Stage3.css';

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

const shortModel = (m) => (m ? (m.split('/')[1] || m) : '');

// Convert common inline-LaTeX artifacts to real Unicode and drop $...$ delimiters.
function normalizeLatex(text) {
  if (!text) return '';
  let t = text;
  const map = [
    [/\\checkmark/g, '✓'], [/\\times/g, '×'], [/\\approx/g, '≈'],
    [/\\rightarrow/g, '→'], [/\\Rightarrow/g, '⇒'], [/\\leftarrow/g, '←'],
    [/\\to\b/g, '→'], [/\\leq/g, '≤'], [/\\geq/g, '≥'], [/\\neq/g, '≠'],
    [/\\ne\b/g, '≠'], [/\\pm/g, '±'], [/\\cdot/g, '·'], [/\\infty/g, '∞'],
    [/\\bullet/g, '•'], [/\\star/g, '★'], [/\\%/g, '%'],
  ];
  for (const [re, rep] of map) t = t.replace(re, rep);
  // Strip inline math delimiters: $ ... $  and \( ... \)
  t = t.replace(/\$([^$\n]*)\$/g, '$1');
  t = t.replace(/\\\(([^)]*)\\\)/g, '$1');
  return t;
}

// Replace long decorative rules (═══, ***, ───, ===) with a real markdown <hr>.
function normalizeDecorative(text) {
  return text.replace(/^[ \t]*[═=*─—_]{3,}[ \t]*$/gm, '\n---\n');
}

// Content prepared for on-screen ReactMarkdown and the WYSIWYG PDF surface.
function sanitizeForDisplay(text) {
  return normalizeDecorative(normalizeLatex(text || ''));
}

// Strip markdown syntax to a clean, readable plain-text (copy / .txt export).
function markdownToPlain(text) {
  let t = sanitizeForDisplay(text);
  t = t.replace(/```[a-zA-Z]*\n?/g, '').replace(/```/g, ''); // code fences
  t = t.replace(/`([^`]+)`/g, '$1');                          // inline code
  t = t.replace(/^\s{0,3}(#{1,6})\s*(.+?)\s*#*\s*$/gm, (_, h, txt) => txt.toUpperCase());
  t = t.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/__([^_]+)__/g, '$1'); // bold
  t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1$2');            // italic *
  t = t.replace(/^\s*[-*]\s+/gm, '• ');                       // bullets
  t = t.replace(/^\s*---\s*$/gm, '────────────────────');     // hr
  t = t.replace(/\n{3,}/g, '\n\n');                           // collapse blanks
  return t.trim();
}

export default function Stage3({
  finalResponse,
  stage1Responses,
  aggregateRankings,
  labelToModel,
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [pdfBusy, setPdfBusy] = useState(false);
  const [membersOpen, setMembersOpen] = useState(false);
  const [rankingOpen, setRankingOpen] = useState(false);
  const exportRef = useRef(null);

  if (!finalResponse) return null;

  const chairman = shortModel(finalResponse.model);
  const members = Array.isArray(stage1Responses) ? stage1Responses : [];
  const ranking = Array.isArray(aggregateRankings) ? aggregateRankings : [];

  const flashError = (msg) => {
    setError(msg);
    setTimeout(() => setError(''), 3000);
  };

  // Build the full plain-text report (Chairman + members + aggregate ranking).
  const buildReportText = () => {
    const parts = [];
    parts.push('LLM COUNCIL — RAPPORT FINAL');
    parts.push(`Chairman : ${chairman}`);
    parts.push('');
    parts.push('=== SYNTHÈSE FINALE (CHAIRMAN) ===');
    parts.push(markdownToPlain(finalResponse.response));
    if (members.length) {
      parts.push('');
      parts.push('=== MEMBRES DU COUNCIL ===');
      members.forEach((m, i) => {
        parts.push('');
        parts.push(`— ${shortModel(m.model)} (${i + 1}/${members.length}) —`);
        parts.push(markdownToPlain(m.response));
      });
    }
    if (ranking.length) {
      parts.push('');
      parts.push('=== CLASSEMENT AGRÉGÉ (score plus bas = meilleur) ===');
      ranking.forEach((agg, i) => {
        parts.push(
          `#${i + 1}  ${shortModel(agg.model)}  — moyenne ${Number(agg.average_rank).toFixed(2)} (${agg.rankings_count} votes)`
        );
      });
    }
    return parts.join('\n');
  };

  const handleCopy = async () => {
    const text = buildReportText();
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
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
      const blob = new Blob([buildReportText()], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `council-report-${timestamp()}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      flashError('Échec de l’export texte.');
    }
  };

  // WYSIWYG PDF: capture the offscreen, fully-expanded report surface as an image
  // (browser fonts render all Unicode correctly) and paginate across A4 pages.
  const handleExportPdf = async () => {
    if (pdfBusy) return;
    setPdfBusy(true);
    try {
      const node = exportRef.current;
      const canvas = await html2canvas(node, {
        scale: 2,
        backgroundColor: '#ffffff',
        useCORS: true,
        windowWidth: node.scrollWidth,
      });
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF({ unit: 'pt', format: 'a4', orientation: 'portrait' });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      let heightLeft = imgHeight;
      let position = 0;
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
      while (heightLeft > 0) {
        position -= pageHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }
      pdf.save(`council-report-${timestamp()}.pdf`);
    } catch {
      flashError('Échec de la génération du PDF.');
    } finally {
      setPdfBusy(false);
    }
  };

  const md = (text) => (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{sanitizeForDisplay(text)}</ReactMarkdown>
  );

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="final-response-header">
          <div className="chairman-label">Chairman: {chairman}</div>
          <div className="report-actions" data-testid="stage3-actions">
            <button type="button" className="report-action-btn" onClick={handleCopy}
              data-testid="stage3-copy-btn" title="Copier le rapport">
              {copied ? 'Copié ✓' : 'Copier'}
            </button>
            <button type="button" className="report-action-btn" onClick={handleExportText}
              data-testid="stage3-export-txt-btn" title="Exporter en texte">
              Exporter .txt
            </button>
            <button type="button" className="report-action-btn" onClick={handleExportPdf}
              disabled={pdfBusy} data-testid="stage3-export-pdf-btn" title="Exporter en PDF">
              {pdfBusy ? 'PDF…' : 'Exporter .pdf'}
            </button>
          </div>
        </div>

        {error && (
          <div className="report-action-error" data-testid="stage3-action-error">{error}</div>
        )}

        {/* Chairman synthesis — always visible */}
        <div className="final-text markdown-content" data-testid="stage3-final-text">
          {md(finalResponse.response)}
        </div>

        {/* Members of the council — collapsible */}
        {members.length > 0 && (
          <div className="report-section">
            <button
              type="button"
              className={`report-accordion-toggle ${membersOpen ? 'open' : ''}`}
              onClick={() => setMembersOpen((v) => !v)}
              data-testid="stage3-members-toggle"
              aria-expanded={membersOpen}
            >
              <span className="chevron">▶</span>
              Membres du council ({members.length})
            </button>
            {membersOpen && (
              <div className="report-members" data-testid="stage3-members">
                {members.map((m, i) => (
                  <details key={i} className="member-item" open={i === 0}>
                    <summary className="member-summary">{shortModel(m.model)}</summary>
                    <div className="member-response markdown-content">{md(m.response)}</div>
                  </details>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Aggregate ranking — collapsible */}
        {ranking.length > 0 && (
          <div className="report-section">
            <button
              type="button"
              className={`report-accordion-toggle ${rankingOpen ? 'open' : ''}`}
              onClick={() => setRankingOpen((v) => !v)}
              data-testid="stage3-ranking-toggle"
              aria-expanded={rankingOpen}
            >
              <span className="chevron">▶</span>
              Classement agrégé ({ranking.length})
            </button>
            {rankingOpen && (
              <div className="report-ranking" data-testid="stage3-ranking">
                <table className="ranking-table">
                  <thead>
                    <tr><th>#</th><th>Modèle</th><th>Score moyen</th><th>Votes</th></tr>
                  </thead>
                  <tbody>
                    {ranking.map((agg, i) => (
                      <tr key={i}>
                        <td className="rank-pos">{i + 1}</td>
                        <td>{shortModel(agg.model)}</td>
                        <td>{Number(agg.average_rank).toFixed(2)}</td>
                        <td>{agg.rankings_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="ranking-note">Score plus bas = mieux classé par les pairs.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Offscreen, fully-expanded surface used to render the WYSIWYG PDF. */}
      <div className="stage3-export-surface" ref={exportRef} aria-hidden="true">
        <div className="export-doc">
          <h1 className="export-title">LLM Council — Rapport final</h1>
          <div className="export-chairman">Chairman : {chairman}</div>

          <h2 className="export-h">Synthèse finale (Chairman)</h2>
          <div className="markdown-content">{md(finalResponse.response)}</div>

          {members.length > 0 && (
            <>
              <h2 className="export-h">Membres du council</h2>
              {members.map((m, i) => (
                <div key={i} className="export-member">
                  <h3 className="export-h3">{shortModel(m.model)}</h3>
                  <div className="markdown-content">{md(m.response)}</div>
                </div>
              ))}
            </>
          )}

          {ranking.length > 0 && (
            <>
              <h2 className="export-h">Classement agrégé</h2>
              <table className="ranking-table">
                <thead>
                  <tr><th>#</th><th>Modèle</th><th>Score moyen</th><th>Votes</th></tr>
                </thead>
                <tbody>
                  {ranking.map((agg, i) => (
                    <tr key={i}>
                      <td>{i + 1}</td>
                      <td>{shortModel(agg.model)}</td>
                      <td>{Number(agg.average_rank).toFixed(2)}</td>
                      <td>{agg.rankings_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="ranking-note">Score plus bas = mieux classé par les pairs.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
