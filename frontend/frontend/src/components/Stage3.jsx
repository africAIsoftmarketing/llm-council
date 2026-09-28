import { useState, useRef, useEffect } from 'react';
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
// If a capture fails or comes back blank (GPU/memory limits), retry that chunk
// at a lower resolution instead of failing the whole export.
const PDF_RETRY_SCALES = [PDF_SCALE, 1.5, 1];
const PDF_MARGIN_PT = 28;               // top/bottom margin on every A4 page
const PDF_JPEG_QUALITY = 0.92;          // sharp text on white, fast to embed
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

// html2canvas clones the WHOLE page (the full app + the full report) and lays
// it out again on every call. On a real council conversation (100k+ DOM nodes,
// 150+ pages) that is 6-20 s per chunk, i.e. many minutes and enough memory
// pressure for Edge/Chrome to fail. For each chunk we therefore clone ONLY
// the elements that intersect it:
//   - everything outside the report surface is skipped (ignoreElements),
//   - report blocks entirely above/below the chunk are skipped too,
//   - in the private clone, an invisible spacer puts the first kept block
//     back at its exact original offset, so page breaks stay pixel-exact.
// Tables, formulas, code blocks… are never split (their layout depends on all
// their content); only plain flow containers are pruned.
const PDF_SKIP_MARGIN_PX = 64; // safety band for glyphs overflowing their box
const PDF_SPLITTABLE = new Set(['DIV', 'SECTION', 'ARTICLE', 'UL', 'OL', 'LI', 'BLOCKQUOTE']);

function planChunk(node, top, bottom) {
  const rootTop = node.getBoundingClientRect().top;
  const lo = top - PDF_SKIP_MARGIN_PX;
  const hi = bottom + PDF_SKIP_MARGIN_PX;
  const ignore = new Set();
  const olSkips = [];      // [pathToOl, removedLiCount]
  let anchor = null;
  let anchorPath = null;   // child indexes from `node`, counting kept elements only
  let anchorTop = 0;
  const visit = (el, path) => {
    let removedLi = 0;
    let keptIndex = -1;
    for (const child of el.children) {
      const r = child.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) { keptIndex += 1; continue; } // no box: keep
      const cTop = r.top - rootTop;
      const cBottom = r.bottom - rootTop;
      const splittable = PDF_SPLITTABLE.has(child.tagName) && child.children.length > 0;
      if (cBottom < lo && !anchor) {            // entirely above the chunk
        ignore.add(child);
        if (child.tagName === 'LI') removedLi += 1;
        continue;
      }
      if (cTop > hi) {                          // entirely below the chunk
        ignore.add(child);
        continue;
      }
      keptIndex += 1;
      const childPath = [...path, keptIndex];
      if (!anchor) {                            // first block reaching the chunk
        if (cTop < lo && splittable) {
          visit(child, childPath);              // starts above: drop its head
        } else {
          anchor = child; anchorPath = childPath; anchorTop = cTop;
          if (cBottom > hi && splittable) visit(child, childPath); // drop its tail
        }
      } else if (cBottom > hi && splittable) {  // runs past the chunk: prune tail
        visit(child, childPath);
      }
    }
    if (removedLi > 0 && el.tagName === 'OL') olSkips.push([path, removedLi]);
  };
  visit(node, []);
  return { ignore, olSkips, anchorPath, anchorTop };
}

// Follow a kept-children index path inside the cloned report.
// html2canvas injects <html2canvaspseudoelement> nodes for ::before/::after;
// they are not part of the original structure, so skip them when walking.
function elementAtPath(root, path) {
  let el = root;
  for (const i of path) {
    if (!el) return null;
    const kids = [...el.children].filter((c) => c.tagName !== 'HTML2CANVASPSEUDOELEMENT');
    el = kids[i];
  }
  return el || null;
}

