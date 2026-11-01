# Changelog

## 2026-11-01
- Created `convert_pages.py` to convert `kannada-bala-vyakarana.pdf` into web-efficient WebP images (`thumb/`, `full/`, `bw/`) and built the gallery/page reader in `index.html`.
- Created `ocr_pages.py` to extract Kannada Markdown for all 116 pages into `ocr/0001.md`–`ocr/0116.md` using `Qwen2.5-VL-32B-Instruct-GGUF` on Unsloth Studio with local Tesseract line anchors.
- Created `build_latex.py` and generated the A5-sized LaTeX book `kbv.tex` (and compiled `kbv.pdf`) from `ocr/*.md`, using `coverpage.png` as the cover and preserving the original page numbers.
- Added `Makefile` to compile `kbv.tex` into `kbv.pdf` with `xelatex` and clean up intermediate TeX build files.
- Changed `kbv.tex` page dimensions to 5in x 7in and recompiled `kbv.pdf`.
- Reformatted page 116 in `kbv.tex` as the back cover page matching `full/0116.webp` (framed notice box, indented paragraphs, and bottom title/price footer) and exported `backcoverpage.png`.
- Recreated the front cover page in `kbv.tex` using native TikZ and TeX elements (full-bleed red canvas, horizontal rules, double-ring scalloped cloud badge, outlined Kannada display title, vector peacock publisher logo, and bottom sinusoidal wave ribbons).
- Changed chapter and section heading fonts in `build_latex.py` from Noto Serif Kannada (fake bold) to Noto Sans Kannada Bold; body text stays Noto Serif Kannada. Regenerated `kbv.tex` and `kbv.pdf`.
