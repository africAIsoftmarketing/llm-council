import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import MarkdownView from './MarkdownView';
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

// ---------------------------------------------------------------------------
// PDF export helpers
// ---------------------------------------------------------------------------
// Rendering the whole report into ONE html2canvas bitmap breaks on long
// reports: browsers cap canvas size (Chrome/Firefox: 32 767 px per side,
// Safari/iOS: ~16.7 M px total area), so the capture comes back blank and
// jsPDF throws. Re-adding that full bitmap on every page also produced PDFs of
// hundreds of MB. We therefore (1) compute page breaks on block boundaries,
// (2) capture the surface in bounded chunks, and (3) embed only each page's
// own slice.
const PDF_SCALE = 2;
const PDF_MARGIN_PT = 28;               // top/bottom margin on every A4 page
const MAX_CANVAS_SIDE = 16000;          // px — well under every browser cap
const MAX_CANVAS_AREA = 16000000;       // px² — under Safari's ~16.7 M limit

// Blocks we avoid splitting across two pages (lines of text, rows, formulas…).
const PDF_BLOCK_SELECTOR = [
  'p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'blockquote', 'tr',
  'hr', 'img', '.katex-display', '.export-chairman', '.ranking-note',
].join(',');

// Returns [[top, bottom], …] page slices (CSS px, relative to `node`).
function computePdfPages(node, pageHeightPx) {
  const rootTop = node.getBoundingClientRect().top;
  const total = Math.ceil(node.scrollHeight);
  const blocks = [];
  node.querySelectorAll(PDF_BLOCK_SELECTOR).forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.height <= 0) return;
    const top = r.top - rootTop;
    let bottom = r.bottom - rootTop;
    // Keep headings with the beginning of the content that follows them.
    if (/^H[1-6]$/.test(el.tagName) && el.nextElementSibling) {
      const n = el.nextElementSibling.getBoundingClientRect();
      if (n.height > 0) bottom = Math.max(bottom, Math.min(n.bottom, n.top + 60) - rootTop);
    }
    blocks.push([top, bottom]);
  });

  const pages = [];
  let start = 0;
  while (total - start > pageHeightPx) {
    const hardEnd = start + pageHeightPx;
    let cut = hardEnd;
    let moved = true;
    while (moved) {
      moved = false;
      for (const [top, bottom] of blocks) {
        if (top < cut && bottom > cut && top > start) {
          cut = top;
          moved = true;
        }
      }
    }
    // A block taller than most of a page (huge code block/table): cut through it
    // rather than producing an almost empty page.
    if (cut < start + pageHeightPx * 0.3) cut = hardEnd;
    cut = Math.floor(cut);
    pages.push([start, cut]);
    start = cut;
  }
  pages.push([start, total]);
  return pages;
}

