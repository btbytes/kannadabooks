#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy>=1.26.0",
#     "pillow>=10.0.0",
#     "pymupdf>=1.24.0",
#     "scipy>=1.11.0",
# ]
# ///
"""Convert a single PDF inside a folder into web-efficient WebP images (one per page)
and generate an index.html to view the pages as a gallery as well as individual pages.

For each page, 3 WebP variants are created inside the folder:
1. thumb/NNNN.webp:
   Small thumbnail (~320px max width, WebP quality 70) for fast index/grid browsing.
2. full/NNNN.webp:
   High-resolution page render (200 DPI, WebP quality 82) preserving original color/grayscale
   and illustrations.
3. bw/NNNN.webp (clean grayscale / color-aware reading & OCR copy):
   250 DPI page processed to remove scan artefacts:
   - Detects whether the page contains genuine color pictures/diagrams (after white-balancing
     to ignore uniform paper yellowing/sepia tint).
   - If the page has no color pictures/diagrams, outputs a clean anti-aliased grayscale
     image: uneven lighting and gutter shadows are flattened via Gaussian background
     division, paper bleed-through and isolated dust specks (< 4 px) are suppressed to pure
     white (255), dark scanner border bars are stripped, and smooth stroke gradients are
     preserved for comfortable reading and accurate OCR.
   - If the page contains color pictures or diagrams, preserves color (RGB) while still
     white-balancing and cleaning the background illumination.

Usage:
    ./convert_pages.py [ target_dir_or_pdf ] [options]

Options:
    --title TEXT        English / main display title (default: inferred from filename)
    --kannada TEXT      Optional Kannada display title (auto-detected from ../index.md if present)
    --max-pages N       Only process the first N pages (useful for testing)
    --workers N         Number of parallel worker processes (default: half of CPU cores)
    --force             Overwrite existing page images
    --html-only         Only generate index.html without converting PDF pages
"""
from __future__ import annotations

import argparse
import concurrent.futures
import html
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # PyMuPDF

import numpy as np
from PIL import Image
from scipy import ndimage


THUMB_WIDTH = 320
FULL_DPI = 200
BW_DPI = 250


def has_color_content(
    rgb: np.ndarray,
    chroma_thresh: float = 38.0,
    min_color_fraction: float = 0.005,
) -> bool:
    """Return True if an RGB page has genuine color pictures/diagrams (ignoring paper tint)."""
    # Downsample by 4x for fast chroma analysis
    small = rgb[::4, ::4, :].astype(np.float32)

    # White-balance using the 85th percentile per channel (paper background color)
    bg_rgb = np.percentile(small.reshape(-1, 3), 85, axis=0)
    bg_rgb = np.maximum(bg_rgb, 32.0)
    wb = np.clip(small * (255.0 / bg_rgb), 0.0, 255.0)

    c_max = wb.max(axis=2)
    c_min = wb.min(axis=2)
    lum = wb.mean(axis=2)
    chroma = c_max - c_min

    # Ignore very dark ink and near-white paper; smooth locally to ignore edge fringing
    valid = (lum > 30.0) & (lum < 235.0)
    smoothed_chroma = ndimage.uniform_filter(chroma * valid, size=5, mode="nearest")

    color_pixels = np.count_nonzero(smoothed_chroma > chroma_thresh)
    return (color_pixels / float(smoothed_chroma.size)) >= min_color_fraction


