#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy>=1.26.0",
#     "pillow>=10.0.0",
# ]
# ///
"""Convert cleaned page images (bw/NNNN.webp) into Kannada Markdown files (ocr/NNNN.md)
using a Hybrid Dual-Tesseract + Vision-Language Model OCR pipeline:
1. Local Tesseract Pass (`-l kan` and `-l script/Kannada` at full 250 DPI) provides two
   complementary character/line anchors so no lines are skipped.
2. Vision-Language Model (`unsloth/Qwen2.5-VL-32B-Instruct-GGUF` by default) hosted on
   Unsloth Studio (`http://100.101.214.127:8888`) inspects the page image alongside both
   OCR drafts to resolve ottaksharas, glyph confusions, grammar equations, and tables.

Usage:
    ./ocr_pages.py [target_dir] [options]

Examples:
    UNSLOTH_API_KEY=sk-unsloth-... ./ocr_pages.py --pages 10,15
    UNSLOTH_API_KEY=sk-unsloth-... ./ocr_pages.py
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image


DEFAULT_HOST = "http://100.101.214.127:8888"
DEFAULT_MODEL = "unsloth/Qwen2.5-VL-32B-Instruct-GGUF"
VLM_MAX_IMAGE_DIM = 1288  # Fits cleanly within llama-server default mtmd batch limit

SYSTEM_PROMPT = """You are an expert Kannada scholar, grammarian, and optical character recognition (OCR) specialist.
Your task is to produce a 100% accurate UTF-8 Kannada Markdown transcription of a scanned page from the Kannada grammar book "ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ".