function makeIgnore(node, plan) {
  const body = node.ownerDocument.body;
  return (el) => {
    if (plan.ignore.has(el)) return true;
    if (el === node || node.contains(el)) return false;
    // Rest of the app: not needed for the capture, skip unless it holds the report.
    return body.contains(el) && el !== body && !el.contains(node);
  };
}

function restoreChunkLayout(clonedNode, plan) {
  for (const [path, skipped] of plan.olSkips) {
    const ol = elementAtPath(clonedNode, path);
    if (ol && ol.tagName === 'OL') ol.start = (ol.start || 1) + skipped; // keep numbering
  }
  if (!plan.anchorPath) return;
  const anchor = elementAtPath(clonedNode, plan.anchorPath);
  if (!anchor || !anchor.parentNode) return;
  const anchorTop = plan.anchorTop;
  const spacer = clonedNode.ownerDocument.createElement('div');
  spacer.style.cssText = 'display:block;height:0;margin:0;padding:0;border:0;';
  anchor.parentNode.insertBefore(spacer, anchor);
  let offset = 0;
  for (let i = 0; i < 6; i += 1) {
    const cur = anchor.getBoundingClientRect().top - clonedNode.getBoundingClientRect().top;
    const diff = anchorTop - cur;
    if (Math.abs(diff) < 0.25) break;
    offset += diff;
    spacer.style.height = `${Math.max(0, offset)}px`;
    spacer.style.marginTop = `${Math.min(0, offset)}px`;
  }
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

// Browsers only honour a script-initiated download while the user's click is
// still "active" (a few seconds). Small reports finish within that window;
// long ones do not, and Chrome/Edge/Safari then silently block the download
// (Chrome shows a small "download blocked" icon in the address bar). We
// therefore download immediately only when generation was quick and the
// browser does not report an expired activation; otherwise we hand the user a
// real download button, whose click is always honoured.
const PDF_AUTO_DOWNLOAD_MAX_MS = 3000;
function canAutoDownload(startedAt) {
  if (Date.now() - startedAt > PDF_AUTO_DOWNLOAD_MAX_MS) return false;
  const ua = typeof navigator !== 'undefined' ? navigator.userActivation : undefined;
  return !(ua && ua.isActive === false);
}

function triggerDownload(url, filename) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// The export surface is only rendered while an export runs (it duplicates the
// whole report in the DOM). Wait until React has mounted it for this mode.
function waitForSurface(ref, mode, timeoutMs = 5000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const el = ref.current;
      if (el && el.dataset.pdfMode === mode) {
        // One more frame so layout and KaTeX glyphs are settled.
        requestAnimationFrame(() => resolve(el));
      } else if (Date.now() - started > timeoutMs) {
        reject(new Error('PDF export surface not mounted'));
      } else {
        requestAnimationFrame(tick);
      }
    };
    tick();
  });
}