def clean_page_for_reading_and_ocr(
    rgb: np.ndarray,
    sauvola_window: int = 41,
    sauvola_k: float = 0.20,
    min_speck_area: int = 4,
    border_px: int = 12,
) -> tuple[Image.Image, bool]:
    """Clean scan artefacts; return (grayscale Image unless color pictures exist, is_color)."""
    is_color = has_color_content(rgb)

    if is_color:
        # Clean color page: normalize per-channel background illumination & strip border bars
        f_rgb = rgb.astype(np.float32)
        bg = np.stack(
            [ndimage.gaussian_filter(f_rgb[:, :, c], sigma=45.0, mode="nearest") for c in range(3)],
            axis=2,
        )
        bg = np.maximum(bg, 32.0)
        norm_rgb = np.clip((f_rgb / bg) * 255.0, 0.0, 255.0)
        # Push near-white paper background to pure 255 for clean look & better compression
        lum = norm_rgb.mean(axis=2)
        paper_mask = lum > 238.0
        norm_rgb[paper_mask] = 255.0
        if border_px > 0 and norm_rgb.shape[0] > 4 * border_px and norm_rgb.shape[1] > 4 * border_px:
            norm_rgb[:border_px, :, :] = 255.0
            norm_rgb[-border_px:, :, :] = 255.0
            norm_rgb[:, :border_px, :] = 255.0
            norm_rgb[:, -border_px:, :] = 255.0
        return Image.fromarray(norm_rgb.astype(np.uint8), mode="RGB"), True

    # Grayscale path: convert RGB -> luminance
    f = (
        0.299 * rgb[:, :, 0].astype(np.float32)
        + 0.587 * rgb[:, :, 1].astype(np.float32)
        + 0.114 * rgb[:, :, 2].astype(np.float32)
    )

    # 1. Estimate slow-varying paper background illumination and normalize to 255.
    bg = ndimage.gaussian_filter(f, sigma=35.0, mode="nearest")
    bg = np.maximum(bg, 1.0)
    norm = np.clip((f / bg) * 255.0, 0.0, 255.0)

    # 2. Local Sauvola threshold to identify foreground (text + grayscale diagrams/shading)
    # vs. paper background / bleed-through.
    mean = ndimage.uniform_filter(norm, size=sauvola_window, mode="nearest")
    mean_sq = ndimage.uniform_filter(norm * norm, size=sauvola_window, mode="nearest")
    var = np.maximum(mean_sq - mean * mean, 0.0)
    std = np.sqrt(var)
    thresh = mean * (1.0 + sauvola_k * ((std / 128.0) - 1.0))

    fg = (norm < thresh) | (norm < 220.0)

    # 3. Strip dark scanner edge bars along the outer page border.
    if border_px > 0 and fg.shape[0] > 4 * border_px and fg.shape[1] > 4 * border_px:
        fg[:border_px, :] = False
        fg[-border_px:, :] = False
        fg[:, :border_px] = False
        fg[:, -border_px:] = False

    # 4. Connected-component despeckling: remove tiny isolated salt-and-pepper specks
    # without eroding thin strokes or Kannada vowel signs.
    if min_speck_area > 1:
        labels, num = ndimage.label(fg)
        if num > 0:
            counts = np.bincount(labels.ravel())
            remove_mask = counts < min_speck_area
            remove_mask[0] = False
            fg[remove_mask[labels]] = False

    # 5. Contrast-stretch foreground grayscale while setting background to pure white (255).
    # Soft ramp near threshold keeps anti-aliased glyph edges smooth.
    cleaned = np.where(fg, norm, 255.0)
    # Darken ink core slightly for crisp reading/OCR while preserving midtones
    cleaned = np.clip((cleaned - 25.0) * (255.0 / 215.0), 0.0, 255.0)
    # Quantize to 32 gray levels so lossless/near-lossless WebP compresses tightly
    quantized = (np.round(cleaned / 8.0) * 8.0).clip(0.0, 255.0).astype(np.uint8)
    return Image.fromarray(quantized, mode="L"), False