// Group consecutive pages into capture chunks that respect canvas limits.
function groupPagesIntoChunks(pages, widthPx, scale) {
  const maxByArea = MAX_CANVAS_AREA / (widthPx * scale * scale);
  const maxChunkPx = Math.floor(Math.min(MAX_CANVAS_SIDE / scale, maxByArea));
  const chunks = [];
  let current = null;
  for (const page of pages) {
    if (current && page[1] - current.top <= maxChunkPx) {
      current.pages.push(page);
      current.bottom = page[1];
    } else {
      current = { top: page[0], bottom: page[1], pages: [page] };
      chunks.push(current);
    }
  }
  return chunks;
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
  const { t } = useTranslation();

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
    parts.push(t('stage3.reportTitle'));
    parts.push(`${t('stage3.chairman', { model: chairman })}`);
    parts.push('');
    parts.push(`=== ${t('stage3.finalSynthesis')} ===`);
    parts.push(markdownToPlain(finalResponse.response));
    if (members.length) {
      parts.push('');
      parts.push(`=== ${t('stage3.councilMembers')} ===`);
      members.forEach((m, i) => {
        parts.push('');
        parts.push(`— ${shortModel(m.model)} (${i + 1}/${members.length}) —`);
        parts.push(markdownToPlain(m.response));
      });
    }
    if (ranking.length) {
      parts.push('');
      parts.push(`=== ${t('stage3.aggregateRanking')} ===`);
      ranking.forEach((agg, i) => {
        parts.push(
          `#${i + 1}  ${shortModel(agg.model)}  — ${Number(agg.average_rank).toFixed(2)} (${agg.rankings_count})`
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
      flashError(t('stage3.copyError'));
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
      flashError(t('stage3.txtError'));
    }
  };

  // WYSIWYG PDF: capture the offscreen, fully-expanded report surface as images
  // (browser fonts render all Unicode correctly) and paginate across A4 pages.
  // Captured in bounded chunks and sliced per page (see computePdfPages).
  const handleExportPdf = async () => {
    if (pdfBusy) return;
    setPdfBusy(true);
    try {
      const node = exportRef.current;
      if (!node) throw new Error('PDF export surface not mounted');
      // Make sure web fonts (incl. KaTeX) are loaded before capturing.
      if (document.fonts && document.fonts.ready) {
        try { await document.fonts.ready; } catch { /* non-blocking */ }
      }

      const pdf = new jsPDF({ unit: 'pt', format: 'a4', orientation: 'portrait' });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const widthPx = Math.ceil(node.scrollWidth);
      const ptPerPx = pageWidth / widthPx;
      const contentHeightPx = (pageHeight - 2 * PDF_MARGIN_PT) / ptPerPx;

      const pages = computePdfPages(node, contentHeightPx);
      const chunks = groupPagesIntoChunks(pages, widthPx, PDF_SCALE);

      let pageIndex = 0;
      for (const chunk of chunks) {
        const chunkCanvas = await html2canvas(node, {
          scale: PDF_SCALE,
          backgroundColor: '#ffffff',
          useCORS: true,
          windowWidth: node.scrollWidth,
          width: widthPx,
          y: chunk.top,
          height: Math.ceil(chunk.bottom - chunk.top),
        });
        const pxScale = chunkCanvas.width / widthPx; // effective device scale

        for (const [top, bottom] of chunk.pages) {
          const srcY = Math.round((top - chunk.top) * pxScale);
          const srcH = Math.min(
            Math.round((bottom - top) * pxScale),
            chunkCanvas.height - srcY,
          );
          if (srcH <= 0) continue;
          const pageCanvas = document.createElement('canvas');
          pageCanvas.width = chunkCanvas.width;
          pageCanvas.height = srcH;
          const ctx = pageCanvas.getContext('2d');
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
          ctx.drawImage(chunkCanvas, 0, srcY, chunkCanvas.width, srcH,
            0, 0, pageCanvas.width, srcH);

          if (pageIndex > 0) pdf.addPage();
          pdf.addImage(pageCanvas.toDataURL('image/png'), 'PNG',
            0, PDF_MARGIN_PT, pageWidth, (srcH / pxScale) * ptPerPx,
            undefined, 'FAST');
          pageIndex += 1;
          pageCanvas.width = 0; pageCanvas.height = 0; // free memory early
        }
        chunkCanvas.width = 0; chunkCanvas.height = 0;
      }

      if (pageIndex === 0) throw new Error('PDF export produced no page');
      pdf.save(`council-report-${timestamp()}.pdf`);
    } catch (err) {
      console.error('[Stage3] PDF export failed:', err);
      flashError(t('stage3.pdfError'));
    } finally {
      setPdfBusy(false);
    }
  };

  const md = (text) => <MarkdownView>{text}</MarkdownView>;

  return (
    <div className="stage stage3">
      <h3 className="stage-title">{t('stage3.title')}</h3>
      <div className="final-response">
        <div className="final-response-header">
          <div className="chairman-label">{t('stage3.chairman', { model: chairman })}</div>
          <div className="report-actions" data-testid="stage3-actions">
            <button type="button" className="report-action-btn" onClick={handleCopy}
              data-testid="stage3-copy-btn" title={t('stage3.copyTitle')}>
              {copied ? t('stage3.copied') : t('stage3.copy')}
            </button>
            <button type="button" className="report-action-btn" onClick={handleExportText}
              data-testid="stage3-export-txt-btn" title={t('stage3.exportTxtTitle')}>
              {t('stage3.exportTxt')}
            </button>
            <button type="button" className="report-action-btn" onClick={handleExportPdf}
              disabled={pdfBusy} data-testid="stage3-export-pdf-btn" title={t('stage3.exportPdfTitle')}>
              {pdfBusy ? t('stage3.pdfBusy') : t('stage3.exportPdf')}
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
              {t('stage3.members', { count: members.length })}
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
              {t('stage3.aggRanking', { count: ranking.length })}
            </button>
            {rankingOpen && (
              <div className="report-ranking" data-testid="stage3-ranking">
                <table className="ranking-table">
                  <thead>
                    <tr><th>#</th><th>{t('stage3.colModel')}</th><th>{t('stage3.colAvg')}</th><th>{t('stage3.colVotes')}</th></tr>
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
                <p className="ranking-note">{t('stage3.rankingNote')}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Offscreen, fully-expanded surface used to render the WYSIWYG PDF. */}
      <div className="stage3-export-surface" ref={exportRef} aria-hidden="true">
        <div className="export-doc">
          <h1 className="export-title">{t('stage3.reportTitle')}</h1>
          <div className="export-chairman">{t('stage3.chairman', { model: chairman })}</div>

          <h2 className="export-h">{t('stage3.finalSynthesis')}</h2>
          <div className="markdown-content">{md(finalResponse.response)}</div>

          {members.length > 0 && (
            <>
              <h2 className="export-h">{t('stage3.councilMembers')}</h2>
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
              <h2 className="export-h">{t('stage3.aggregateRanking')}</h2>
              <table className="ranking-table">
                <thead>
                  <tr><th>#</th><th>{t('stage3.colModel')}</th><th>{t('stage3.colAvg')}</th><th>{t('stage3.colVotes')}</th></tr>
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
              <p className="ranking-note">{t('stage3.rankingNote')}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