Follow these strict rules:
1. OUTPUT ONLY THE TRANSCRIBED KANNADA MARKDOWN TEXT. Do not include any introductory or concluding remarks, explanations, or ```markdown code fences.
2. You are given:
   - The scanned page image.
   - Two noisy local Tesseract OCR drafts (`kan` and `script/Kannada`) of the exact same page.
3. How to combine the image and the two OCR drafts:
   - Use the drafts to anchor every single line in exact reading order (never skip, summarize, or invent lines).
   - Notice that `kan` and `script/Kannada` make complementary glyph errors:
     * `kan` often misreads ಮ as ನು (e.g. ನಾನು instead of ನಾಮ), ರೈ as ಕೈ (ಕೈತನು instead of ರೈತನು), ಕೃ as ಶ್ಯ (ಪ್ರಶ್ಯತಿ instead of ಪ್ರಕೃತಿ), and ವ as ನ (ಹುತ್ತನಿದೆ instead of ಹುತ್ತವಿದೆ).
     * `script/Kannada` gets ನಾಮ and ರೈತನು right, but often misreads ಪ as ಸ (ಸದಕ್ಕೆ/ಸ್ರಕೃತಿ/ಸ-ವರ್ಗ instead of ಪದಕ್ಕೆ/ಪ್ರಕೃತಿ/ಪ-ವರ್ಗ) and ವ as ನ (ಹೊಲನನ್ನು instead of ಹೊಲವನ್ನು).
   - Reference Kannada Varnamale when transcribing alphabet sections:
     * ಹ್ರಸ್ವ ಸ್ವರಗಳು (6): ಅ, ಇ, ಉ, ಋ, ಎ, ಒ
     * ದೀರ್ಘ ಸ್ವರಗಳು (8): ಆ, ಈ, ಊ, ೠ, ಏ, ಐ, ಓ, ಔ
     * ವರ್ಗೀಯ ವ್ಯಂಜನಗಳು (25):
       - ಕ—ವರ್ಗ: ಕ ಖ ಗ ಘ ಙ
       - ಚ—ವರ್ಗ: ಚ ಛ ಜ ಝ ಞ
       - ಟ—ವರ್ಗ: ಟ ಠ ಡ ಢ ಣ
       - ತ—ವರ್ಗ: ತ ಥ ದ ಧ ನ
       - ಪ—ವರ್ಗ: ಪ ಫ ಬ ಭ ಮ
     * ಅವರ್ಗೀಯ ವ್ಯಂಜನಗಳು (9): ಯ ರ ಲ ವ ಶ ಷ ಸ ಹ ಳ
   - Compare both drafts with the page image and Kannada grammar context to output the exact, orthographically correct Kannada words, ottaksharas (conjunct subscripts), arkavattu (ರ್), and halant/virama (್).
4. Grammar equations and decompositions MUST use clean `+` and `=` signs as shown in the image:
   - Example: `ಕ್ + ಅ = ಕ ; ಇದೇ ರೀತಿಯಾಗಿ ಚ್ + ಆ = ಚಾ, ಟ್ + ಇ = ಟಿ, ತ್ + ಈ = ತೀ, ಪ್ + ಉ = ಪು ಆಗುವುದು.`
   - Example: `ಹೊಲ + ಉ = ಹೊಲವು (ವ್ + ಉ = ವು)`
   - Example: `ಹೊಲ + ಅಲ್ಲಿ = ಹೊಲದಲ್ಲಿ`, `ಹೊಲ + ಅನ್ನು = ಹೊಲವನ್ನು`, `ಹೊಲ + ದ = ಹೊಲದ`
5. Format headings, bullet squares (`□`), and consonant/grammar tables cleanly in Markdown.
6. Ignore any stray single-character scanner bleed-through along the extreme left/right page edges."""


def api_request(
    host: str,
    path: str,
    api_key: str,
    method: str = "GET",
    payload: dict | None = None,
    timeout: float = 300.0,
) -> dict:
    url = host.rstrip("/") + path
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} on {method} {path}: {err_body}") from exc


def normalize_repo_id(model_name: str) -> str:
    if "/" not in model_name:
        return f"unsloth/{model_name}"
    return model_name


def ensure_model_loaded(
    host: str,
    api_key: str,
    model_name: str,
    quant_override: str | None = None,
    force_reload: bool = False,
) -> str:
    """Ensure the requested GGUF vision model is downloaded and loaded in Unsloth Studio."""
    repo_id = normalize_repo_id(model_name)
    short_name = repo_id.split("/")[-1].lower()

    if not force_reload:
        status = api_request(host, "/api/inference/status", api_key)
        active = (status.get("active_model") or status.get("model_identifier") or "").lower()
        if active and short_name in active and status.get("is_vision") and not status.get("disable_vision"):
            print(f"Model already loaded and active: {status.get('active_model')}", flush=True)
            return repo_id

    q_repo = urllib.parse.quote(repo_id, safe="")
    variants_info = api_request(host, f"/api/models/gguf-variants?repo_id={q_repo}", api_key)
    variants = variants_info.get("variants") or []
    default_quant = variants_info.get("default_variant") or "UD-Q4_K_XL"

    downloaded_variants = [v for v in variants if v.get("downloaded")]
    if quant_override:
        chosen_quant = quant_override
        is_downloaded = any(v.get("quant") == chosen_quant and v.get("downloaded") for v in variants)
    elif downloaded_variants:
        chosen_quant = downloaded_variants[0]["quant"]
        is_downloaded = True
    else:
        chosen_quant = default_quant
        is_downloaded = False

    if not is_downloaded:
        target_v = next((v for v in variants if v.get("quant") == chosen_quant), None)
        expected_bytes = target_v.get("download_size_bytes", 0) if target_v else 0
        size_gb = expected_bytes / (1024**3) if expected_bytes else 0
        print(
            f"Downloading {repo_id} ({chosen_quant}, ~{size_gb:.1f} GB) on Unsloth server...",
            flush=True,
        )
        api_request(
            host,
            "/api/hub/download",
            api_key,
            method="POST",
            payload={
                "repo_id": repo_id,
                "gguf_variant": chosen_quant,
                "transport_mode": "auto",
            },
        )
        last_pct = -1
        while True:
            time.sleep(4.0)
            st = api_request(
                host,
                f"/api/hub/download-status?repo_id={q_repo}&gguf_variant={urllib.parse.quote(chosen_quant)}",
                api_key,
            )
            state = st.get("state")
            if state == "complete":
                print(f"Download of {repo_id} ({chosen_quant}) complete!", flush=True)
                break
            if state in ("error", "cancelled"):
                raise RuntimeError(f"Model download failed ({state}): {st.get('error')}")
            prog = api_request(
                host,
                f"/api/hub/gguf-download-progress?repo_id={q_repo}&variant={urllib.parse.quote(chosen_quant)}&expected_bytes={expected_bytes}",
                api_key,
            )
            pct = int(prog.get("percent") or 0)
            dl_bytes = prog.get("downloaded_bytes") or 0
            if pct != last_pct:
                print(
                    f"  Download progress: {pct}% ({dl_bytes / (1024**3):.2f} / {size_gb:.2f} GB) [{state}]",
                    flush=True,
                )
                last_pct = pct

    print(f"Loading model {repo_id} ({chosen_quant}) onto RTX 5090...", flush=True)
    load_resp = api_request(
        host,
        "/api/inference/load",
        api_key,
        method="POST",
        payload={
            "model_path": repo_id,
            "gguf_variant": chosen_quant,
            "disable_vision": False,
            "gpu_memory_mode": "auto",
            "n_batch": 4096,
            "n_ubatch": 1024,
            "force_reload": force_reload,
            "force_cancel_active": True,
        },
        timeout=600.0,
    )
    print(f"Model loaded: {load_resp.get('model_path', repo_id)} ({chosen_quant})", flush=True)
    return repo_id


def crop_gutter_margins(img: Image.Image) -> Image.Image:
    """Detect and whiten outer spine bleed-through and scanner border bars without clipping text."""
    arr_rgb = img.convert("RGB")
    arr_gray = np.asarray(img.convert("L"))
    h, w = arr_gray.shape

    # Measure vertical column ink density over the middle 90% of page height
    mid = arr_gray[int(h * 0.05) : int(h * 0.95), :]
    col_ink = (mid < 200).mean(axis=0)

    # Left gutter: look for a clean vertical valley (< 0.2% ink over 6px) in the leftmost 6%
    # that separates left-edge bleed-through/spine line from the main text block.
    left_zone = int(w * 0.06)
    left_cut = int(w * 0.006)
    for x in range(left_zone, int(w * 0.01), -1):
        if np.all(col_ink[x - 6 : x] < 0.002) and col_ink[: x - 6].max() > 0.01:
            left_cut = x
            break

    # Right gutter: look for a clean vertical valley in the rightmost 6%
    right_zone = int(w * 0.94)
    right_cut = int(w * 0.994)
    for x in range(right_zone, int(w * 0.99)):
        if np.all(col_ink[x : x + 6] < 0.002) and col_ink[x + 6 :].max() > 0.01:
            right_cut = x
            break

    top_cut = int(h * 0.012)
    bot_cut = int(h * 0.988)
    fill = (255, 255, 255)
    if left_cut > 0:
        arr_rgb.paste(fill, (0, 0, left_cut, h))
    if right_cut < w:
        arr_rgb.paste(fill, (right_cut, 0, w, h))
    if top_cut > 0:
        arr_rgb.paste(fill, (0, 0, w, top_cut))
    if bot_cut < h:
        arr_rgb.paste(fill, (0, bot_cut, w, h))
    return arr_rgb


def run_local_tesseract_dual(img: Image.Image) -> tuple[str, str]:
    """Run local Tesseract with both `kan` and `script/Kannada` models on the 250 DPI image."""
    if not shutil.which("tesseract"):
        return "", ""
    buf = io.BytesIO()
    img.convert("L").save(buf, format="PNG")
    png_bytes = buf.getvalue()

    results: list[str] = []
    for lang in ("kan", "script/Kannada"):
        try:
            proc = subprocess.run(
                ["tesseract", "stdin", "stdout", "-l", lang, "--psm", "6"],
                input=png_bytes,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0:
                results.append(proc.stdout.decode("utf-8", errors="replace").strip())
            else:
                results.append("")
        except Exception:  # noqa: BLE001
            results.append("")
    return results[0], results[1]


def encode_vlm_image_jpeg(img: Image.Image, max_dim: int = VLM_MAX_IMAGE_DIM) -> str:
    """Resize RGB image to fit within llama.cpp mtmd batch budget and return base64 JPEG."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        rgb = rgb.resize((int(round(w * scale)), int(round(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def clean_markdown_response(text: str) -> str:
    """Strip any <think>...</think> blocks or outer ```markdown code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    m = re.match(r"^```(?:markdown|md|text)?\s*\n(.*?)\n```\s*$", text, flags=re.DOTALL)
    if m:
        text = m.group(1).strip()
    return text.strip() + "\n"