def render_page_pixmap(page: fitz.Page, dpi: int, colorspace: fitz.Colorspace) -> Image.Image:
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, colorspace=colorspace, alpha=False)
    mode = "L" if colorspace == fitz.csGRAY else "RGB"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def convert_single_page(
    pdf_path: Path,
    out_dir: Path,
    idx: int,
    force: bool = False,
) -> tuple[int, bool, str | None]:
    """Convert a single 0-indexed page of pdf_path into thumb, full, and bw WebP files.

    Returns (page_num, was_converted, error_msg).
    """
    page_num = idx + 1
    fname = f"{page_num:04d}.webp"
    thumb_path = out_dir / "thumb" / fname
    full_path = out_dir / "full" / fname
    bw_path = out_dir / "bw" / fname

    if not force and thumb_path.is_file() and full_path.is_file() and bw_path.is_file():
        return (page_num, False, None)

    try:
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(idx)

            # 1 & 2: Full resolution + Thumbnail (derived from full render)
            if force or not full_path.is_file() or not thumb_path.is_file():
                full_img = render_page_pixmap(page, FULL_DPI, fitz.csRGB)
                if force or not full_path.is_file():
                    full_img.save(full_path, format="WEBP", quality=82, method=4)
                if force or not thumb_path.is_file():
                    w, h = full_img.size
                    thumb_h = max(1, int(round(h * (THUMB_WIDTH / float(w)))))
                    thumb_img = full_img.resize((THUMB_WIDTH, thumb_h), Image.Resampling.LANCZOS)
                    thumb_img.save(thumb_path, format="WEBP", quality=70, method=4)

            # 3: Clean grayscale (or color if page has color pictures/diagrams) for reading & OCR
            if force or not bw_path.is_file():
                rgb_img = render_page_pixmap(page, BW_DPI, fitz.csRGB)
                bw_img, is_color = clean_page_for_reading_and_ocr(np.asarray(rgb_img))
                if is_color:
                    bw_img.save(bw_path, format="WEBP", quality=78, method=4)
                else:
                    bw_img.save(bw_path, format="WEBP", quality=75, method=4)

        return (page_num, True, None)
    except Exception as exc:  # noqa: BLE001
        return (page_num, False, str(exc))


def clean_display_title(pdf_path: Path) -> str:
    stem = pdf_path.stem
    stem = re.sub(r"\s*\((kann+n?ada|english)\)\s*$", "", stem, flags=re.IGNORECASE).strip()
    if "-" in stem or "_" in stem:
        words = re.split(r"[-_]+", stem)
        return " ".join(w.capitalize() if w.islower() else w for w in words if w)
    return stem


def detect_titles_from_parent_index(pdf_path: Path) -> tuple[str | None, str | None]:
    """Check ../index.md for a markdown link referencing this PDF with 'Kannada|English' title."""
    parent_index = pdf_path.resolve().parent.parent / "index.md"
    if not parent_index.is_file():
        return None, None
    try:
        text = parent_index.read_text(encoding="utf-8")
        pattern = re.compile(r"\[([^\]]+)\]\([^)]*" + re.escape(pdf_path.name) + r"\)")
        m = pattern.search(text)
        if m:
            label = m.group(1).strip()
            if "|" in label:
                kn_part, en_part = [p.strip() for p in label.split("|", 1)]
                return en_part or None, kn_part or None
            return label, None
    except Exception:  # noqa: BLE001
        pass
    return None, None


def get_page_count(pdf_path: Path, out_dir: Path) -> int:
    """Determine page count from extracted images and/or the source PDF."""
    count = 0
    full_dir = out_dir / "full"
    if full_dir.is_dir():
        count = len(list(full_dir.glob("*.webp")))
    if pdf_path.is_file():
        try:
            with fitz.open(pdf_path) as doc:
                count = max(count, len(doc))
        except Exception:  # noqa: BLE001
            pass
    return count