function formatMb(bytes, lang) {
  const mb = bytes / (1024 * 1024);
  try {
    return mb.toLocaleString(lang || undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  } catch {
    return mb.toFixed(1);
  }
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
  const [pdfReady, setPdfReady] = useState(null);       // { url, name, size }
  const [pdfError, setPdfError] = useState('');         // stays until next export
  const [pdfMode, setPdfMode] = useState(null);         // 'chairman' | 'members' while exporting
  const [pdfMenuOpen, setPdfMenuOpen] = useState(false);
  const pdfMenuRef = useRef(null);
  const [membersOpen, setMembersOpen] = useState(false);
  const [rankingOpen, setRankingOpen] = useState(false);
  const exportRef = useRef(null);
  const pdfUrlRef = useRef(null);
  const pdfProgressRef = useRef(null); // text updated directly: no re-render
  const { t, i18n } = useTranslation();

  // Release the generated PDF blob when a new one replaces it or on unmount.
  const releasePdfUrl = () => {
    if (pdfUrlRef.current) {
      URL.revokeObjectURL(pdfUrlRef.current);
      pdfUrlRef.current = null;
    }
  };
  useEffect(() => releasePdfUrl, []);

  useEffect(() => {
    if (!pdfMenuOpen) return undefined;
    const onDown = (e) => {
      if (pdfMenuRef.current && !pdfMenuRef.current.contains(e.target)) setPdfMenuOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setPdfMenuOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [pdfMenuOpen]);

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
  // Two separate documents keep each export small:
  //   'chairman' → chairman's final synthesis + aggregate ranking
  //   'members'  → each council member's individual opinion (Stage 1)
  const handleExportPdf = async (mode) => {
    if (pdfBusy) return;
    setPdfMenuOpen(false);
    const startedAt = Date.now();
    setPdfBusy(true);
    setPdfReady(null);
    setPdfError('');
    releasePdfUrl();
    setPdfMode(mode);
    try {
      const node = await waitForSurface(exportRef, mode);
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
      const showProgress = (done) => {
        if (pdfProgressRef.current && pages.length > 1) {
          pdfProgressRef.current.textContent = ` ${done}/${pages.length}`;
        }
      };
      showProgress(0);

      // Capture one chunk and slice it into per-page JPEGs. Nothing is added to
      // the PDF until the whole chunk succeeded, so a retry never duplicates pages.
      const captureChunkPages = async (chunk, scale) => {
        const plan = planChunk(node, chunk.top, chunk.bottom);
        const chunkCanvas = await html2canvas(node, {
          scale,
          backgroundColor: '#ffffff',
          useCORS: true,
          windowWidth: node.scrollWidth,
          width: widthPx,
          y: chunk.top,
          height: Math.ceil(chunk.bottom - chunk.top),
          ignoreElements: makeIgnore(node, plan),
          onclone: (_doc, clonedNode) => restoreChunkLayout(clonedNode, plan),
        });
        try {
          if (!chunkCanvas || !chunkCanvas.width || !chunkCanvas.height) {
            throw new Error('empty capture');
          }
          const pxScale = chunkCanvas.width / widthPx; // effective device scale
          const images = [];
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
            if (!ctx) throw new Error('canvas context unavailable');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
            ctx.drawImage(chunkCanvas, 0, srcY, chunkCanvas.width, srcH,
              0, 0, pageCanvas.width, srcH);
            // JPEG is embedded as-is by jsPDF (DCTDecode); PNG would be decoded
            // and re-deflated in JavaScript, which is far slower.
            const dataUrl = pageCanvas.toDataURL('image/jpeg', PDF_JPEG_QUALITY);
            pageCanvas.width = 0; pageCanvas.height = 0; // free memory early
            if (!dataUrl.startsWith('data:image/jpeg')) throw new Error('canvas export failed');
            images.push({ dataUrl, heightPt: (srcH / pxScale) * ptPerPx });
          }
          return images;
        } finally {
          chunkCanvas.width = 0; chunkCanvas.height = 0;
        }
      };

      let pageIndex = 0;
      for (const chunk of chunks) {
        let images = null;
        let lastErr = null;
        for (const scale of PDF_RETRY_SCALES) {
          try {
            images = await captureChunkPages(chunk, scale);
            break;
          } catch (err) {
            lastErr = err;
            console.warn(`[Stage3] PDF chunk capture failed at scale ${scale}, retrying lower`, err);
          }
        }
        if (!images) throw lastErr || new Error('capture failed');
        for (const { dataUrl, heightPt } of images) {
          if (pageIndex > 0) pdf.addPage();
          pdf.addImage(dataUrl, 'JPEG', 0, PDF_MARGIN_PT, pageWidth, heightPt);
          pageIndex += 1;
        }
        showProgress(pageIndex);
      }

      if (pageIndex === 0) throw new Error('PDF export produced no page');

      const blob = pdf.output('blob');
      const name = mode === 'members'
        ? `council-members-${timestamp()}.pdf`
        : `council-report-${timestamp()}.pdf`;
      const url = URL.createObjectURL(blob);
      pdfUrlRef.current = url;
      if (canAutoDownload(startedAt)) {
        triggerDownload(url, name);
      } else {
        // Click expired during generation: let the user trigger the download.
        setPdfReady({ url, name, size: blob.size });
      }
    } catch (err) {
      console.error('[Stage3] PDF export failed:', err);
      const detail = err && (err.message || String(err));
      setPdfError(`${t('stage3.pdfError')}${detail ? ` (${detail})` : ''}`);
    } finally {
      setPdfBusy(false);
      setPdfMode(null); // unmount the heavy export surface
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
            <div className="report-pdf-menu" ref={pdfMenuRef}>
              <button type="button" className="report-action-btn"
                onClick={() => setPdfMenuOpen((v) => !v)}
                disabled={pdfBusy} data-testid="stage3-export-pdf-btn" title={t('stage3.exportPdfTitle')}
                aria-haspopup="menu" aria-expanded={pdfMenuOpen}>
                {pdfBusy ? t('stage3.pdfBusy') : t('stage3.exportPdf')}
                {pdfBusy && <span ref={pdfProgressRef} data-testid="stage3-pdf-progress" />}
                {!pdfBusy && <span className="report-pdf-caret" aria-hidden="true"> ▾</span>}
              </button>
              {pdfMenuOpen && !pdfBusy && (
                <div className="report-pdf-options" role="menu" data-testid="stage3-pdf-menu">
                  <button type="button" role="menuitem" className="report-pdf-option"
                    onClick={() => handleExportPdf('chairman')} data-testid="stage3-pdf-chairman">
                    <span className="report-pdf-option-title">{t('stage3.pdfChairman')}</span>
                    <span className="report-pdf-option-desc">{t('stage3.pdfChairmanDesc')}</span>
                  </button>
                  <button type="button" role="menuitem" className="report-pdf-option"
                    onClick={() => handleExportPdf('members')} data-testid="stage3-pdf-members"
                    disabled={members.length === 0}>
                    <span className="report-pdf-option-title">{t('stage3.pdfMembers')}</span>
                    <span className="report-pdf-option-desc">{t('stage3.pdfMembersDesc', { count: members.length })}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {(error || pdfError) && (
          <div className="report-action-error" data-testid="stage3-action-error">{error || pdfError}</div>
        )}

        {pdfReady && (
          <div className="report-pdf-ready" data-testid="stage3-pdf-ready">
            <span>{t('stage3.pdfReady', { size: formatMb(pdfReady.size, i18n.language) })}</span>
            <a
              className="report-action-btn report-pdf-download"
              href={pdfReady.url}
              download={pdfReady.name}
              data-testid="stage3-pdf-download-link"
            >
              {t('stage3.pdfDownload')}
            </a>
          </div>
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

      {/* Offscreen, fully-expanded surface used to render the WYSIWYG PDF.
          Mounted only while an export runs, with the content of that export. */}
      {pdfMode && (
        <div className="stage3-export-surface" ref={exportRef} aria-hidden="true" data-pdf-mode={pdfMode}>
          <div className="export-doc">
            {pdfMode === 'chairman' && (
              <>
                <h1 className="export-title">{t('stage3.reportTitle')}</h1>
                <div className="export-chairman">{t('stage3.chairman', { model: chairman })}</div>

                <h2 className="export-h">{t('stage3.finalSynthesis')}</h2>
                <div className="markdown-content">{md(finalResponse.response)}</div>

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
              </>
            )}

            {pdfMode === 'members' && (
              <>
                <h1 className="export-title">{t('stage3.membersReportTitle')}</h1>
                <div className="export-chairman">{t('stage3.chairman', { model: chairman })}</div>
                {members.map((m, i) => (
                  <div key={i} className="export-member">
                    <h2 className="export-h">{`${i + 1}. ${shortModel(m.model)}`}</h2>
                    <div className="markdown-content">{md(m.response)}</div>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