def ocr_single_page(
    img_path: Path,
    host: str,
    api_key: str,
    model_id: str,
    quant_override: str | None = None,
    use_tesseract: bool = True,
) -> str:
    with Image.open(img_path) as raw_img:
        cleaned_img = crop_gutter_margins(raw_img)
        draft_kan, draft_script = (
            run_local_tesseract_dual(cleaned_img) if use_tesseract else ("", "")
        )
        b64_jpeg = encode_vlm_image_jpeg(cleaned_img)

    user_prompt = (
        "Transcribe this Kannada grammar book page into accurate, well-formatted UTF-8 Kannada Markdown.\n"
        "Output ONLY the final corrected Kannada Markdown for this page."
    )
    if draft_kan or draft_script:
        user_prompt += (
            "\n\n=== Pass-1 Draft A (Tesseract `kan`) ===\n"
            f"{draft_kan}\n"
            "\n=== Pass-1 Draft B (Tesseract `script/Kannada`) ===\n"
            f"{draft_script}\n"
            "===\n"
            "Carefully reconcile Draft A and Draft B with the page image to fix all glyph/ottakshara errors, "
            "restore `+` and `=` in grammar equations, and format any tables cleanly."
        )

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_jpeg}"},
                    },
                    {"type": "text", "text": user_prompt},
                ],
            },
        ],
        "temperature": 0.1,
        "top_p": 0.9,
        "max_tokens": 4096,
        "stream": False,
    }

    for attempt in range(2):
        try:
            resp = api_request(
                host,
                "/api/inference/chat/completions",
                api_key,
                method="POST",
                payload=payload,
                timeout=300.0,
            )
            choices = resp.get("choices") or []
            if not choices:
                raise RuntimeError(f"Empty choices in completion response: {resp}")
            content = choices[0].get("message", {}).get("content") or ""
            return clean_markdown_response(content)
        except Exception as exc:  # noqa: BLE001
            if attempt == 0 and ("500" in str(exc) or "upstream" in str(exc).lower()):
                print("  Reloading model after upstream error and retrying...", flush=True)
                ensure_model_loaded(host, api_key, model_id, quant_override, force_reload=True)
                continue
            raise
    raise RuntimeError("Failed after retry")