def build_reader_html(
    pdf_filename: str,
    en_title: str,
    kn_title: str | None,
    page_count: int,
    has_parent_index: bool = True,
) -> str:
    pdf_href = quote(pdf_filename)

    if kn_title:
        page_title = f"{kn_title} — {en_title}"
        header_title_html = (
            f'<span class="title-kn">{html.escape(kn_title)}</span>'
            f'<span class="title-en">{html.escape(en_title)}</span>'
        )
    else:
        page_title = en_title
        header_title_html = f'<span class="title-main">{html.escape(en_title)}</span>'

    back_link_html = (
        '<a class="back-link" href="../index.html">&larr; All Books</a>'
        if has_parent_index
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title)} — Reader</title>
<style>
  :root {{
    --maroon: #72211f;
    --maroon-dark: #571915;
    --gold: #c9a227;
    --bg: #1e1b18;
    --panel: #2a2521;
    --ink: #f5efe6;
    --muted: #b8aca0;
    --line: #3d352e;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Georgia, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }}
  header {{
    position: sticky;
    top: 0;
    z-index: 30;
    background: var(--maroon);
    color: #f7ecd4;
    border-bottom: 3px solid var(--gold);
    padding: 0.55rem 1rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }}
  .back-link {{
    color: #ffe9b0;
    text-decoration: none;
    font-size: 0.88rem;
    padding: 0.3rem 0.65rem;
    border: 1px solid rgba(255, 233, 176, 0.45);
    border-radius: 6px;
    white-space: nowrap;
  }}
  .back-link:hover {{ background: var(--maroon-dark); }}
  .book-title {{
    display: flex;
    flex-direction: column;
    min-width: 0;
  }}
  .title-kn {{
    font-size: 1.05rem;
    font-weight: 600;
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .title-en {{
    font-size: 0.8rem;
    color: #ecd9ae;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .title-main {{
    font-size: 1.02rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .toolbar {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
  }}
  button, .btn-link, select {{
    font-family: inherit;
    font-size: 0.85rem;
    color: #fff;
    background: rgba(0, 0, 0, 0.28);
    border: 1px solid rgba(255, 233, 176, 0.4);
    border-radius: 6px;
    padding: 0.35rem 0.7rem;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }}
  button:hover:not(:disabled), .btn-link:hover, select:hover {{
    background: var(--maroon-dark);
  }}
  button:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
  }}
  button.active {{
    background: var(--gold);
    color: #1e1b18;
    border-color: var(--gold);
    font-weight: 600;
  }}
  .page-jump {{
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.85rem;
  }}
  #page-input {{
    width: 4.2rem;
    text-align: center;
    padding: 0.3rem 0.35rem;
    border-radius: 6px;
    border: 1px solid rgba(255, 233, 176, 0.5);
    background: rgba(0, 0, 0, 0.35);
    color: #fff;
    font-size: 0.85rem;
  }}
  main {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 1rem 0.5rem 2.5rem;
  }}
  .stage {{
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    max-width: 100%;
  }}
  #page-img {{
    display: block;
    background: #fff;
    box-shadow: 0 6px 28px rgba(0, 0, 0, 0.65);
    border-radius: 2px;
    user-select: none;
    max-width: min(1000px, 96vw);
    height: auto;
  }}
  body.fit-height #page-img {{
    max-height: calc(100vh - 96px);
    width: auto;
    max-width: 96vw;
  }}
  body.fit-original #page-img {{
    max-width: none;
    max-height: none;
  }}
  .nav-zone {{
    position: fixed;
    top: 64px;
    bottom: 48px;
    width: 12vw;
    min-width: 44px;
    max-width: 140px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 10;
    opacity: 0;
    transition: opacity 0.15s ease;
    user-select: none;
  }}
  .nav-zone:hover {{ opacity: 1; }}
  .nav-zone.prev {{ left: 0; }}
  .nav-zone.next {{ right: 0; }}
  .nav-pill {{
    background: rgba(114, 33, 31, 0.88);
    color: #fff;
    border: 1px solid var(--gold);
    border-radius: 999px;
    padding: 0.6rem 0.9rem;
    font-size: 1.1rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  }}
  .bottom-bar {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 25;
    background: rgba(42, 37, 33, 0.95);
    border-top: 1px solid var(--line);
    padding: 0.4rem 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    font-size: 0.82rem;
    color: var(--muted);
    backdrop-filter: blur(6px);
  }}
  #scrubber {{
    width: min(420px, 55vw);
    accent-color: var(--gold);
    cursor: pointer;
  }}
  /* Thumbnails Drawer / Modal */
  #thumbs-overlay {{
    position: fixed;
    inset: 0;
    z-index: 50;
    background: rgba(18, 15, 13, 0.94);
    display: none;
    flex-direction: column;
  }}
  #thumbs-overlay.open {{
    display: flex;
  }}
  .thumbs-header {{
    background: var(--panel);
    border-bottom: 1px solid var(--line);
    padding: 0.75rem 1.2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .thumbs-grid {{
    flex: 1;
    overflow-y: auto;
    padding: 1.2rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 1rem;
    align-content: start;
  }}
  .thumb-card {{
    background: var(--panel);
    border: 2px solid transparent;
    border-radius: 6px;
    padding: 0.4rem;
    text-align: center;
    cursor: pointer;
    color: var(--ink);
    text-decoration: none;
    transition: transform 0.12s ease, border-color 0.12s ease;
  }}
  .thumb-card:hover {{
    transform: translateY(-2px);
    border-color: rgba(201, 162, 39, 0.6);
  }}
  .thumb-card.current {{
    border-color: var(--gold);
    background: rgba(201, 162, 39, 0.16);
  }}
  .thumb-card img {{
    width: 100%;
    aspect-ratio: 1 / 1.42;
    object-fit: contain;
    background: #fff;
    border-radius: 3px;
    display: block;
  }}
  .thumb-label {{
    margin-top: 0.35rem;
    font-size: 0.78rem;
    color: var(--muted);
  }}
  .thumb-card.current .thumb-label {{
    color: var(--gold);
    font-weight: 600;
  }}
  .status-msg {{
    margin-top: 1rem;
    color: var(--muted);
    font-size: 0.9rem;
    text-align: center;
  }}
</style>
</head>
<body>
  <header>
    <div class="brand">
      {back_link_html}
      <div class="book-title">{header_title_html}</div>
    </div>
    <div class="toolbar">
      <button type="button" id="btn-first" title="First page (Home)">&laquo;</button>
      <button type="button" id="btn-prev" title="Previous page (&larr;)">&lsaquo; Prev</button>
      <form class="page-jump" id="jump-form">
        <input id="page-input" type="number" min="1" max="{page_count}" value="1" aria-label="Page number">
        <span>/ <span id="total-pages">{page_count}</span></span>
      </form>
      <button type="button" id="btn-next" title="Next page (&rarr;)">Next &rsaquo;</button>
      <button type="button" id="btn-last" title="Last page (End)">&raquo;</button>
      <button type="button" id="btn-thumbs" title="View all page thumbnails (G)">Thumbnails</button>
      <select id="mode-select" aria-label="Image mode" title="Switch between Full Resolution and Clean Grayscale/BW">
        <option value="full" selected>Full Resolution</option>
        <option value="bw">Clean / B&amp;W</option>
      </select>
      <select id="fit-select" aria-label="Fit mode" title="Page fit mode">
        <option value="width" selected>Fit Width</option>
        <option value="height">Fit Height</option>
        <option value="original">Actual Size</option>
      </select>
      <a class="btn-link" href="{pdf_href}" download title="Download original PDF">PDF</a>
    </div>
  </header>

  <main>
    <div class="nav-zone prev" id="zone-prev" title="Previous page"><span class="nav-pill">&lsaquo;</span></div>
    <div class="stage">
      <img id="page-img" alt="Page 1" src="full/0001.webp">
    </div>
    <div class="status-msg" id="status-msg" hidden></div>
    <div class="nav-zone next" id="zone-next" title="Next page"><span class="nav-pill">&rsaquo;</span></div>
  </main>

  <div class="bottom-bar">
    <span id="page-caption">Page 1 of {page_count}</span>
    <input id="scrubber" type="range" min="1" max="{max(1, page_count)}" value="1" aria-label="Page slider">
    <span>Keys: &larr;/&rarr; turn page &middot; G thumbnails &middot; F fit</span>
  </div>

  <div id="thumbs-overlay" role="dialog" aria-modal="true" aria-label="Page Thumbnails">
    <div class="thumbs-header">
      <strong>All Pages ({page_count})</strong>
      <button type="button" id="btn-close-thumbs">Close (Esc)</button>
    </div>
    <div class="thumbs-grid" id="thumbs-grid"></div>
  </div>

<script>
(function () {{
  var TOTAL = {page_count};
  var currentPage = 1;
  var currentMode = 'full';
  var thumbsBuilt = false;

  var imgEl = document.getElementById('page-img');
  var inputEl = document.getElementById('page-input');
  var scrubberEl = document.getElementById('scrubber');
  var captionEl = document.getElementById('page-caption');
  var statusEl = document.getElementById('status-msg');
  var btnFirst = document.getElementById('btn-first');
  var btnPrev = document.getElementById('btn-prev');
  var btnNext = document.getElementById('btn-next');
  var btnLast = document.getElementById('btn-last');
  var btnThumbs = document.getElementById('btn-thumbs');
  var btnCloseThumbs = document.getElementById('btn-close-thumbs');
  var overlayEl = document.getElementById('thumbs-overlay');
  var gridEl = document.getElementById('thumbs-grid');
  var modeSelect = document.getElementById('mode-select');
  var fitSelect = document.getElementById('fit-select');

  function pad4(n) {{
    return String(n).padStart(4, '0');
  }}

  function pageUrl(page, mode) {{
    return (mode || currentMode) + '/' + pad4(page) + '.webp';
  }}

  function thumbUrl(page) {{
    return 'thumb/' + pad4(page) + '.webp';
  }}

  function readStateFromUrl() {{
    var params = new URLSearchParams(window.location.search);
    var p = parseInt(params.get('page'), 10);
    if (!p && window.location.hash) {{
      var m = window.location.hash.match(/page=(\\d+)/);
      if (m) p = parseInt(m[1], 10);
    }}
    if (isNaN(p) || p < 1) p = 1;
    if (TOTAL > 0 && p > TOTAL) p = TOTAL;

    var mode = params.get('mode');
    if (mode === 'bw' || mode === 'full') {{
      currentMode = mode;
      modeSelect.value = mode;
    }}
    return p;
  }}

  function writeStateToUrl(replace) {{
    var url = new URL(window.location.href);
    url.searchParams.set('page', String(currentPage));
    if (currentMode !== 'full') {{
      url.searchParams.set('mode', currentMode);
    }} else {{
      url.searchParams.delete('mode');
    }}
    try {{
      if (replace) {{
        window.history.replaceState({{ page: currentPage, mode: currentMode }}, '', url);
      }} else {{
        window.history.pushState({{ page: currentPage, mode: currentMode }}, '', url);
      }}
    }} catch (e) {{
      window.location.hash = 'page=' + currentPage;
    }}
  }}

  function preload(page) {{
    if (page < 1 || page > TOTAL) return;
    var pre = new Image();
    pre.src = pageUrl(page, currentMode);
  }}

  function updateHighlightInThumbs() {{
    if (!thumbsBuilt) return;
    var prev = gridEl.querySelector('.thumb-card.current');
    if (prev) prev.classList.remove('current');
    var next = gridEl.querySelector('[data-page="' + currentPage + '"]');
    if (next) next.classList.add('current');
  }}

  function goToPage(page, opts) {{
    opts = opts || {{}};
    if (TOTAL < 1) return;
    var target = Math.max(1, Math.min(TOTAL, parseInt(page, 10) || 1));
    currentPage = target;

    statusEl.hidden = true;
    imgEl.src = pageUrl(currentPage, currentMode);
    imgEl.alt = 'Page ' + currentPage;
    inputEl.value = String(currentPage);
    scrubberEl.value = String(currentPage);
    captionEl.textContent = 'Page ' + currentPage + ' of ' + TOTAL;

    btnFirst.disabled = currentPage <= 1;
    btnPrev.disabled = currentPage <= 1;
    btnNext.disabled = currentPage >= TOTAL;
    btnLast.disabled = currentPage >= TOTAL;

    if (!opts.skipUrl) {{
      writeStateToUrl(Boolean(opts.replaceUrl));
    }}
    updateHighlightInThumbs();
    preload(currentPage + 1);
    preload(currentPage - 1);
    if (!opts.keepScroll) {{
      window.scrollTo({{ top: 0, behavior: 'instant' }});
    }}
  }}

  imgEl.addEventListener('error', function () {{
    statusEl.hidden = false;
    statusEl.textContent = 'Page image ' + pageUrl(currentPage, currentMode) + ' has not been generated yet. Run convert_pages.py to extract pages.';
  }});

  function buildThumbs() {{
    if (thumbsBuilt) return;
    var frag = document.createDocumentFragment();
    for (var i = 1; i <= TOTAL; i++) {{
      var a = document.createElement('a');
      a.className = 'thumb-card' + (i === currentPage ? ' current' : '');
      a.dataset.page = String(i);
      a.href = '?page=' + i;
      var im = document.createElement('img');
      im.loading = 'lazy';
      im.src = thumbUrl(i);
      im.alt = 'Page ' + i;
      var lbl = document.createElement('div');
      lbl.className = 'thumb-label';
      lbl.textContent = 'Page ' + i;
      a.appendChild(im);
      a.appendChild(lbl);
      a.addEventListener('click', function (ev) {{
        ev.preventDefault();
        var p = parseInt(this.dataset.page, 10);
        closeThumbs();
        goToPage(p);
      }});
      frag.appendChild(a);
    }}
    gridEl.appendChild(frag);
    thumbsBuilt = true;
  }}

  function openThumbs() {{
    buildThumbs();
    updateHighlightInThumbs();
    overlayEl.classList.add('open');
    btnThumbs.classList.add('active');
    var cur = gridEl.querySelector('.thumb-card.current');
    if (cur) cur.scrollIntoView({{ block: 'center' }});
  }}

  function closeThumbs() {{
    overlayEl.classList.remove('open');
    btnThumbs.classList.remove('active');
  }}

  function toggleThumbs() {{
    if (overlayEl.classList.contains('open')) closeThumbs();
    else openThumbs();
  }}

  btnFirst.addEventListener('click', function () {{ goToPage(1); }});
  btnPrev.addEventListener('click', function () {{ goToPage(currentPage - 1); }});
  btnNext.addEventListener('click', function () {{ goToPage(currentPage + 1); }});
  btnLast.addEventListener('click', function () {{ goToPage(TOTAL); }});
  document.getElementById('zone-prev').addEventListener('click', function () {{ goToPage(currentPage - 1); }});
  document.getElementById('zone-next').addEventListener('click', function () {{ goToPage(currentPage + 1); }});

  document.getElementById('jump-form').addEventListener('submit', function (e) {{
    e.preventDefault();
    goToPage(inputEl.value);
  }});
  inputEl.addEventListener('change', function () {{
    goToPage(inputEl.value);
  }});
  scrubberEl.addEventListener('input', function () {{
    captionEl.textContent = 'Page ' + scrubberEl.value + ' of ' + TOTAL;
  }});
  scrubberEl.addEventListener('change', function () {{
    goToPage(scrubberEl.value);
  }});

  btnThumbs.addEventListener('click', toggleThumbs);
  btnCloseThumbs.addEventListener('click', closeThumbs);
  overlayEl.addEventListener('click', function (e) {{
    if (e.target === overlayEl) closeThumbs();
  }});

  modeSelect.addEventListener('change', function () {{
    currentMode = modeSelect.value;
    goToPage(currentPage, {{ keepScroll: true }});
  }});

  fitSelect.addEventListener('change', function () {{
    document.body.classList.remove('fit-height', 'fit-original');
    if (fitSelect.value === 'height') document.body.classList.add('fit-height');
    else if (fitSelect.value === 'original') document.body.classList.add('fit-original');
  }});

  window.addEventListener('popstate', function () {{
    goToPage(readStateFromUrl(), {{ skipUrl: true }});
  }});
  window.addEventListener('hashchange', function () {{
    goToPage(readStateFromUrl(), {{ skipUrl: true }});
  }});

  window.addEventListener('keydown', function (e) {{
    if (e.target === inputEl || e.target === modeSelect || e.target === fitSelect) return;
    if (e.key === 'Escape' && overlayEl.classList.contains('open')) {{
      closeThumbs();
      return;
    }}
    if (e.key === 'g' || e.key === 'G') {{
      e.preventDefault();
      toggleThumbs();
      return;
    }}
    if (overlayEl.classList.contains('open')) return;
    if (e.key === 'ArrowRight' || e.key === 'j' || e.key === 'PageDown') {{
      e.preventDefault();
      goToPage(currentPage + 1);
    }} else if (e.key === 'ArrowLeft' || e.key === 'k' || e.key === 'PageUp') {{
      e.preventDefault();
      goToPage(currentPage - 1);
    }} else if (e.key === 'Home') {{
      e.preventDefault();
      goToPage(1);
    }} else if (e.key === 'End') {{
      e.preventDefault();
      goToPage(TOTAL);
    }} else if (e.key === 'f' || e.key === 'F') {{
      e.preventDefault();
      var order = ['width', 'height', 'original'];
      var nextFit = order[(order.indexOf(fitSelect.value) + 1) % order.length];
      fitSelect.value = nextFit;
      fitSelect.dispatchEvent(new Event('change'));
    }}
  }});

  goToPage(readStateFromUrl(), {{ replaceUrl: true }});
}})();
</script>
</body>
</html>
"""


def resolve_pdf_and_folder(target: Path) -> tuple[Path, Path]:
    """Return (pdf_path, folder_path) given either a folder containing one PDF or a PDF path."""
    target = target.resolve()
    if target.is_file():
        if target.suffix.lower() != ".pdf":
            raise ValueError(f"Target file is not a PDF: {target}")
        return target, target.parent

    if not target.is_dir():
        raise FileNotFoundError(f"Target path does not exist: {target}")

    pdfs = sorted(p for p in target.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        raise FileNotFoundError(f"No PDF file found in folder: {target}")
    if len(pdfs) > 1:
        # Prefer the PDF matching the folder name if multiple exist
        matching = [p for p in pdfs if p.stem.lower() == target.name.lower()]
        if len(matching) == 1:
            return matching[0], target
        names = ", ".join(p.name for p in pdfs)
        raise ValueError(
            f"Multiple PDFs found in {target} ({names}); pass the specific PDF path."
        )
    return pdfs[0], target


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Folder containing the PDF, or path to the PDF itself (default: current directory)",
    )
    p.add_argument("--title", type=str, default=None, help="Override English/main display title")
    p.add_argument("--kannada", type=str, default=None, help="Optional Kannada display title")
    p.add_argument("--max-pages", type=int, default=None, help="Maximum pages to convert")
    p.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 4) // 2),
        help="Parallel worker processes",
    )
    p.add_argument("--force", action="store_true", help="Re-generate existing page files")
    p.add_argument(
        "--html-only",
        action="store_true",
        help="Only generate index.html without converting pages",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        pdf_path, out_dir = resolve_pdf_and_folder(args.target)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    thumb_dir = out_dir / "thumb"
    full_dir = out_dir / "full"
    bw_dir = out_dir / "bw"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    full_dir.mkdir(parents=True, exist_ok=True)
    bw_dir.mkdir(parents=True, exist_ok=True)

    try:
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
    except Exception as exc:  # noqa: BLE001
        print(f"Error opening PDF {pdf_path}: {exc}", file=sys.stderr)
        return 1

    errors = 0
    if not args.html_only:
        limit = min(total_pages, args.max_pages) if args.max_pages else total_pages
        print(
            f"Converting {pdf_path.name} ({limit}/{total_pages} pages) in {out_dir} "
            f"using {args.workers} worker(s)...",
            flush=True,
        )
        converted = 0
        if args.workers <= 1 or limit == 1:
            for idx in range(limit):
                page_num, did_conv, err = convert_single_page(pdf_path, out_dir, idx, args.force)
                if err:
                    errors += 1
                    print(f"  [Page {page_num}/{limit}] ERROR: {err}", flush=True)
                elif did_conv:
                    converted += 1
                    if page_num % 10 == 0 or page_num == limit:
                        print(f"  [{page_num}/{limit}] pages processed...", flush=True)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
                futs = [
                    pool.submit(convert_single_page, pdf_path, out_dir, idx, args.force)
                    for idx in range(limit)
                ]
                done_count = 0
                for fut in concurrent.futures.as_completed(futs):
                    page_num, did_conv, err = fut.result()
                    done_count += 1
                    if err:
                        errors += 1
                        print(f"  [Page {page_num}] ERROR: {err}", flush=True)
                    else:
                        if did_conv:
                            converted += 1
                        if done_count % 10 == 0 or done_count == limit:
                            print(f"  [{done_count}/{limit}] pages processed...", flush=True)

        print(
            f"Finished image conversion: {converted} converted / {total_pages} total pages"
            + (f" ({errors} errors)" if errors else ""),
            flush=True,
        )

    detected_en, detected_kn = detect_titles_from_parent_index(pdf_path)
    en_title = args.title or detected_en or clean_display_title(pdf_path)
    kn_title = args.kannada if args.kannada is not None else detected_kn
    has_parent_index = (out_dir.parent / "index.html").is_file() or (out_dir.parent / "index.md").is_file()

    page_count = get_page_count(pdf_path, out_dir)
    reader_html = build_reader_html(
        pdf_filename=pdf_path.name,
        en_title=en_title,
        kn_title=kn_title,
        page_count=page_count,
        has_parent_index=has_parent_index,
    )
    index_path = out_dir / "index.html"
    index_path.write_text(reader_html, encoding="utf-8")
    print(f"Generated {index_path} ({page_count} pages, title: {en_title!r}).", flush=True)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