def parse_pages_spec(spec: str, total_pages: int) -> list[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = max(1, int(start_s))
            end = min(total_pages, int(end_s))
            pages.update(range(start, end + 1))
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p)
    return sorted(pages)


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
        help="Folder containing bw/*.webp images (default: current directory)",
    )
    p.add_argument("--host", type=str, default=os.environ.get("UNSLOTH_HOST", DEFAULT_HOST))
    p.add_argument("--api-key", type=str, default=os.environ.get("UNSLOTH_API_KEY", ""))
    p.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Unsloth vision model repo ID")
    p.add_argument("--quant", type=str, default=None, help="Optional GGUF quant variant override")
    p.add_argument("--pages", type=str, default=None, help="Page numbers/ranges, e.g. '10,15' or '1-20'")
    p.add_argument("--max-pages", type=int, default=None, help="Maximum number of pages to OCR")
    p.add_argument("--workers", type=int, default=2, help="Concurrent page requests (default: 2)")
    p.add_argument("--no-tesseract", action="store_true", help="Disable Pass-1 local Tesseract drafts")
    p.add_argument("--force", action="store_true", help="Overwrite existing ocr/NNNN.md files")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print("Error: --api-key or UNSLOTH_API_KEY environment variable is required.", file=sys.stderr)
        return 1

    base_dir = args.target.resolve()
    if base_dir.is_file():
        base_dir = base_dir.parent

    bw_dir = base_dir / "bw"
    full_dir = base_dir / "full"
    img_dir = bw_dir if bw_dir.is_dir() and any(bw_dir.glob("*.webp")) else full_dir
    if not img_dir.is_dir():
        print(f"Error: No bw/ or full/ page images found in {base_dir}. Run convert_pages.py first.", file=sys.stderr)
        return 1

    all_images = sorted(img_dir.glob("*.webp"))
    total_pages = len(all_images)
    if total_pages == 0:
        print(f"Error: No .webp images found in {img_dir}.", file=sys.stderr)
        return 1

    if args.pages:
        selected_nums = parse_pages_spec(args.pages, total_pages)
    else:
        selected_nums = list(range(1, total_pages + 1))

    if args.max_pages is not None:
        selected_nums = selected_nums[: args.max_pages]

    ocr_dir = base_dir / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)

    todo_nums = [
        p for p in selected_nums
        if args.force or not (ocr_dir / f"{p:04d}.md").is_file() or (ocr_dir / f"{p:04d}.md").stat().st_size == 0
    ]

    if not todo_nums:
        print(f"All {len(selected_nums)} requested page(s) already exist in {ocr_dir}. Use --force to re-run.")
        return 0

    model_id = ensure_model_loaded(args.host, args.api_key, args.model, args.quant)

    print(
        f"Running Kannada OCR on {len(todo_nums)} page(s) -> {ocr_dir}/NNNN.md "
        f"(model: {model_id}, workers: {args.workers}, dual_tesseract_anchor: {not args.no_tesseract})...",
        flush=True,
    )

    def _process_one(page_num: int) -> tuple[int, int, float, str | None]:
        img_path = img_dir / f"{page_num:04d}.webp"
        out_path = ocr_dir / f"{page_num:04d}.md"
        t0 = time.time()
        try:
            md_text = ocr_single_page(
                img_path=img_path,
                host=args.host,
                api_key=args.api_key,
                model_id=model_id,
                quant_override=args.quant,
                use_tesseract=not args.no_tesseract,
            )
            out_path.write_text(md_text, encoding="utf-8")
            return (page_num, len(md_text), time.time() - t0, None)
        except Exception as exc:  # noqa: BLE001
            return (page_num, 0, time.time() - t0, str(exc))

    errors = 0
    if args.workers <= 1 or len(todo_nums) == 1:
        for idx, page_num in enumerate(todo_nums, 1):
            pnum, nchars, dt, err = _process_one(page_num)
            if err:
                errors += 1
                print(f"[{idx}/{len(todo_nums)}] Page {pnum:04d} ERROR: {err}", file=sys.stderr, flush=True)
            else:
                print(f"[{idx}/{len(todo_nums)}] Page {pnum:04d} -> {pnum:04d}.md ({nchars} chars, {dt:.1f}s)", flush=True)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_process_one, p): p for p in todo_nums}
            for idx, fut in enumerate(concurrent.futures.as_completed(futs), 1):
                pnum, nchars, dt, err = fut.result()
                if err:
                    errors += 1
                    print(f"[{idx}/{len(todo_nums)}] Page {pnum:04d} ERROR: {err}", file=sys.stderr, flush=True)
                else:
                    print(f"[{idx}/{len(todo_nums)}] Page {pnum:04d} -> {pnum:04d}.md ({nchars} chars, {dt:.1f}s)", flush=True)

    print(
        f"Done! {len(todo_nums) - errors}/{len(todo_nums)} page(s) written to {ocr_dir}."
        + (f" ({errors} errors)" if errors else ""),
        flush=True,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
