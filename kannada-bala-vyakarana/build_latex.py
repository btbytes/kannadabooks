#!/usr/bin/env python3
"""Compose a 5in x 7in LaTeX document (kbv.tex) from ocr/*.md files, preserving
the original book's exact page numbers, layout, and typography across all 116 pages.
"""
from __future__ import annotations

import re
from pathlib import Path


SPECIAL_LATEX_MAP = str.maketrans({
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "[": r"{[}",
    "]": r"{]}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
})


# Canonical chapter titles by file_num to fix OCR character corruptions in headings
CANONICAL_CHAPTER_TITLES: dict[int, str] = {
    7: "ಪಾಠ ೧ : ವಿಷಯ ಪ್ರವೇಶ",
    9: "ಪಾಠ ೨ : ಅಕ್ಷರ ಮಾಲೆ",
    14: "ಪಾಠ ೩ : ನಾಮಪದ",
    16: "ಪಾಠ ೪ : ವಾಕ್ಯರಚನೆ",
    20: "ಪಾಠ ೫ : ಕ್ರಿಯಾಪದ",
    23: "ಪಾಠ ೬ : ಕನ್ನಡ ಸಂಧಿಗಳು",
    27: "ಪಾಠ ೭ : ಸಂಸ್ಕೃತ ಸಂಧಿಗಳು",
    35: "ಪಾಠ ೮ : ನಾಮಪದದ ವಿಭೇದಗಳು",
    41: "ಪಾಠ ೯ : ನಾಮಪದಗಳ ರೂಪ ಬದಲಾವಣೆ (i)",
    45: "ಪಾಠ ೧೦ : ನಾಮಪದಗಳ ರೂಪ ಬದಲಾವಣೆ (ii)",
    48: "ಪಾಠ ೧೧ : ನಾಮಪದಗಳ ರೂಪಬದಲಾವಣೆ (iii)",
    54: "ಪಾಠ ೧೨ : ಕ್ರಿಯಾಪದ-ಲಿಂಗ, ವಚನ, ಕಾಲ",
    64: "ಪಾಠ ೧೩ : ಸಮಾಸಗಳು",
    72: "ಪಾಠ ೧೪ : ಕೃದಂತಗಳು",
    77: "ಪಾಠ ೧೫ : ತದ್ಧಿತಾಂತಗಳು",
    81: "ಪಾಠ ೧೬ : ಅವ್ಯಯಗಳು",
    85: "ಪಾಠ ೧೭ : ದ್ವಿರುಕ್ತಿ",
    86: "ಪಾಠ ೧೮ : ತತ್ಸಮ-ತದ್ಭವ",
    87: "ಪಾಠ ೧೯ : ಲೇಖನ ಚಿಹ್ನೆಗಳು",
    92: "ಪಾಠ ೨೦ : ಅಲಂಕಾರಗಳು",
    99: "ಪಾಠ ೨೧ : ಛಂದಸ್ಸು",
    112: "೨೨. ದಿನಬಳಕೆಯ ಗಾದೆಗಳು",
}

CANONICAL_EXERCISE_TITLES: dict[int, str] = {
    7: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧",
    13: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೨",
    16: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೩",
    19: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೪",
    22: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೫",
    27: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೬",
    34: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೭",
    40: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೮",
    44: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೯",
    47: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೦",
    53: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೧",
    62: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೨",
    71: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೩",
    76: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೪",
    80: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೫",
    84: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೬",
    86: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೭",
    87: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೮",
    91: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧೯",
    97: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೨೦",
    109: "ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ : ೨೧",
}


def escape_latex_preserve_math(text: str) -> str:
    """Escape LaTeX special characters outside of inline $...$ math expressions."""
    text = text.replace("□", r"\ensuremath{\square}")
    text = text.replace("∵", r"\ensuremath{\because}")
    text = text.replace("×", r"\ensuremath{\times}")
    text = text.replace("«", "“").replace("»", "”")
    text = text.replace("║", "॥")

    token_re = re.compile(
        r"(\$[^$]+\$|\\ensuremath\{\\(?:square|because|times|smile)\})"
    )
    parts = token_re.split(text)
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(part)
        else:
            part = re.sub(r"[A-Za-z]+", lambda m: "\x00L" + m.group(0) + "\x00E", part)
            part = part.translate(SPECIAL_LATEX_MAP)
            out.append(part.replace("\x00L", r"{\kbvlatin ").replace("\x00E", "}"))
    return "".join(out)


def format_inline_markdown(text: str) -> str:
    """Convert inline **bold** and escape LaTeX characters."""
    pieces: list[str] = []
    last = 0
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        pieces.append(escape_latex_preserve_math(text[last : m.start()]))
        inner = escape_latex_preserve_math(m.group(1))
        pieces.append(rf"\textbf{{{inner}}}")
        last = m.end()
    pieces.append(escape_latex_preserve_math(text[last:]))
    res = "".join(pieces)
    res = res.replace("*", "")
    # Add comfortable spacing around + and = in inline grammar expressions
    res = re.sub(r"\s*\+\s*", " + ", res)
    res = re.sub(r"\s*=\s*", " = ", res)
    return res


def is_table_separator(line: str) -> bool:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    cells = [c.strip() for c in s.strip("|").split("|")]
    return bool(cells) and all(re.match(r"^:?-{2,}:?$", c) for c in cells if c != "")


def convert_markdown_table(table_lines: list[str], file_num: int) -> str:
    """Convert a GFM pipe table block into a LaTeX table matching the original book style."""
    rows: list[list[str]] = []
    header_idx: int | None = None

    for idx, raw in enumerate(table_lines):
        s = raw.strip()
        if is_table_separator(s):
            if idx == 1:
                header_idx = 0
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return ""

    max_cols = max(len(r) for r in rows)
    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

    keep_cols = [
        c
        for c in range(max_cols)
        if any(norm_rows[r][c].strip() for r in range(len(norm_rows)))
    ]
    if not keep_cols:
        return ""

    filtered_rows = [[r[c] for c in keep_cols] for r in norm_rows]
    num_cols = len(keep_cols)

    # Case 1: 6-column Tatsama-Tadbhava table on page 85 (0087.md) with vertical dividers between pairs
    if file_num == 87 and num_cols == 6:
        lines_out = [
            r"\vspace{5pt plus 4pt minus 1pt}",
            r"\begin{center}",
            r"{\renewcommand{\arraystretch}{1.22}\setlength{\tabcolsep}{5.5pt}",
            r"\begin{tabularx}{\textwidth}{X X | X X | X X}",
        ]
        for r_i, row in enumerate(filtered_rows):
            formatted_cells = [format_inline_markdown(c) for c in row]
            if r_i == 0:
                formatted_cells = [
                    rf"{{\kbvsecfont {c}}}" if c else "" for c in formatted_cells
                ]
                lines_out.append(" & ".join(formatted_cells) + r" \\[3pt]")
            else:
                lines_out.append(" & ".join(formatted_cells) + r" \\")
        lines_out.extend([
            r"\end{tabularx}}",
            r"\end{center}",
            r"\vspace{5pt plus 4pt minus 1pt}",
        ])
        return "\n".join(lines_out)

    # Case 2: Kagunita table on page 10 (0012.md) with vertical & horizontal rules
    if file_num == 12 and num_cols == 3:
        lines_out = [
            r"\vspace{5pt plus 4pt minus 1pt}",
            r"\begin{center}",
            r"{\renewcommand{\arraystretch}{1.20}\setlength{\tabcolsep}{10pt}",
            r"\begin{tabular}{c | c | l}",
            r"\toprule",
        ]
        for r_i, row in enumerate(filtered_rows):
            formatted_cells = [format_inline_markdown(c) for c in row]
            if r_i == 0:
                formatted_cells = [
                    rf"{{\kbvsecfont {c}}}" if c else "" for c in formatted_cells
                ]
                lines_out.append(" & ".join(formatted_cells) + r" \\")
                lines_out.append(r"\midrule")
            else:
                lines_out.append(" & ".join(formatted_cells) + r" \\")
        lines_out.extend([
            r"\bottomrule",
            r"\end{tabular}}",
            r"\end{center}",
            r"\vspace{5pt plus 4pt minus 1pt}",
        ])
        return "\n".join(lines_out)

    # Case 3: Chandas Vritta table on page 107 (0109.md) with horizontal rules between rows
    if file_num == 109 and num_cols >= 8:
        col_spec = "l " + " ".join(["c"] * (num_cols - 1))
        lines_out = [
            r"\vspace{5pt plus 4pt minus 1pt}",
            r"\noindent\begin{adjustbox}{max width=\textwidth}",
            r"{\renewcommand{\arraystretch}{1.30}\setlength{\tabcolsep}{4.5pt}",
            rf"\begin{{tabular}}{{{col_spec}}}",
            r"\toprule",
        ]
        for r_i, row in enumerate(filtered_rows):
            formatted_cells = [format_inline_markdown(c) for c in row]
            if r_i == 0:
                formatted_cells = [
                    rf"\textbf{{{c}}}" if c else "" for c in formatted_cells
                ]
                lines_out.append(" & ".join(formatted_cells) + r" \\")
                lines_out.append(r"\midrule")
            else:
                lines_out.append(" & ".join(formatted_cells) + r" \\")
                if r_i < len(filtered_rows) - 1:
                    lines_out.append(r"\hline")
        lines_out.extend([
            r"\bottomrule",
            r"\end{tabular}}",
            r"\end{adjustbox}",
            r"\vspace{6pt plus 4pt minus 1pt}",
        ])
        return "\n".join(lines_out)

    # Case 4: Sajatiya Ottakshara 5x5 grid on page 11 (0013.md)
    if file_num == 13 and num_cols == 5:
        lines_out = [
            r"\vspace{4pt plus 3pt minus 1pt}",
            r"\begin{center}",
            r"{\renewcommand{\arraystretch}{1.28}\setlength{\tabcolsep}{11pt}",
            r"\begin{tabular}{c c c c c}",
        ]
        for row in filtered_rows:
            formatted_cells = [format_inline_markdown(c) for c in row]
            lines_out.append(" & ".join(formatted_cells) + r" \\")
        lines_out.extend([
            r"\end{tabular}}",
            r"\end{center}",
            r"\vspace{2pt}",
        ])
        return "\n".join(lines_out)

    # Case 5: Two-column matching lists (e.g. 0008.md ಅ-ಪಟ್ಟಿ / ಬ-ಪಟ್ಟಿ, 0010.md ಕ-ವರ್ಗ, 0045.md ಏಕವಚನ/ಬಹುವಚನ)
    if num_cols == 2:
        has_dots = file_num in (8, 10)
        zebra = "" if has_dots or len(filtered_rows) < 3 else r"\rowcolors{2}{kbvrow}{white}"
        lines_out = [
            r"\vspace{5pt plus 4pt minus 1pt}",
            r"\begin{center}",
            r"{\renewcommand{\arraystretch}{1.24}\setlength{\tabcolsep}{10pt}" + zebra,
            r"\begin{tabular}{l c l}" if has_dots else r"\begin{tabularx}{0.88\textwidth}{X X}",
        ]
        for r_i, row in enumerate(filtered_rows):
            c0 = format_inline_markdown(row[0])
            c1 = format_inline_markdown(row[1])
            if r_i == 0 and header_idx == 0 and file_num != 10:
                if has_dots:
                    lines_out.append(rf"\textbf{{{c0}}} & \hspace{{12mm}} & \textbf{{{c1}}} \\[3pt]")
                else:
                    lines_out.append(rf"{{\kbvsecfont\color{{kbvaccentdark}}{c0}}} & {{\kbvsecfont\color{{kbvaccentdark}}{c1}}} \\[1pt]")
                    lines_out.append(r"\arrayrulecolor{kbvline}\specialrule{0.5pt}{0pt}{2pt}\arrayrulecolor{black}")
            else:
                if has_dots:
                    lines_out.append(rf"{c0} & \ldots\ldots & {c1} \\")
                else:
                    lines_out.append(rf"{c0} & {c1} \\")
        lines_out.extend([
            r"\end{tabular}}" if has_dots else r"\end{tabularx}}",
            r"\end{center}",
            r"\vspace{5pt plus 4pt minus 1pt}",
        ])
        return "\n".join(lines_out)

    # Case 6: General borderless multi-column word/inflection grids (utilizing full horizontal width)
    col_spec = " ".join(["X"] * num_cols)
    # Check if first row is actually data rather than a column header (e.g., word grids on 0014.md, 0072.md, 0080.md, 0052.md, 0107.md)
    real_header = (
        header_idx == 0
        and file_num not in (14, 27, 66, 72, 74, 80, 107)
        and not (file_num == 52 and filtered_rows[0][0].startswith("ತೃ"))
    )
    zebra = r"\rowcolors{2}{kbvrow}{white}" if real_header and len(filtered_rows) >= 4 else (
        r"\rowcolors{1}{kbvrow}{white}" if len(filtered_rows) >= 4 else ""
    )
    lines_out = [
        r"\vspace{5pt plus 4pt minus 1pt}",
        r"\noindent{\renewcommand{\arraystretch}{1.24}\setlength{\tabcolsep}{4pt}" + zebra,
        rf"\begin{{tabularx}}{{\textwidth}}{{{col_spec}}}",
    ]
    for r_i, row in enumerate(filtered_rows):
        formatted_cells = [format_inline_markdown(c) for c in row]
        if r_i == 0 and real_header:
            formatted_cells = [
                rf"{{\kbvsecfont\color{{kbvaccentdark}}{c}}}" if c else "" for c in formatted_cells
            ]
            lines_out.append(" & ".join(formatted_cells) + r" \\[1pt]")
            lines_out.append(r"\arrayrulecolor{kbvline}\specialrule{0.5pt}{0pt}{2pt}\arrayrulecolor{black}")
        else:
            lines_out.append(" & ".join(formatted_cells) + r" \\")
    lines_out.extend([
        r"\end{tabularx}}",
        r"\vspace{5pt plus 4pt minus 1pt}",
    ])
    return "\n".join(lines_out)


def running_chapter_name(file_num: int) -> str:
    """Short chapter name for the running header: latest chapter starting at or before this page."""
    starts = [k for k in CANONICAL_CHAPTER_TITLES if k <= file_num]
    if not starts:
        return ""
    title = CANONICAL_CHAPTER_TITLES[max(starts)]
    name = title.split(" : ", 1)[1] if " : " in title else re.sub(r"^[೦-೯0-9]+\.\s*", "", title)
    return format_inline_markdown(name)


def strip_leading_page_number(lines: list[str]) -> list[str]:
    """Remove standalone printed page number line at the top of OCR markdown."""
    out = list(lines)
    while out and not out[0].strip():
        out.pop(0)
    if not out:
        return out

    first = out[0].strip().strip("|").strip()
    if re.match(r"^[0-9೦-೯]{1,3}\]?$", first) or re.match(r"^7\]\s*97$", first):
        out.pop(0)
        while out and not out[0].strip():
            out.pop(0)
    return out


def clean_ocr_line(line: str, file_num: int) -> str:
    """Clean stray scanner pipe artifacts while preserving poetic dandas on verse pages."""
    s = line.strip()
    if re.fullmatch(r"[`\"“”'\s]+", s):
        return ""
    if s.startswith("|") and s.endswith("|") and s.count("|") >= 3:
        return s

    # On Alankara & Chandas pages (92..111), convert trailing | and || on verse lines to dandas
    if 92 <= file_num <= 111 and not s.startswith("|"):
        if re.search(r"\|\|\s*$", s):
            s = re.sub(r"\s*\|\|\s*$", " ॥", s)
        elif re.search(r"\|\s*$", s):
            s = re.sub(r"\s*\|\s*$", " ।", s)

    # Strip stray leading or trailing pipes from scanner margins
    s = re.sub(r"^\|\s*", "", s)
    s = re.sub(r"\s*(?:\|\s*)+[ಮ]*\s*$", "", s)
    # Clean stray leading underscore/dot scanner noise
    s = re.sub(r"^[_.\s]+(?=[ಕ-ಹಅ-ಔ])", "", s)
    return s.strip()


def is_chapter_heading(s: str, file_num: int) -> str | None:
    """Return canonical chapter heading if line is a chapter title."""
    plain = s.lstrip("#").strip().strip("*").strip()
    if file_num == 112 and "ದಿನಬಳಕೆಯ ಗಾದೆಗಳು" in plain:
        return CANONICAL_CHAPTER_TITLES[112]
    if re.match(r"^[ಪವಸಹ]ಾ[ಠರಧ]ೆ?\s*[೦-೯0-9ಆ೭%]+", plain):
        return CANONICAL_CHAPTER_TITLES.get(file_num, plain)
    return None


def is_exercise_heading(s: str, file_num: int) -> str | None:
    """Return canonical exercise heading if line is an ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ header."""
    plain = s.lstrip("#").strip().strip("|").strip().strip("*").strip()
    if re.match(r"^ಅಭ[್ಯಾಣ]+ಸ\s+[ಪಸ]ಂ?[ತ್ರ್ಶ]+ರ?ಿಕೆ", plain):
        return CANONICAL_EXERCISE_TITLES.get(file_num, plain.rstrip("."))
    return None


def is_standalone_line(s: str, file_num: int) -> bool:
    """Determine if a line starts a new structural item or must remain on its own line."""
    if not s:
        return True
    if file_num >= 112:
        return True  # Proverbs on pages 110-112: 1 proverb per line
    if is_chapter_heading(s, file_num) or is_exercise_heading(s, file_num):
        return True
    if s.startswith("#"):
        return True
    # Centered dash subtitles like — ಲಿಂಗ — or —ಕ್ರಿಯಾಪದ ಪ್ರಕರಣ ನೋಡಿ—
    if re.match(r"^[—\-]+\s*.+\s*[—\-]+$", s):
        return True
    # Poetic source attributions starting with —
    if re.match(r"^[—\-]\s*[^—]+$", s) and len(s) < 60:
        return True
    # Square bullet □ or bullet -
    if s.startswith("□") or re.match(r"^[-•]\s+", s):
        return True
    # Numbered or lettered items: (1), [1], 1., (೧), ೧., [ಅ], (ಅ)
    if re.match(
        r"^(\([0-9೦-೯ಅ-ಔಕ-ಳ]+\)|\[[0-9೦-೯ಅ-ಔಕ-ಳ]+\]|[0-9೦-೯]{1,2}[.)])\s+",
        s,
    ):
        return True
    # Label keywords at start of line
    if re.match(
        r"^(ಉದಾಹರಣೆಗೆ|ಉದಾಹರಣೆ|ಉದಾ|ವ್ಯಾಖ್ಯೆ|ಸೂತ್ರ|ವಿವರಣೆ|ವಿ\.ಸೂ\.|ವಿನ್ಯಾಸ|ಗಮನಿಸಿ)\s*[:;-]",
        s,
    ):
        return True
    # Equations or grammar breakdown lines containing = or + or ×
    if "=" in s or " + " in s or "+" in s or "×" in s:
        return True
    # Word chains with -- or — (e.g. ಕಬ್ಬು--ರಸ--ಸಿಹಿ)
    if "--" in s and len(s) < 55:
        return True
    # Verse lines ending with । or ॥
    if s.endswith("।") or s.endswith("॥"):
        return True
    # Short standalone section titles ending with :
    if s.endswith(":") and len(s) < 52:
        return True
    return False


def format_equation_or_pair_block(lines: list[str]) -> str:
    """Format consecutive equation/derivation lines (with = or × or semicolon-separated columns)
    using horizontal alignment across the page.
    """
    return "\\begin{kbvderiv}\n" + _format_equation_or_pair_block_inner(lines) + "\n\\end{kbvderiv}"


def _split_result(rhs: str) -> str:
    """Highlight the derived word; keep trailing notes like (ಲೋಪ ಸಂಧಿ) or [∵ ...] in grey."""
    if "+" in rhs:
        return rhs
    m = re.match(r"^(.*?)(\s*(?:\.{2,}|\(|\[|\{\[\}|\\ldots).*)$", rhs)
    if m and m.group(1).strip():
        return rf"\kbvresult{{{m.group(1).strip()}}}{{\color{{kbvgrey}}{m.group(2)}}}"
    return rf"\kbvresult{{{rhs}}}"


def _format_equation_or_pair_block_inner(lines: list[str]) -> str:
    # 1. Semicolon-separated multi-column rows (e.g. ಹಸಿರು + ಎಲೆ ; ಹಣೆ + ಕಣ್ಣು ; ಕೆಂಪು + ತುಟಿ)
    if all(";" in l for l in lines) and len(lines) >= 2:
        split_rows = [[c.strip() for c in l.split(";") if c.strip()] for l in lines]
        max_c = max(len(r) for r in split_rows)
        if 2 <= max_c <= 4:
            col_spec = " ".join(["X"] * max_c)
            out = [
                r"\vspace{4pt plus 3pt minus 1pt}",
                r"\noindent{\renewcommand{\arraystretch}{1.24}\setlength{\tabcolsep}{5pt}",
                rf"\begin{{tabularx}}{{\textwidth}}{{{col_spec}}}",
            ]
            for r in split_rows:
                padded = r + [""] * (max_c - len(r))
                cells = [format_inline_markdown(c) for c in padded]
                out.append(" & ".join(cells) + r" \\")
            out.extend([
                r"\end{tabularx}}",
                r"\vspace{4pt plus 3pt minus 1pt}",
            ])
            return "\n".join(out)

    # 2. Equations of the form LHS = RHS (with optional + on LHS or RHS)
    if len(lines) >= 2 and all("=" in l and ";" not in l and len(l) < 75 for l in lines):
        out = [
            r"\vspace{4pt plus 3pt minus 1pt}",
            r"\begin{center}\begin{adjustbox}{max width=\textwidth}",
            r"{\renewcommand{\arraystretch}{1.22}\setlength{\tabcolsep}{4pt}",
            r"\begin{tabular}{l c l}",
        ]
        for l in lines:
            clean_l = re.sub(r"^[-•]\s*", "", l.strip())
            parts = clean_l.split("=", 1)
            lhs = format_inline_markdown(parts[0].strip())
            rhs = _split_result(format_inline_markdown(parts[1].strip()))
            out.append(rf"{lhs} & {{\color{{kbvgrey}}$=$}} & {rhs} \\")
        out.extend([
            r"\end{tabular}}",
            r"\end{adjustbox}\end{center}",
            r"\vspace{4pt plus 3pt minus 1pt}",
        ])
        return "\n".join(out)

    # 3. Opposition pairs with × (e.g. ಗುಣವಂತ × ಗುಣವಂತೆ ... (ಗುಣವಂತ + ಎ))
    if len(lines) >= 2 and all("×" in l and len(l) < 75 for l in lines):
        out = [
            r"\vspace{4pt plus 3pt minus 1pt}",
            r"\begin{center}\begin{adjustbox}{max width=\textwidth}",
            r"{\renewcommand{\arraystretch}{1.22}\setlength{\tabcolsep}{5pt}",
            r"\begin{tabular}{l c l l}",
        ]
        for l in lines:
            clean_l = re.sub(r"^[-•]\s*", "", l.strip())
            lhs, rhs_full = clean_l.split("×", 1)
            if "(" in rhs_full:
                r1, r2 = rhs_full.split("(", 1)
                r1_Clean = re.sub(r"\.+", "", r1).strip()
                out.append(
                    rf"{format_inline_markdown(lhs.strip())} & $\times$ & {format_inline_markdown(r1_Clean)} & \ldots\ ({format_inline_markdown(r2.strip())} \\"
                )
            else:
                out.append(
                    rf"{format_inline_markdown(lhs.strip())} & $\times$ & {format_inline_markdown(rhs_full.strip())} & \\"
                )
        out.extend([
            r"\end{tabular}}",
            r"\end{adjustbox}\end{center}",
            r"\vspace{4pt plus 3pt minus 1pt}",
        ])
        return "\n".join(out)

    # Fallback: indented line-by-line display block
    formatted = [r"\hspace*{1.8em}" + format_inline_markdown(l) for l in lines]
    return (
        r"\vspace{3pt plus 3pt minus 1pt}" + "\n"
        + " \\\\\n".join(formatted)
        + "\n" + r"\vspace{3pt plus 3pt minus 1pt}"
    )


def render_special_page_3() -> str:
    """Render 0003.md (Inner Title Page) matching full/0003.webp layout and style."""
    return r"""% === File 0003.md: Inner Title Page (matching full/0003.webp) ===
\thispagestyle{empty}
\vbox to 0.96\textheight{%
  \vspace*{12mm}
  \begin{center}
    {\kbvchapfont\fontsize{25pt}{30pt}\selectfont ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ}
  \end{center}
  \vfill
  \begin{center}
    \begin{tikzpicture}
      \node[
        inner xsep=7mm,
        inner ysep=5.5mm,
        text width=82mm,
        align=center
      ] (tbox) {%
        \linespread{1.32}\fontsize{11.5pt}{15.5pt}\selectfont
        ಪ್ರಾಥಮಿಕ ಶಾಲೆಯ ಮತ್ತು ಪ್ರೌಢ ಶಾಲೆಯ\\
        ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಹೆಚ್ಚು ಉಪಯುಕ್ತವಾದ\\
        ಸರಳ ವ್ಯಾಕರಣ ಪಠ್ಯ ಪುಸ್ತಕ%
      };
      % Letterpress-style border rules with slight corner gaps matching full/0003.webp
      \draw[line width=0.9pt] ([xshift=1.2mm]tbox.north west) -- ([xshift=-1.2mm]tbox.north east);
      \draw[line width=0.9pt] ([xshift=1.2mm]tbox.south west) -- ([xshift=-1.2mm]tbox.south east);
      \draw[line width=0.9pt] ([yshift=-1.2mm]tbox.north west) -- ([yshift=1.2mm]tbox.south west);
      \draw[line width=0.9pt] ([yshift=-1.2mm]tbox.north east) -- ([yshift=1.2mm]tbox.south east);
    \end{tikzpicture}
  \end{center}
  \vspace{6mm}
  \begin{center}
    {\kbvsecfont\fontsize{13pt}{17pt}\selectfont ಕೆ. ಆರ್. ಕೆ. ಮೂರ್ತಿ}\\[3.5pt]
    {\fontsize{11pt}{15pt}\selectfont {[}ನಿವೃತ್ತ ಪ್ರೌಢಶಾಲಾ ಶಿಕ್ಷಕ{]}}
  \end{center}
  \vfill
  \noindent\rule{\textwidth}{0.95pt}\par
  \vspace{2.5mm}
  \begin{center}
    {\kbvchapfont\fontsize{14.5pt}{18pt}\selectfont ವಾಹಿನಿ ಪ್ರಕಾಶನ : : ಬೆಂಗಳೂರು-22}
  \end{center}
  \vspace{1.5mm}
  \noindent\rule{\textwidth}{0.95pt}\par
  \vspace*{4mm}
}
\clearpage
"""


def render_special_page_4() -> str:
    """Render 0004.md (Imprint / Copyright Page) matching full/0004.webp layout and style."""
    return r"""% === File 0004.md: Copyright & Imprint Page (matching full/0004.webp) ===
\thispagestyle{empty}
\vbox to 0.96\textheight{%
  \vspace*{16mm}
  \noindent\hspace*{5mm}{\fontsize{11.5pt}{15.5pt}\selectfont ಈ ಗ್ರಂಥದ ಸ್ವಾಮ್ಯ ಲೇಖಕರಿಗೆ ಸೇರಿದ್ದು}\par
  \vspace{28mm}
  \noindent\hspace*{5mm}{\fontsize{11pt}{15pt}\selectfont ಪ್ರತಿಗಳ ಅಧಿಕೃತ ಮಾರಾಟಗಾರರು :}\\[4pt]
  \hspace*{13mm}{\kbvsecfont\fontsize{11.5pt}{15.5pt}\selectfont ಚಾಮುಂಡಿ ಸ್ಟೋರ್ಸ್}\\[2.5pt]
  \hspace*{13mm}{\fontsize{11pt}{15pt}\selectfont ಪುಸ್ತಕ ವ್ಯಾಪಾರಿಗಳು,}\\[2.5pt]
  \hspace*{13mm}{\fontsize{11pt}{15pt}\selectfont ಯಶವಂತಪುರ, ಬೆಂಗಳೂರು-560 022.}\par
  \vfill
  \noindent\hspace*{5mm}{\fontsize{11pt}{15pt}\selectfont ಮುದ್ರಣ :}\\[4pt]
  \hspace*{13mm}{\kbvsecfont\fontsize{11.5pt}{15.5pt}\selectfont ಪದ್ಮ ಪ್ರಿಂಟಿಂಗ್ ಪ್ರೆಸ್}\\[2.5pt]
  \hspace*{13mm}{\fontsize{11pt}{15pt}\selectfont ಬಳೇಪೇಟೆ, ಬೆಂಗಳೂರು-53.}\par
  \vspace*{6mm}
}
\clearpage
"""


def render_special_page_5() -> str:
    """Render 0005.md (Table of Contents) matching full/0005.webp layout and style."""
    toc_items = [
        ("೧.", "ವಿಷಯ ಪ್ರವೇಶ", "5"),
        ("೨.", "ಅಕ್ಷರ ಮಾಲೆ", "7"),
        ("೩.", "ನಾಮಪದ", "12"),
        ("೪.", "ವಾಕ್ಯರಚನೆ", "14"),
        ("೫.", "ಕ್ರಿಯಾಪದ", "18"),
        ("೬.", "ಕನ್ನಡ ಸಂಧಿಗಳು", "21"),
        ("೭.", "ಸಂಸ್ಕೃತ ಸಂಧಿಗಳು", "25"),
        ("೮.", "ನಾಮಪದದ ವಿಭೇದಗಳು", "33"),
        ("೯.", "ನಾಮಪದಗಳ ರೂಪ ಬದಲಾವಣೆ (i)", "39"),
        ("೧೦.", "ನಾಮಪದಗಳ ರೂಪ ಬದಲಾವಣೆ (ii)", "43"),
        ("೧೧.", "ನಾಮಪದಗಳ ರೂಪ ಬದಲಾವಣೆ (iii)", "46"),
        ("೧೨.", "ಕ್ರಿಯಾಪದ : ಲಿಂಗ, ವಚನ, ಕಾಲ", "52"),
        ("೧೩.", "ಸಮಾಸಗಳು", "62"),
        ("೧೪.", "ಕೃದಂತಗಳು", "70"),
        ("೧೫.", "ತದ್ಧಿತಾಂತಗಳು", "75"),
        ("೧೬.", "ಅವ್ಯಯಗಳು", "79"),
        ("೧೭.", "ದ್ವಿರುಕ್ತಿ", "83"),
        ("೧೮.", "ತತ್ಸಮ-ತದ್ಭವ", "84"),
        ("೧೯.", "ಲೇಖನ ಚಿಹ್ನೆಗಳು", "85"),
        ("೨೦.", "ಅಲಂಕಾರಗಳು", "90"),
        ("೨೧.", "ಛಂದಸ್ಸು", "97"),
    ]
    rows_tex = "\n".join(
        rf"    {{\kbvsecfont\color{{kbvaccent}}{num}}} & {format_inline_markdown(title)} & {{\color{{kbvgrey}}\ldots\ldots}} & {{\kbvsecfont {pg}}} \\"
        for num, title, pg in toc_items
    )
    return rf"""% === File 0005.md: Table of Contents (matching full/0005.webp) ===
\thispagestyle{{empty}}
\vbox to 0.96\textheight{{%
  \vspace*{{2mm}}
  \begin{{center}}
    {{\kbvchapfont\fontsize{{18pt}}{{22pt}}\selectfont ವಿಷಯಾನುಕ್ರಮಣಿಕೆ}}\\[3pt]
    {{\color{{kbvline}}\rule{{48mm}}{{0.5pt}}}}
  \end{{center}}
  \vspace{{3mm}}
  \noindent\hspace*{{6mm}}{{\kbvsecfont\fontsize{{11pt}}{{14pt}}\selectfont ಪ್ರಕರಣ}}\hfill{{\kbvsecfont\fontsize{{11pt}}{{14pt}}\selectfont ಪುಟ ಸಂಖ್ಯೆ}}\par
  \vspace{{1.5mm}}
  \noindent{{\renewcommand{{\arraystretch}}{{1.20}}\setlength{{\tabcolsep}}{{4pt}}%
  \begin{{tabularx}}{{\textwidth}}{{r X c r}}
{rows_tex}
  \end{{tabularx}}}}\par
  \vfill
  \begin{{center}}
    {{\color{{kbvline}}\rule{{28mm}}{{0.5pt}}}}
  \end{{center}}
  \vspace*{{2mm}}
}}
\clearpage
"""


def render_special_page_105() -> str:
    """Body for 0105.md (printed page 103): the ಷಟ್ಪದಿಗಳ ಲಕ್ಷಣಗಳು table, upright across the full text width."""
    rows = [
        ("೧.", "ಶರ ಷಟ್ಪದಿ", "ಪ್ರತಿ ಪಾದದಲ್ಲಿ ನಾಲ್ಕು ಮಾತ್ರೆಯ ಎರಡು ಗಣಗಳಿರುವುವು.",
         "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 4 ಮಾತ್ರೆಯ 3 ಗಣಗಳು ಮತ್ತು ಮೇಲೊಂದು ಗುರು ಇರುವುದು.",
         r"“$\smile - \smile$” ಈ ರೀತಿಯ ಗಣ ಬರುವುದಿಲ್ಲ."),
        ("೨.", "ಕುಸುಮ ಷಟ್ಪದಿ", "ಪ್ರತಿ ಪಾದದಲ್ಲಿ ಐದು ಮಾತ್ರೆಯ ಎರಡು ಗಣಗಳಿರುವುವು.",
         "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 5 ಮಾತ್ರೆಯ 3 ಗಣಗಳು ಮತ್ತು ಮೇಲೊಂದು ಗುರು ಇರುವುದು.",
         r"“$\smile - \smile\smile$” ಮತ್ತು “$\smile - -$” ರೀತಿಯ ಗಣವಿರುವುದಿಲ್ಲ."),
        ("೩.", "ಭೋಗ ಷಟ್ಪದಿ", "ಪ್ರತಿ ಪಾದದಲ್ಲಿ ಮೂರು ಮಾತ್ರೆಯ ನಾಲ್ಕು ಗಣಗಳಿರುವುವು.",
         "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 3 ಮಾತ್ರೆಯ 6 ಗಣಗಳಿರುವುವು ಮತ್ತು ಮೇಲೊಂದು ಗುರುವಿರುವುದು.",
         r"“$\smile -$” ಈ ರೀತಿಯ ಗಣಗಳಿರುವುದಿಲ್ಲ."),
        ("೪.", "ಭಾಮಿನೀ ಷಟ್ಪದಿ", "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 3 ಮತ್ತು 4 ಮಾತ್ರೆಯ 4 ಗಣಗಳು ಪರ್ಯಾಯವಾಗಿ ಬರುವುವು.",
         "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 3 ಮತ್ತು 4 ಮಾತ್ರೆಯ 6 ಗಣಗಳು ಪರ್ಯಾಯವಾಗಿ ಬರುವುವು ಮತ್ತು ಮೇಲೊಂದು ಗುರುವಿರುವುದು.",
         r"“$\smile - \smile$” ಈ ರೀತಿಯ ಗಣವಿರುವುದಿಲ್ಲ."),
        ("೫.", "ಪರಿವರ್ಧಿನೀ ಷಟ್ಪದಿ", "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 4 ಮಾತ್ರೆಯ 4 ಗಣಗಳಿರುವುವು.",
         "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 4 ಮಾತ್ರೆಯ 6 ಗಣಗಳಿರುವುವು ಮತ್ತು ಮೇಲೊಂದು ಗುರುವಿರುವುದು.",
         r"“$\smile - \smile$” ಈ ರೀತಿಯ ಗಣವಿರುವುದಿಲ್ಲ."),
        ("೬.", "ವಾರ್ಧಕ ಷಟ್ಪದಿ", "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 5 ಮಾತ್ರೆಯ 4 ಗಣಗಳಿರುವುವು.",
         "ಪ್ರತಿ ಪಾದದಲ್ಲಿ 5 ಮಾತ್ರೆಯ 6 ಗಣಗಳು ಮತ್ತು ಮೇಲೊಂದು ಗುರು ಇರುವುದು.",
         r"{\color{kbvgrey}\ldots\ldots}"),
    ]
    header = [r"{\kbvsecfont ಷಟ್ಪದಿ}", r"{\kbvsecfont ೧, ೨, ೪, ೫ ನೆಯ ಪಾದಗಳು}",
              r"{\kbvsecfont ೩ ಮತ್ತು ೬ ನೆಯ ಪಾದಗಳು}", r"{\kbvsecfont ವಿಶೇಷ ವಿಚಾರ}"]
    row_tex = [rf"      {{\kbvsecfont {num}}}\,{name} & {c1} & {c2} & {note}" for num, name, c1, c2, note in rows]
    body_rows = (r" \\" + "\n" + r"      \specialrule{0.3pt}{2.5pt}{2.5pt}" + "\n").join(row_tex)
    return (
        r"""% === File 0105.md (Printed Page 103: ಷಟ್ಪದಿಗಳ ಲಕ್ಷಣಗಳು, full-width upright table) ===
\par\vspace{6pt plus 4pt}\noindent\begin{minipage}{\textwidth}% keep title and table together
\begin{center}{\kbvchapfont\fontsize{14pt}{18pt}\selectfont ಷಟ್ಪದಿಗಳ ಲಕ್ಷಣಗಳು}\end{center}
\vspace{4pt plus 3pt minus 1pt}
\noindent{\fontsize{8.8pt}{11pt}\selectfont\renewcommand{\arraystretch}{1.05}\setlength{\tabcolsep}{3pt}\arrayrulecolor{kbvline}%
\setlength{\kbvcolw}{\dimexpr(\textwidth-17mm-21mm-6\tabcolsep)/2\relax}%
\begin{tabular}{@{} >{\raggedright\arraybackslash}p{17mm} >{\raggedright\arraybackslash}p{\kbvcolw} >{\raggedright\arraybackslash}p{\kbvcolw} >{\raggedright\arraybackslash}p{21mm} @{}}
      \specialrule{0.5pt}{0pt}{3pt}
      """ + " & ".join(header) + r""" \\
      \specialrule{0.5pt}{3pt}{3pt}
""" + body_rows + r""" \\
      \specialrule{0.5pt}{3pt}{0pt}
\end{tabular}\arrayrulecolor{black}}
\end{minipage}\par\vspace{6pt plus 4pt}
"""
    )


def markdown_page_to_latex(md_text: str, file_num: int) -> str:
    return "\n\n".join(markdown_page_to_blocks(md_text, file_num))


def markdown_page_to_blocks(md_text: str, file_num: int) -> list[str]:
    raw_lines = md_text.splitlines()
    lines = strip_leading_page_number(raw_lines)
    if not lines:
        return []

    i = 0
    n = len(lines)
    blocks: list[str] = []

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        # 1. Check for Markdown pipe table
        if (
            "|" in stripped
            and not (92 <= file_num <= 114 and not stripped.startswith("|"))
            and i + 1 < n
            and (is_table_separator(lines[i + 1]) or lines[i + 1].strip().startswith("|"))
        ):
            t_lines: list[str] = []
            j = i
            while j < n and "|" in lines[j] and (
                lines[j].strip().startswith("|") or is_table_separator(lines[j])
            ):
                t_lines.append(lines[j])
                j += 1
            if len(t_lines) >= 2:
                # Single-column pipe box (like on 0027.md): treat inner lines as normal semicolon rows
                cells_per_row = [
                    len([c for c in tl.strip().strip("|").split("|") if c.strip()])
                    for tl in t_lines
                    if not is_table_separator(tl)
                ]
                if cells_per_row and max(cells_per_row) == 1:
                    inner_rows = [
                        tl.strip().strip("|").strip()
                        for tl in t_lines
                        if not is_table_separator(tl)
                    ]
                    if len(inner_rows) == 1 and is_exercise_heading(inner_rows[0], file_num):
                        ex_title = is_exercise_heading(inner_rows[0], file_num)
                        blocks.append(rf"\kbvexercise{{{format_inline_markdown(ex_title)}}}")
                    else:
                        blocks.append(format_equation_or_pair_block(inner_rows))
                else:
                    blocks.append(convert_markdown_table(t_lines, file_num))
                i = j
                continue

        cleaned = clean_ocr_line(raw, file_num)
        if not cleaned:
            i += 1
            continue

        # 2. Book Title on Page 5 (0007.md)
        if file_num == 7 and cleaned.startswith("# ") and "ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ" in cleaned:
            blocks.append(
                r"\vspace{2pt plus 2pt}"
                r"\begin{center}{\kbvchapfont\fontsize{20pt}{24pt}\selectfont ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ}\end{center}"
                r"\vspace{4pt plus 4pt minus 1pt}"
            )
            i += 1
            continue

        # 3. Chapter Heading (ಪಾಠ ೧ .. ಪಾಠ ೨೧, ೨೨. ದಿನಬಳಕೆಯ ಗಾದೆಗಳು)
        chap_title = is_chapter_heading(cleaned, file_num)
        if chap_title:
            if " : " in chap_title:
                c_num, c_name = chap_title.split(" : ", 1)
                blocks.append(rf"\kbvchapter{{{format_inline_markdown(c_num)}}}{{{format_inline_markdown(c_name)}}}")
            else:
                m_c = re.match(r"^([೦-೯0-9]+)\.\s*(.+)$", chap_title)
                if m_c:
                    blocks.append(rf"\kbvchapter{{ಪಾಠ {m_c.group(1)}}}{{{format_inline_markdown(m_c.group(2))}}}")
                else:
                    blocks.append(rf"\kbvchapterplain{{{format_inline_markdown(chap_title)}}}")
            i += 1
            continue

        # 4. Exercise Heading (ಅಭ್ಯಾಸ ಪತ್ರಿಕೆ ೧ .. ೨೧)
        ex_title = is_exercise_heading(cleaned, file_num)
        if ex_title:
            blocks.append(rf"\kbvexercise{{{format_inline_markdown(ex_title)}}}")
            i += 1
            continue

        # 5. Centered Dash Subtitles (e.g. — ಲಿಂಗ —, — ವಚನ —, — ವಿಭಕ್ತಿ ಪ್ರತ್ಯಯಗಳು —)
        if re.match(r"^[—\-]+\s*.+\s*[—\-]+$", cleaned):
            title_tex = format_inline_markdown(cleaned.strip("—- "))
            if 92 <= file_num <= 111 and blocks and blocks[-1].startswith("\\begin{kbvverse}"):
                blocks.append(
                    rf"\noindent\hfill{{\fontsize{{9.5pt}}{{12.5pt}}\selectfont\color{{kbvgrey}}— {title_tex}}}\par\vspace{{3pt plus 2pt}}"
                )
            else:
                blocks.append(rf"\kbvsubtitle{{{title_tex}}}")
            i += 1
            continue

        # 6. Explicit Markdown Headings (## / ### / ####)
        m_head = re.match(r"^(#{1,4})\s+(.+)$", cleaned)
        if m_head:
            level = len(m_head.group(1))
            h_text = m_head.group(2).strip()
            title_tex = format_inline_markdown(h_text)
            if level <= 2 or h_text in ("ಕನ್ನಡ ಸಂಧಿಗಳು",):
                blocks.append(
                    r"\vspace{6pt plus 5pt minus 1pt}"
                    rf"\begin{{center}}{{\kbvsecfont\fontsize{{12.5pt}}{{16pt}}\selectfont\color{{kbvaccentdark}} {title_tex}}}\end{{center}}"
                    r"\vspace{3pt plus 3pt minus 1pt}"
                )
            else:
                blocks.append(rf"\kbvsechead{{{title_tex}}}")
            i += 1
            continue

        # 7. Centered numbered major section headings like "1. ಅರ್ಥಾಲಂಕಾರ" or "2. ಶಬ್ದಾಲಂಕಾರ"
        if re.match(r"^[12]\.\s+(ಅರ್ಥಾಲಂಕಾರ|ಶಬ್ದಾಲಂಕಾರ)$", cleaned):
            title_tex = format_inline_markdown(cleaned)
            blocks.append(
                r"\vspace{7pt plus 6pt minus 1pt}"
                rf"\begin{{center}}{{\kbvsecfont\fontsize{{13pt}}{{16.5pt}}\selectfont\color{{kbvaccentdark}} {title_tex}}}\end{{center}}"
                r"\vspace{3pt plus 3pt minus 1pt}"
            )
            i += 1
            continue

        # 8. Special Kannada Alphabet Chart on Page 7 (0009.md)
        if file_num == 9 and cleaned.startswith("ಅ ಆ ಇ ಈ"):
            chart_lines: list[str] = []
            while i < n:
                cl = clean_ocr_line(lines[i], file_num)
                if not cl or cl.startswith("□"):
                    break
                # Space out aksharas horizontally
                spaced = r"\hspace{0.55em}".join(cl.split())
                chart_lines.append(format_inline_markdown(spaced).replace(r"\textbackslash{}hspace\{0.55em\}", r"\hspace{0.55em}"))
                i += 1
            # Re-format cleanly with \hspace{0.55em} between tokens
            clean_chart_rows = []
            for idx_c in range(i - len(chart_lines), i):
                raw_tokens = clean_ocr_line(lines[idx_c], file_num).split()
                is_vowel_row = all(re.match(r"^(ಅಂ|ಅಃ|[ಅ-ಔೠ])$", t) for t in raw_tokens)
                cells = []
                for t in raw_tokens:
                    t_tex = format_inline_markdown(t)
                    if is_vowel_row:
                        t_tex = rf"{{\kbvsecfont {t_tex}}}"
                    cells.append(rf"\makebox[1.7em]{{{t_tex}}}")
                clean_chart_rows.append("".join(cells))
            blocks.append(
                r"\vspace{4pt plus 4pt minus 1pt}"
                r"\begin{center}"
                r"{\fontsize{11pt}{17pt}\selectfont "
                + " \\\\\n".join(clean_chart_rows)
                + r"}\end{center}"
                r"\vspace{4pt plus 4pt minus 1pt}"
            )
            continue

        # 9. Special Avargiya Ottakshara row on Page 11 (0013.md)
        if file_num == 13 and cleaned.startswith("ಯ್ಯ"):
            tokens = [format_inline_markdown(t) for t in cleaned.split()]
            blocks.append(
                r"\begin{center}{\fontsize{11pt}{15pt}\selectfont "
                + r"\hspace{1.1em}".join(tokens)
                + r"}\end{center}\vspace{3pt}"
            )
            i += 1
            continue

        # 10. Right-aligned poetic source attribution (e.g. —ಕರ್ಣಾಟ ಭಾರತ ಕಥಾಮಂಜರಿ : ಉದ್ಯೋಗಪರ್ವ)
        if 92 <= file_num <= 111 and re.match(r"^[—\-]\s*[^—]+$", cleaned) and len(cleaned) < 58:
            blocks.append(
                rf"\noindent\hfill{{\fontsize{{9.5pt}}{{12.5pt}}\selectfont\color{{kbvgrey}}{format_inline_markdown(cleaned)}}}\par\vspace{{3pt plus 2pt}}"
            )
            i += 1
            continue

        # 11. Consecutive equation / derivation / semicolon-grid lines
        if (
            ("=" in cleaned or ";" in cleaned or "×" in cleaned)
            and len(cleaned) < 75
            and not re.match(r"^(\([0-9]+\)|\[[0-9]+\]|[0-9]+\.)\s+", cleaned)
        ):
            eq_lines = [cleaned]
            j = i + 1
            while j < n:
                nxt = clean_ocr_line(lines[j], file_num)
                if (
                    nxt
                    and ("=" in nxt or ";" in nxt or "×" in nxt)
                    and len(nxt) < 75
                    and not is_chapter_heading(nxt, file_num)
                    and not is_exercise_heading(nxt, file_num)
                ):
                    eq_lines.append(nxt)
                    j += 1
                else:
                    break
            if len(eq_lines) >= 2:
                blocks.append(format_equation_or_pair_block(eq_lines))
                i = j
                continue

        # 12. Consecutive short bullet items (- ಪದ, - ಪದ) -> join horizontally across the page!
        if re.match(r"^[-•]\s+", cleaned) and len(cleaned) < 35 and "=" not in cleaned and "×" not in cleaned:
            short_bullets = [re.sub(r"^[-•]\s+", "", cleaned)]
            j = i + 1
            while j < n:
                nxt = clean_ocr_line(lines[j], file_num)
                if nxt and re.match(r"^[-•]\s+", nxt) and len(nxt) < 35 and "=" not in nxt and "×" not in nxt:
                    short_bullets.append(re.sub(r"^[-•]\s+", "", nxt))
                    j += 1
                else:
                    break
            if len(short_bullets) >= 2:
                joined_items = r"\hspace{0.9em}".join(
                    format_inline_markdown(b) for b in short_bullets
                )
                blocks.append(rf"\noindent\hspace*{{1.8em}}{joined_items}\par\vspace{{3pt plus 2pt}}")
                i = j
                continue

        # 13. Consecutive short (೧), (೨), (೩) items -> horizontal line or aligned columns!
        if re.match(r"^\([೦-೯0-9ಅ-ಔ]\)\s+", cleaned) and len(cleaned) < 58:
            sub_items = [cleaned]
            j = i + 1
            while j < n:
                nxt = clean_ocr_line(lines[j], file_num)
                if nxt and re.match(r"^\([೦-೯0-9ಅ-ಔ]\)\s+", nxt) and len(nxt) < 58 and not nxt.endswith(":"):
                    sub_items.append(nxt)
                    j += 1
                else:
                    break
            # 3 very short items -> single horizontal line with \hfill (e.g. (೧) ಲೋಪ ಸಂಧಿ, (೨) ಆಗಮ ಸಂಧಿ, (೩) ಆದೇಶ ಸಂಧಿ)
            if 2 <= len(sub_items) <= 3 and all(len(x) <= 24 for x in sub_items):
                row_str = r"\hfill ".join(format_inline_markdown(x) for x in sub_items)
                blocks.append(
                    rf"\vspace{{2pt plus 2pt}}\noindent\hspace*{{1.5em}}{row_str}\hspace*{{1.5em}}\par\vspace{{2pt plus 2pt}}"
                )
                i = j
                continue
            # Sub-items with "ಉದಾ :" (like on page 33, 0035.md) -> aligned 3-column table!
            if len(sub_items) >= 3 and all("ಉದಾ" in x for x in sub_items):
                out_t = [
                    r"\vspace{4pt plus 3pt minus 1pt}",
                    r"\begin{center}",
                    r"{\renewcommand{\arraystretch}{1.22}\setlength{\tabcolsep}{5pt}",
                    r"\begin{tabular}{r l c l}",
                ]
                for x in sub_items:
                    m_u = re.match(r"^(\([೦-೯0-9]+\))\s*[:.]?\s*(.+?)\s+ಉದಾ\s*[:;.]*\s*(.+)$", x)
                    if m_u:
                        c_num = format_inline_markdown(m_u.group(1))
                        c_name = format_inline_markdown(m_u.group(2).strip(" :.,"))
                        c_ex = format_inline_markdown(m_u.group(3).strip(" :.,"))
                        out_t.append(rf"{c_num} & {c_name} & ಉದಾ : & {c_ex} \\")
                    else:
                        out_t.append(rf"\multicolumn{{4}}{{l}}{{{format_inline_markdown(x)}}} \\")
                out_t.extend([
                    r"\end{tabular}}",
                    r"\end{center}",
                    r"\vspace{4pt plus 3pt minus 1pt}",
                ])
                blocks.append("\n".join(out_t))
                i = j
                continue

        # 14. Standalone short bold section heading ending with ":" (or known sub-heading)
        if (
            (cleaned.endswith(":") or cleaned.endswith(";"))
            and len(cleaned) < 52
            and not cleaned.startswith("(")
            and not cleaned.startswith("[")
            and "=" not in cleaned
            and "+" not in cleaned
        ) or cleaned in ("ಸ್ವರಗಳು", "ವ್ಯಂಜನಗಳು", "ಗಣಗಳ ವಿನ್ಯಾಸ", "**ವಿಭಕ್ತಿ ರೂಪಗಳು**"):
            h_clean = cleaned.rstrip(";").strip()
            if not h_clean.endswith(":") and h_clean not in ("ಗಣಗಳ ವಿನ್ಯಾಸ", "**ವಿಭಕ್ತಿ ರೂಪಗಳು**"):
                h_clean += " :"
            if re.match(r"^ಉದಾ", h_clean):
                blocks.append(r"\vspace{3pt plus 2pt}\noindent\hspace*{1.2em}\kbvlabel{ಉದಾ}\par\vspace{1pt}")
            else:
                blocks.append(rf"\kbvsechead{{{format_inline_markdown(h_clean)}}}")
            i += 1
            continue

        # 15. Square-bullet rule paragraph (□ ...)
        if cleaned.startswith("□"):
            rule_paras: list[str] = []
            j = i
            while j < n:
                cur = clean_ocr_line(lines[j], file_num)
                if not cur.startswith("□"):
                    break
                rule_text = re.sub(r"^□\.?\s*", "", cur)
                j += 1
                while j < n:
                    nxt = clean_ocr_line(lines[j], file_num)
                    if nxt and not is_standalone_line(nxt, file_num):
                        rule_text += " " + nxt
                        j += 1
                    else:
                        break
                rule_paras.append(format_inline_markdown(rule_text))
                # skip blank lines between consecutive rules
                while j < n and not clean_ocr_line(lines[j], file_num):
                    j += 1
            body = "\\par\n".join(rf"\noindent\kbvbullet\hspace{{0.5em}}{p}" for p in rule_paras)
            blocks.append("\\begin{kbvrule}\n" + body + "\n\\end{kbvrule}")
            i = j
            continue

        # 16. Numbered exercise / section item: (1), [1], 1., (೧), ೧.
        m_num = re.match(
            r"^(\([0-9೦-೯ಅ-ಔಕ-ಳ]+\)|\[[0-9೦-೯ಅ-ಔಕ-ಳ]+\]|[0-9೦-೯]{1,2}[.)])\s*(.+)$",
            cleaned,
        )
        if m_num:
            marker = m_num.group(1)
            rest = m_num.group(2).strip()
            j = i + 1
            while j < n:
                nxt = clean_ocr_line(lines[j], file_num)
                if not is_standalone_line(nxt, file_num):
                    rest += " " + nxt
                    j += 1
                else:
                    break
            # Check if this is a bold section sub-heading like "(೧) ಲೋಪ ಸಂಧಿ :" or "(1) ವರ್ತಮಾನ ಕಾಲದ ಕ್ರಿಯಾಪದ ರೂಪಗಳು : ..."
            m_subsec = re.match(r"^([^:?]{2,38}:)\s*(.*)$", rest)
            if m_subsec and not any(q in m_subsec.group(1) for q in ("ಉದಾ", "ಕೆಳಗೆ", "ಪದಗಳ", "ವಾಕ್ಯ")):
                sub_title = format_inline_markdown(m_subsec.group(1))
                sub_body = format_inline_markdown(m_subsec.group(2)) if m_subsec.group(2) else ""
                marker_tex = format_inline_markdown(marker)
                if sub_body:
                    blocks.append(
                        r"\vspace{4pt plus 4pt minus 1pt}"
                        rf"\noindent{{\kbvsecfont\fontsize{{11pt}}{{14.5pt}}\selectfont\color{{kbvaccentdark}} {marker_tex}\hspace{{0.45em}}{sub_title}}}\hspace{{0.5em}}{sub_body}\par"
                    )
                else:
                    blocks.append(rf"\kbvsechead{{{marker_tex}\hspace{{0.45em}}{sub_title}}}")
            else:
                marker_tex = format_inline_markdown(marker)
                rest_tex = format_inline_markdown(rest)
                blocks.append(
                    r"\vspace{2.5pt plus 3pt minus 0.5pt}"
                    rf"\noindent\hspace*{{1.2em}}\kbvnum{{{marker_tex}}}\hspace{{0.55em}}{rest_tex}\par"
                )
            i = j
            continue

        # 17. Proverb lines on pages 110-112 (0112.md..0114.md) or verse lines ending with । / ॥
        if file_num >= 112:
            blocks.append(
                rf"\noindent\hspace*{{0.6em}}\kbvbullet\hspace{{0.55em}}{format_inline_markdown(cleaned)}\par"
            )
            i += 1
            continue
        if cleaned.endswith("।") or cleaned.endswith("॥"):
            verse_lines = [cleaned]
            j = i + 1
            while j < n:
                nxt = clean_ocr_line(lines[j], file_num)
                if nxt and (nxt.endswith("।") or nxt.endswith("॥")):
                    verse_lines.append(nxt)
                    j += 1
                else:
                    break
            body = " \\\\\n".join(rf"\noindent {format_inline_markdown(v)}" for v in verse_lines)
            blocks.append("\\begin{kbvverse}\n" + body + "\n\\end{kbvverse}")
            i = j
            continue

        # 18. Regular prose paragraph (with inline bolding for ವ್ಯಾಖ್ಯೆ :, ಸೂತ್ರ :, ಉದಾ :, ವಿ.ಸೂ. :)
        para_parts = [cleaned]
        j = i + 1
        while j < n:
            nxt = clean_ocr_line(lines[j], file_num)
            if not is_standalone_line(nxt, file_num):
                # Keep short example sentences (like on 0014.md, 0041.md, 0081.md) on separate lines
                if len(para_parts[-1]) < 40 and para_parts[-1].endswith((".", "?", "!")) and len(nxt) < 40 and nxt.endswith((".", "?", "!")):
                    break
                para_parts.append(nxt)
                j += 1
            else:
                break

        full_para = " ".join(para_parts)
        # Bold leading label like ವ್ಯಾಖ್ಯೆ :, ಸೂತ್ರ :, ವಿವರಣೆ :, ಉದಾ :, ವಿ.ಸೂ. :
        m_label = re.match(
            r"^((?:ಉದಾಹರಣೆಗೆ|ಉದಾಹರಣೆ|ಉದಾ|ವ್ಯಾಖ್ಯೆ|ಸೂತ್ರ|ವಿವರಣೆ|ವಿ\.ಸೂ\.|ವಿನ್ಯಾಸ|ಗಮನಿಸಿ)\s*[:;-])\s*(.+)$",
            full_para,
        )
        if m_label:
            lbl_raw = m_label.group(1).rstrip(" :;-")
            lbl_tex = format_inline_markdown(lbl_raw)
            body_tex = format_inline_markdown(m_label.group(2))
            if lbl_raw.startswith("ಉದಾ"):
                blocks.append(
                    rf"\noindent\hspace*{{1.2em}}\kbvlabel{{ಉದಾ}}\hspace{{0.6em}}{body_tex}\par"
                )
            elif lbl_raw in ("ವ್ಯಾಖ್ಯೆ", "ಸೂತ್ರ"):
                blocks.append(
                    "\\begin{kbvrule}\n"
                    rf"\noindent{{\kbvsecfont {lbl_tex} :}}\hspace{{0.5em}}{body_tex}"
                    "\n\\end{kbvrule}"
                )
            else:
                blocks.append(
                    "\\begin{kbvnote}\n"
                    rf"\noindent{{\kbvsecfont {lbl_tex} :}}\hspace{{0.5em}}{body_tex}"
                    "\n\\end{kbvnote}"
                )
        elif len(para_parts) == 1 and len(full_para) < 42 and full_para.endswith((".", "?", "!")):
            # Short standalone example sentence (indented display sentence)
            blocks.append(rf"\noindent\hspace*{{2.2em}}{format_inline_markdown(full_para)}\par")
        else:
            blocks.append(rf"\indent {format_inline_markdown(full_para)}\par")
        i = j

    return blocks


# ---------------------------------------------------------------------------
# Shared LaTeX preamble pieces (used by both the page-faithful kbv.tex and kbv-redux.tex)
# ---------------------------------------------------------------------------
KBV_PACKAGES_TEX = r"""\usepackage{fontspec}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{eso-pic}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{adjustbox}
\usepackage{fancyhdr}
\usepackage{tikz}
\usepackage{xcolor}
\usepackage{colortbl}
\usepackage[skins]{tcolorbox}

% --- Design palette: monochrome interior (the red cover keeps its own colours) ---
\definecolor{kbvaccent}{HTML}{1A1A1A}
\definecolor{kbvaccentdark}{HTML}{000000}
\definecolor{kbvtint}{HTML}{FFFFFF}
\definecolor{kbvblue}{HTML}{333333}
\definecolor{kbvbluetint}{HTML}{FFFFFF}
\definecolor{kbvgrey}{HTML}{6E6E6E}
\definecolor{kbvrow}{HTML}{FFFFFF}
\definecolor{kbvline}{HTML}{BDBDBD}
\newlength{\kbvcolw}

"""

KBV_FONTS_TEX = r"""\setmainfont[
  Path=fonts/,
  Extension=.ttf,
  UprightFont=*-Regular,
  ItalicFont=*-Italic,
  Script=Kannada,
  HyphenChar=None,
  AutoFakeBold=1.4
]{TiroKannada}
\setsansfont[
  Script=Kannada,
  HyphenChar=None,
  BoldFont={Noto Sans Kannada Bold}
]{Noto Sans Kannada}
\newfontfamily\kbvdisplayfont[
  Path=fonts/,
  Extension=.ttf,
  UprightFont=*-ExtraBold,
  Script=Kannada,
  HyphenChar=None
]{BalooTamma2}
\newfontfamily\kbvcoversans[
  Path=fonts/,
  Extension=.ttf,
  UprightFont=*-SemiBold,
  Script=Kannada,
  HyphenChar=None
]{BalooTamma2}
\newfontfamily\kbvchapfont[
  Path=fonts/,
  Extension=.ttf,
  UprightFont=*-Bold,
  Script=Kannada,
  HyphenChar=None
]{BalooTamma2}
\newfontfamily\kbvsecfont[
  Script=Kannada,
  HyphenChar=None
]{Noto Sans Kannada Bold}
% Latin fallback: Noto Sans Kannada carries no Latin letters (used for (i), (ii), U metre marks, names)
\newfontfamily\kbvlatin[Path=fonts/,Extension=.ttf,UprightFont=*-Regular,ItalicFont=*-Italic]{TiroKannada}

"""

KBV_DESIGN_MACROS_TEX = r"""% --- Design macros (clean, monochrome) ---
% Chapter opener: small grey lesson label, large title, hairline.
\newcommand{\kbvchapter}[2]{%
  \vspace{2pt plus 2pt}%
  \noindent{\kbvsecfont\fontsize{9.5pt}{12pt}\selectfont\color{kbvgrey}#1}\par
  \vspace{2pt}%
  \noindent{\kbvchapfont\fontsize{16pt}{20pt}\selectfont #2}\par
  \vspace{2pt}\noindent{\color{kbvline}\rule{\textwidth}{0.5pt}}\par
  \vspace{5pt plus 4pt minus 1pt}%
}
\newcommand{\kbvchapterplain}[1]{%
  \vspace{2pt plus 2pt}%
  \noindent{\kbvchapfont\fontsize{16pt}{20pt}\selectfont #1}\par
  \vspace{2pt}\noindent{\color{kbvline}\rule{\textwidth}{0.5pt}}\par
  \vspace{5pt plus 4pt minus 1pt}%
}
% Exercise heading: bold sans with a hairline beneath.
\newcommand{\kbvexercise}[1]{%
  \vspace{7pt plus 6pt minus 2pt}%
  \noindent{\kbvsecfont\fontsize{12pt}{15pt}\selectfont #1}\par
  \vspace{1.5pt}\noindent{\color{kbvline}\rule{\textwidth}{0.4pt}}\par
  \vspace{3pt plus 3pt minus 1pt}%
}
% Centered subtitle between two hairlines:  ——— ಲಿಂಗ ———
\newcommand{\kbvsubtitle}[1]{%
  \vspace{4pt plus 3pt minus 1pt}%
  \noindent{\color{kbvline}\hrulefill}\hspace{0.8em}{\kbvsecfont\fontsize{11.5pt}{14.5pt}\selectfont #1}\hspace{0.8em}{\color{kbvline}\hrulefill}\par
  \vspace{3pt plus 3pt minus 1pt}%
}
% Section head: bold sans, nothing else.
\newcommand{\kbvsechead}[1]{%
  \vspace{5pt plus 4pt minus 1pt}%
  \noindent{\kbvsecfont\fontsize{11.5pt}{15pt}\selectfont #1}\par
  \vspace{2pt plus 2pt}%
}
% Example label, always "ಉದಾ :" in bold sans.
\newcommand{\kbvlabel}[1]{{\kbvsecfont #1\,:}}
% Highlighted result word of a derivation.
\newcommand{\kbvresult}[1]{{\kbvsecfont #1}}
% Item marker (1), (೧), ೧.
\newcommand{\kbvnum}[1]{{\kbvsecfont #1}}
% Proverb / list bullet.
\newcommand{\kbvbullet}{{\color{kbvgrey}\raisebox{0.25ex}{\scriptsize\ensuremath{\blacksquare}}}}
% Grammar rule block: white, no frame (the square bullet marks it).
\newtcolorbox{kbvrule}{enhanced,colback=kbvtint,colframe=kbvtint,boxrule=0pt,arc=0pt,
  left=7pt,right=7pt,top=5pt,bottom=5pt,boxsep=0pt,before skip=5pt plus 3pt,after skip=5pt plus 3pt}
% Note / explanation box: hairline frame on white.
\newtcolorbox{kbvnote}{enhanced,colback=white,colframe=kbvline,boxrule=0.4pt,arc=0pt,
  left=7pt,right=7pt,top=5pt,bottom=5pt,boxsep=0pt,before skip=5pt plus 3pt,after skip=5pt plus 3pt}
% Derivation / word-formation block: white, no frame.
\newtcolorbox{kbvderiv}{enhanced,colback=kbvrow,colframe=kbvrow,boxrule=0pt,arc=0pt,
  left=5pt,right=5pt,top=3pt,bottom=3pt,boxsep=0pt,before skip=5pt plus 3pt,after skip=5pt plus 3pt}
% Verse block: indented, no decoration.
\newtcolorbox{kbvverse}{enhanced,colback=white,colframe=white,boxrule=0pt,arc=0pt,
  left=12pt,right=4pt,top=2pt,bottom=2pt,boxsep=0pt,before skip=4pt plus 3pt,after skip=4pt plus 3pt}
"""


def render_cover_page() -> str:
    """Native TikZ recreation of the red front cover."""
    return r"""% === File 0001.md: Native TikZ Cover Page ===
\thispagestyle{empty}
\AddToShipoutPictureBG*{%
  \AtPageLowerLeft{%
    \begin{tikzpicture}
      \useasboundingbox (0,0) rectangle (\paperwidth,\paperheight);
      % Define exact cover palette from coverpage.png
      \definecolor{kbvred}{HTML}{DF212B}
      \definecolor{kbvdarkred}{HTML}{9E1319}
      \definecolor{kbvcloudedge}{HTML}{B51921}
      \definecolor{kbvtextred}{HTML}{98181D}
      \definecolor{kbvoutline}{HTML}{2A0507}
      \definecolor{kbvwavepink}{HTML}{EB605A}
      \definecolor{kbvplumegrey}{HTML}{B8C2C4}
      \definecolor{kbvplumedark}{HTML}{3D4345}

      % 1. Full-bleed vermilion red background
      \fill[kbvred] (0,0) rectangle (\paperwidth,\paperheight);

      % 2. Darker crimson band & 3 sinusoidal wavy ribbons at bottom right (6.5 crests)
      \begin{scope}
        \clip (0.430\paperwidth, 0.0700\paperheight) rectangle (\paperwidth, 0.1524\paperheight);
        \fill[kbvdarkred] (0.430\paperwidth, 0.0860\paperheight) rectangle (\paperwidth, 0.1365\paperheight);
        % Top white wavy ribbon
        \draw[white, line width=3.8pt, line cap=butt]
          plot[domain=0.425:1.01, samples=220, smooth]
          (\x*\paperwidth, {0.1348*\paperheight + 0.0062*\paperheight*cos((\x - 0.430)*11.4*360)});
        % Middle coral-pink wavy ribbon
        \draw[kbvwavepink, line width=3.8pt, line cap=butt]
          plot[domain=0.425:1.01, samples=220, smooth]
          (\x*\paperwidth, {0.1112*\paperheight + 0.0062*\paperheight*cos((\x - 0.430)*11.4*360)});
        % Bottom white wavy ribbon
        \draw[white, line width=3.8pt, line cap=butt]
          plot[domain=0.425:1.01, samples=220, smooth]
          (\x*\paperwidth, {0.0876*\paperheight + 0.0062*\paperheight*cos((\x - 0.430)*11.4*360)});
      \end{scope}

      % 3. Six horizontal white rules across the page width
      \draw[white, line width=1.1pt] (0, 0.9440\paperheight) -- (\paperwidth, 0.9440\paperheight);
      \draw[white, line width=1.0pt] (0, 0.7574\paperheight) -- (\paperwidth, 0.7574\paperheight);
      \draw[white, line width=1.0pt] (0, 0.6151\paperheight) -- (\paperwidth, 0.6151\paperheight);
      \draw[white, line width=1.0pt] (0, 0.4191\paperheight) -- (\paperwidth, 0.4191\paperheight);
      \draw[white, line width=1.0pt] (0, 0.1524\paperheight) -- (\paperwidth, 0.1524\paperheight);
      \draw[white, line width=1.0pt] (0, 0.0700\paperheight) -- (\paperwidth, 0.0700\paperheight);

      % 4. Scalloped 11-lobed cloud badge on the right (matching coverpage.png lobe geometry)
      \begin{scope}[shift={(0.750\paperwidth, 0.778\paperheight)}]
        \def\cloudlobes{
          -5.8/14.2/9.2, 5.8/14.2/9.2,
          -14.2/9.2/9.2, 14.2/9.2/9.2,
          -17.4/0.8/9.0, 17.4/0.8/9.0,
          -15.2/-7.5/9.0, 15.2/-7.5/9.0,
          -8.6/-13.2/8.6, 8.6/-13.2/8.6,
          0.0/-15.2/8.4
        }
        % Layer 1: Outer dark-red border
        \foreach \rx/\ry/\rad in \cloudlobes {
          \fill[kbvcloudedge] (\rx mm, \ry mm) circle ({\rad mm + 1.35mm});
        }
        \fill[kbvcloudedge] (0,0) ellipse (19.5mm and 16.5mm);

        % Layer 2: Outer white ring
        \foreach \rx/\ry/\rad in \cloudlobes {
          \fill[white] (\rx mm, \ry mm) circle ({\rad mm + 0.85mm});
        }
        \fill[white] (0,0) ellipse (19.0mm and 16.0mm);

        % Layer 3: Inner red contour line
        \foreach \rx/\ry/\rad in \cloudlobes {
          \fill[kbvred] (\rx mm, \ry mm) circle ({\rad mm - 0.15mm});
        }
        \fill[kbvred] (0,0) ellipse (18.0mm and 15.0mm);

        % Layer 4: Pure white cloud interior
        \foreach \rx/\ry/\rad in \cloudlobes {
          \fill[white] (\rx mm, \ry mm) circle ({\rad mm - 0.65mm});
        }
        \fill[white] (0,0) ellipse (17.5mm and 14.5mm);

        % 6-line centered Kannada subtitle inside the cloud
        \node[align=center, text=kbvtextred, font=\kbvcoversans\fontsize{12.2pt}{14.2pt}\selectfont] at (0, -0.2mm) {%
          ಪ್ರಾಥಮಿಕ\\
          ಶಾಲಾ ಮತ್ತು\\
          ಪ್ರೌಢ ಶಾಲಾ\\
          ತರಗತಿಗಳಿಗೆ\\
          ಉಪಯುಕ್ತವಾದ\\
          ಪಠ್ಯ ಪುಸ್ತಕ%
        };
      \end{scope}

      % 5. Outlined giant 3-line display title: ಕನ್ನಡ / ಬಾಲ / ವ್ಯಾಕರಣ
      \foreach \ang in {0,15,...,345} {
        \node[anchor=west, text=kbvoutline] at ([shift={(\ang:1.6pt)}]0.052\paperwidth, 0.840\paperheight)
          {\kbvdisplayfont\fontsize{64pt}{64pt}\selectfont ಕನ್ನಡ};
      }
      \node[anchor=west, text=white] at (0.052\paperwidth, 0.840\paperheight)
        {\kbvdisplayfont\fontsize{64pt}{64pt}\selectfont ಕನ್ನಡ};

      \foreach \ang in {0,15,...,345} {
        \node[anchor=west, text=kbvoutline] at ([shift={(\ang:1.6pt)}]0.052\paperwidth, 0.684\paperheight)
          {\kbvdisplayfont\fontsize{65pt}{65pt}\selectfont ಬಾಲ};
      }
      \node[anchor=west, text=white] at (0.052\paperwidth, 0.684\paperheight)
        {\kbvdisplayfont\fontsize{65pt}{65pt}\selectfont ಬಾಲ};

      \foreach \ang in {0,15,...,345} {
        \node[anchor=west, text=kbvoutline] at ([shift={(\ang:1.6pt)}]0.052\paperwidth, 0.512\paperheight)
          {\kbvdisplayfont\fontsize{63pt}{63pt}\selectfont ವ್ಯಾಕರಣ};
      }
      \node[anchor=west, text=white] at (0.052\paperwidth, 0.512\paperheight)
        {\kbvdisplayfont\fontsize{63pt}{63pt}\selectfont ವ್ಯಾಕರಣ};

      % 6. Author name on the right
      \node[anchor=east, text=white, font=\kbvcoversans\fontsize{15pt}{17pt}\selectfont]
        at (0.945\paperwidth, 0.286\paperheight) {ಕೆ. ಆರ್. ಕೆ. ಮೂರ್ತಿ};

      % 7. Publisher Emblem (Vahini Prakashana stylized peacock in framed box)
      \begin{scope}[shift={(0.106\paperwidth, 0.201\paperheight)}]
        \fill[kbvdarkred, draw=white, line width=0.65pt] (-4.3mm, -6.6mm) rectangle (4.3mm, 6.6mm);
        \fill[kbvplumegrey, draw=kbvplumedark, line width=0.35pt] (0.55mm, 0.35mm) circle (2.65mm);
        \foreach \a in {0,18,...,342} {
          \draw[kbvplumedark, line width=0.22pt] (0.55mm, 0.35mm) ++(\a:1.15mm) -- ++(\a:1.5mm);
        }
        \fill[kbvdarkred, draw=kbvplumedark, line width=0.35pt] (0.55mm, 0.35mm) circle (1.15mm);
        \fill[kbvplumegrey, draw=kbvplumedark, line width=0.3pt]
          (-0.5mm, 2.7mm) .. controls (1.2mm, 3.0mm) and (2.2mm, 2.5mm) .. (2.6mm, 1.8mm)
          .. controls (1.2mm, 1.2mm) and (-0.8mm, 0.6mm) .. (-1.2mm, -1.2mm)
          .. controls (-1.6mm, 0.5mm) and (-1.4mm, 2.0mm) .. cycle;
        \fill[white, draw=kbvplumedark, line width=0.35pt]
          (0.1mm, 3.4mm)
          .. controls (-2.4mm, 3.3mm) and (-3.5mm, 1.2mm) .. (-3.3mm, -1.0mm)
          .. controls (-3.1mm, -2.8mm) and (-1.2mm, -3.8mm) .. (0.3mm, -4.8mm)
          .. controls (0.5mm, -5.4mm) and (0.4mm, -6.0mm) .. (0.3mm, -6.1mm)
          .. controls (1.2mm, -5.0mm) and (1.4mm, -3.4mm) .. (0.7mm, -2.2mm)
          .. controls (-0.8mm, -1.5mm) and (-1.6mm, -0.2mm) .. (-1.5mm, 1.2mm)
          .. controls (-1.4mm, 2.1mm) and (-0.2mm, 2.3mm) .. (0.6mm, 2.6mm)
          .. controls (0.8mm, 3.0mm) and (0.6mm, 3.4mm) .. cycle;
        \fill[kbvplumedark] (-0.25mm, 2.85mm) ellipse (0.45mm and 0.28mm);
        \fill[white] (-0.25mm, 2.85mm) circle (0.14mm);
        \foreach \ca in {55, 75, 95, 115, 135} {
          \draw[white, line width=0.35pt] (-0.1mm, 3.5mm) -- ++(\ca:1.3mm);
          \fill[white] (-0.1mm, 3.5mm) ++(\ca:1.3mm) circle (0.22mm);
        }
      \end{scope}

      % 8. Publisher Name at bottom left (between Rule 5 and Rule 6)
      \node[anchor=west, text=white, font=\kbvcoversans\fontsize{14pt}{16pt}\selectfont]
        at (0.066\paperwidth, 0.111\paperheight) {ವಾಹಿನಿ ಪ್ರಕಾಶನ};
    \end{tikzpicture}%
  }%
}
\mbox{}
\clearpage
"""


def render_back_cover_page() -> str:
    """Back cover: framed publisher notice and price."""
    return r"""% === File 0116.md: Back Cover Page ===
\thispagestyle{empty}
\vspace*{2mm}
\begin{center}
\begin{tikzpicture}
  % Main content node inside the framed box
  \node[
    inner xsep=6.5mm,
    inner ysep=8mm,
    text width=90mm,
    align=justify
  ] (box) {%
    \begin{center}
      {\Large\textbf{ಗಮನಿಸಿ :-}}
    \end{center}
    \vspace{4mm}
    \setlength{\parindent}{1.8em}%
    \setlength{\parskip}{4.5mm}%
    \linespread{1.28}\selectfont
    ಪ್ರಾಥಮಿಕ ಹಾಗೂ ಮಾಧ್ಯಮಿಕ ಶಾಲೆಯ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೂ, ಪ್ರೌಢ ಶಾಲೆಯ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೂ, ಕನ್ನಡವನ್ನು ತೃತೀಯ ಭಾಷೆಯಾಗಿ ತೆಗೆದುಕೊಂಡಿರುವ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೂ, ಖಾಸಗಿಯಾಗಿ ಕನ್ನಡ ಕಲಿಯಲು ಬಯಸುವ ಕನ್ನಡೇತರರಿಗೂ, ವಯಸ್ಕರ ಶಾಲೆ ಸೇರಿ ಓದುಬರಹ ಕಲಿಯಬಯಸುವ ಹಿರಿಯರಿಗೂ ಉಪಯುಕ್ತವಾಗುವ ರೀತಿಯಲ್ಲಿ ಈ ವ್ಯಾಕರಣ ಶಾಸ್ತ್ರವನ್ನು ರಚಿಸಲಾಗಿದೆ.\par
    ಪ್ರಾರಂಭಿಕ ಹಂತದಲ್ಲಿ ಕಲಿಯುವವರ ಮನಸ್ಸಿಗೆ ತೊಡಕು ಉಂಟಾಗಬಾರದು. ಈ ಉದ್ದೇಶದಿಂದ ಆಯಾಯ ಪ್ರಕರಣಗಳಿಗೆ ಸಂಬಂಧಪಟ್ಟ ಪಠ್ಯ ವಿಷಯಗಳನ್ನು ತಿಳಿಯಾಗಿ ವಿವರಿಸಲಾಗಿದೆ ಮತ್ತು ಅಧಿಕ ಸಂಖ್ಯೆಯಲ್ಲಿ ಅತ್ಯಂತ ಸಮಂಜಸವಾದ ಉದಾಹರಣೆಗಳನ್ನು ಕೊಡಲಾಗಿದೆ. ಆದುದರಿಂದ ಈ ಪುಸ್ತಕವು \textbf{5, 6, 7, 8, 9} ಮತ್ತು \textbf{10} ನೆಯ ತರಗತಿಯ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಹೆಚ್ಚು ಉಪಯುಕ್ತವೆನ್ನಬಹುದು.\par
    ವಿದ್ಯಾರ್ಥಿಗಳು ಆಯಾಯ ದರ್ಜೆಗೆ ಸೀಮಿತವಾದ ಪಠ್ಯಕ್ರಮಕ್ಕೆ ಅನುಸಾರವಾಗಿ ವಿಷಯವನ್ನು ಆರಿಸಿಕೊಂಡು ಅಭ್ಯಾಸ ಮಾಡಬೇಕಾದ್ದು ಅತಿಮುಖ್ಯ. ಅಭ್ಯಾಸ ಕಷ್ಟವೆನಿಸಿದಾಗ ಶಿಕ್ಷಕರ ನೆರವು ಪಡೆಯಲು ಹಿಂತೆಗೆಯಬಾರದು. ಆಸಕ್ತಿಯಿಂದ ಕಲಿಕೆ ಮುಂದುವರಿಸಿದಲ್ಲಿ ಕಷ್ಟ ಎನಿಸಿದ್ದು ಸುಲಭ ಸಾಧ್ಯವಾಗುವುದು.\par
    \vspace{2mm}
  };
  % Draw letterpress-style border rules with slight corner gaps like full/0116.webp
  \draw[line width=0.9pt] ([xshift=1.2mm]box.north west) -- ([xshift=-1.2mm]box.north east);
  \draw[line width=0.9pt] ([xshift=1.2mm]box.south west) -- ([xshift=-1.2mm]box.south east);
  \draw[line width=0.9pt] ([yshift=-1.2mm]box.north west) -- ([yshift=1.2mm]box.south west);
  \draw[line width=0.9pt] ([yshift=-1.2mm]box.north east) -- ([yshift=1.2mm]box.south east);
  % Bottom title and price aligned with box edges
  \node[anchor=north west, inner sep=0pt] at ([yshift=-3.5mm]box.south west) {\large\textbf{ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ}};
  \node[anchor=north east, inner sep=0pt] at ([yshift=-3.5mm]box.south east) {\large\textbf{ರೂ. 10-00}};
\end{tikzpicture}
\end{center}
\clearpage
"""


def build_kbv_tex(ocr_dir: Path, out_tex: Path) -> None:
    md_files = sorted(ocr_dir.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No .md files found in {ocr_dir}")

    tex_parts: list[str] = [
        r"""\documentclass[10pt]{article}
\usepackage[
  paperwidth=5in,
  paperheight=7in,
  top=10mm,
  bottom=9mm,
  left=9.5mm,
  right=9.5mm,
  headheight=18pt,
  headsep=3.5mm
]{geometry}
"""
        + KBV_PACKAGES_TEX
        + KBV_FONTS_TEX
        + r"""\setlength{\parindent}{1.6em}
\setlength{\parskip}{4.5pt plus 6pt minus 1.5pt}
\linespread{1.20}
\sloppy

\newsavebox{\kbvpagebox}
\newcommand{\kbvtypesetpage}[1]{%
  \begin{lrbox}{\kbvpagebox}%
    \begin{minipage}{\textwidth}%
      \fontsize{10.0pt}{13.0pt}\selectfont
      \setlength{\parindent}{1.6em}%
      \setlength{\parskip}{4.5pt}%
      #1%
    \end{minipage}%
  \end{lrbox}%
  \ifdim\dimexpr\ht\kbvpagebox+\dp\kbvpagebox\relax>0.965\textheight
    \message{^^JKBVSCALED page \thepage\space ht=\the\dimexpr\ht\kbvpagebox+\dp\kbvpagebox\relax\space th=\the\textheight^^J}%
    \noindent\begin{adjustbox}{max totalheight=0.965\textheight, max width=\textwidth, keepaspectratio}%
      \usebox{\kbvpagebox}%
    \end{adjustbox}%
  \else
    \noindent\vbox to 0.96\textheight{%
      \fontsize{10.0pt}{13.0pt}\selectfont
      \setlength{\parindent}{1.6em}%
      \setlength{\parskip}{3.5pt plus 1.5pt minus 1pt}%
      #1%
      \par\vfill
    }%
  \fi
}

% --- Running header: chapter name left, page number in a red tab right ---
\newcommand{\kbvchaptername}{}
\fancypagestyle{kbvpage}{%
  \fancyhf{}%
  \fancyhead[L]{{\kbvsecfont\fontsize{8pt}{10pt}\selectfont\color{kbvgrey}\kbvchaptername}}%
  \fancyhead[R]{{\kbvsecfont\fontsize{9.5pt}{11pt}\selectfont\thepage}}%
  \renewcommand{\headrule}{{\color{kbvline}\hrule width\headwidth height 0.4pt}}%
  \renewcommand{\footrulewidth}{0pt}%
}

"""
        + KBV_DESIGN_MACROS_TEX
        + "\\begin{document}\n"
    ]

    for md_path in md_files:
        file_num = int(md_path.stem)

        # Page 1: Native TikZ recreation of coverpage.png
        if file_num == 1:
            tex_parts.append(render_cover_page())
            continue

        # Pages 3, 4, 5, 105: Custom exact layouts matching full/0003..0005.webp & full/0105.webp
        if file_num == 3:
            tex_parts.append(render_special_page_3())
            continue
        if file_num == 4:
            tex_parts.append(render_special_page_4())
            continue
        if file_num == 5:
            tex_parts.append(render_special_page_5())
            continue

        # Page 116: Back cover page matching full/0116.webp layout & style
        if file_num == 116:
            tex_parts.append(render_back_cover_page())
            continue

        # Determine original printed page number:
        # Files 0007.md .. 0114.md correspond to printed pages 5 .. 112 (N - 2).
        if 7 <= file_num <= 114:
            printed_page = file_num - 2
        else:
            printed_page = None

        md_text = md_path.read_text(encoding="utf-8").strip()

        if not md_text:
            page_cmd = (
                f"\\setcounter{{page}}{{{printed_page}}}\n\\thispagestyle{{kbvpage}}"
                if printed_page is not None
                else "\\thispagestyle{empty}"
            )
            tex_parts.append(
                f"% === File {md_path.name} (Blank Page) ===\n"
                f"{page_cmd}\n"
                r"\mbox{}" "\n"
                r"\clearpage" "\n"
            )
            continue

        body_latex = render_special_page_105() if file_num == 105 else markdown_page_to_latex(md_text, file_num)
        if printed_page is not None:
            header_setup = (
                f"\\renewcommand{{\\kbvchaptername}}{{{running_chapter_name(file_num)}}}\n"
                f"\\setcounter{{page}}{{{printed_page}}}\n\\thispagestyle{{kbvpage}}"
            )
            page_comment = f"Printed Page {printed_page}"
        else:
            header_setup = "\\thispagestyle{empty}"
            page_comment = "Unnumbered Front/Back Matter"

        tex_parts.append(
            f"% === File {md_path.name} ({page_comment}) ===\n"
            f"{header_setup}\n"
            r"\kbvtypesetpage{%" "\n"
            f"{body_latex}\n"
            r"}" "\n"
            r"\clearpage" "\n"
        )

    tex_parts.append(r"\end{document}" + "\n")
    out_tex.write_text("\n".join(tex_parts), encoding="utf-8")
    print(f"Wrote {out_tex} from {len(md_files)} OCR markdown files.")




# ---------------------------------------------------------------------------
# kbv-redux.tex: reflowed edition (no page-for-page constraint), tuned for legibility and print
# ---------------------------------------------------------------------------
REDUX_PREAMBLE_HEAD_TEX = r"""\documentclass[11pt,twoside,openany]{article}
\usepackage[
  paperwidth=6in,
  paperheight=9in,
  inner=21mm,
  outer=17mm,
  top=21mm,
  bottom=22mm,
  headheight=18pt,
  headsep=6mm,
  footskip=9mm
]{geometry}
"""

REDUX_LAYOUT_TEX = r"""\usepackage{tocloft}

% Optional crop/trim marks: build with  xelatex "\def\kbvcropmarks{1}\input{kbv-redux.tex}"
% The 6x9in page is centred on a 7x10in sheet and trim marks are drawn 3mm outside the trim box.
\ifdefined\kbvcropmarks
  \geometry{paperwidth=7in,paperheight=10in,layoutwidth=6in,layoutheight=9in,layouthoffset=0.5in,layoutvoffset=0.5in}
  \AddToShipoutPictureBG{\AtPageLowerLeft{\begin{tikzpicture}[overlay]
    \foreach \x/\dx in {0.5in/-1, 6.5in/1} {
      \foreach \y/\dy in {0.5in/-1, 9.5in/1} {
        \draw[black,line width=0.25pt] ($(\x,\y)+(\dx*3mm,0)$) -- ($(\x,\y)+(\dx*11mm,0)$);
        \draw[black,line width=0.25pt] ($(\x,\y)+(0,\dy*3mm)$) -- ($(\x,\y)+(0,\dy*11mm)$);
      }
    }
    \node[anchor=west,font=\tiny,text=black!60] at (0.5in,0.2in) {ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ \textperiodcentered\ trim 6in \texttimes\ 9in};
  \end{tikzpicture}}}
\fi
\usetikzlibrary{calc}

\setlength{\parindent}{1.5em}
\setlength{\parskip}{3pt plus 1pt minus 0.5pt}
\linespread{1.30}
\sloppy
\raggedbottom
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000

% Running heads: outer page tab + book title on even pages, chapter name on odd pages.
\newcommand{\kbvchaptername}{}
\newcommand{\kbvpagetab}{{\kbvsecfont\fontsize{9.5pt}{11pt}\selectfont\thepage}}
\fancypagestyle{kbvredux}{%
  \fancyhf{}%
  \fancyhead[LE]{\kbvpagetab\hspace{0.9em}{\kbvsecfont\fontsize{8pt}{10pt}\selectfont\color{kbvgrey}ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ}}%
  \fancyhead[RO]{{\kbvsecfont\fontsize{8pt}{10pt}\selectfont\color{kbvgrey}\kbvchaptername}\hspace{0.9em}\kbvpagetab}%
  \renewcommand{\headrule}{{\color{kbvline}\hrule width\headwidth height 0.4pt}}%
  \renewcommand{\footrulewidth}{0pt}%
}
\fancypagestyle{plain}{\fancyhf{}\renewcommand{\headrule}{}\renewcommand{\headrulewidth}{0pt}}
\pagestyle{kbvredux}

% Table of contents styling
\renewcommand{\contentsname}{ವಿಷಯಾನುಕ್ರಮಣಿಕೆ}
\renewcommand{\cfttoctitlefont}{\kbvchapfont\fontsize{20pt}{24pt}\selectfont\color{kbvaccentdark}}
\renewcommand{\cftaftertoctitle}{\par\vspace{3pt}{\color{kbvline}\hrule height 0.5pt}\vspace{8pt}}
\renewcommand{\cftsecfont}{\normalfont}
\renewcommand{\cftsecpresnum}{\kbvsecfont\color{kbvaccent}}
\renewcommand{\cftsecpagefont}{\kbvsecfont}
\renewcommand{\cftsecleader}{{\color{kbvgrey}\cftdotfill{\cftsecdotsep}}}
\setlength{\cftsecnumwidth}{4.6em}
\setlength{\cftbeforesecskip}{4pt}
\setcounter{tocdepth}{1}
"""

REDUX_OVERRIDES_TEX = r"""
% Boxes stay unbreakable: tcolorbox's breakable mode leaks a colour under XeTeX and the
% paragraph after a box is painted invisibly. Short boxes simply move to the next page.

% Chapter opener: always starts a fresh page, feeds the running head and the contents.
\renewcommand{\kbvchapter}[2]{%
  \clearpage\thispagestyle{plain}%
  \renewcommand{\kbvchaptername}{#2}%
  \addcontentsline{toc}{section}{\protect\numberline{#1}#2}%
  \vspace*{6mm}%
  \noindent{\kbvsecfont\fontsize{11pt}{13pt}\selectfont\color{kbvgrey}#1}\par
  \vspace{4pt}%
  \noindent{\kbvchapfont\fontsize{21pt}{26pt}\selectfont #2}\par
  \vspace{4pt}\noindent{\color{kbvline}\rule{\textwidth}{0.5pt}}\par
  \vspace{9mm}%
}
\renewcommand{\kbvchapterplain}[1]{%
  \clearpage\thispagestyle{plain}%
  \renewcommand{\kbvchaptername}{#1}%
  \addcontentsline{toc}{section}{#1}%
  \vspace*{6mm}%
  \noindent{\kbvchapfont\fontsize{21pt}{26pt}\selectfont #1}\par
  \vspace{4pt}\noindent{\color{kbvline}\rule{\textwidth}{0.5pt}}\par
  \vspace{9mm}%
}
"""

_PROSE_RE = re.compile(r"^\\indent (.*)\\par$", re.DOTALL)
_SENTENCE_END_RE = re.compile(r"[.?!:;।॥”\"\)\]]\s*$")


def _merge_cross_page(prev_blocks: list[str], next_blocks: list[str]) -> None:
    """Join a paragraph that the original printing split across two pages.

    The OCR is page-by-page, so a sentence cut by a page break became two paragraphs.
    If the previous page ends with a plain paragraph (or list item) that has no sentence-final
    punctuation and the next page starts with a plain paragraph, glue them back together.
    """
    if not prev_blocks or not next_blocks:
        return
    last = prev_blocks[-1]
    first = next_blocks[0]
    if "\\begin{" in last or not last.endswith("\\par"):
        return
    m_first = _PROSE_RE.match(first)
    if not m_first:
        return
    last_text = last[: -len("\\par")]
    if _SENTENCE_END_RE.search(last_text):
        return
    prev_blocks[-1] = last_text.rstrip() + " " + m_first.group(1).strip() + "\\par"
    next_blocks.pop(0)


def build_redux_tex(ocr_dir: Path, out_tex: Path) -> None:
    md_files = sorted(ocr_dir.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No .md files found in {ocr_dir}")

    parts: list[str] = [
        REDUX_PREAMBLE_HEAD_TEX
        + KBV_PACKAGES_TEX
        + KBV_FONTS_TEX
        + REDUX_LAYOUT_TEX
        + KBV_DESIGN_MACROS_TEX
        + REDUX_OVERRIDES_TEX
        + "\\begin{document}\n",
        "\\pagenumbering{roman}\n",
        render_cover_page(),
        render_special_page_3(),
        render_special_page_4(),
        "% === Table of contents (generated) ===\n\\tableofcontents\\thispagestyle{empty}\n\\cleardoublepage\n",
        "\\pagenumbering{arabic}\n",
    ]

    body_blocks: list[str] = []
    for md_path in md_files:
        file_num = int(md_path.stem)
        if not 7 <= file_num <= 114:
            continue  # cover, front matter and back cover are rendered separately
        md_text = md_path.read_text(encoding="utf-8").strip()
        if not md_text:
            continue
        if file_num == 105:
            body_blocks.append(render_special_page_105())
            continue
        blocks = markdown_page_to_blocks(md_text, file_num)
        if file_num == 7:
            blocks = [b for b in blocks if "ಕನ್ನಡ ಬಾಲ ವ್ಯಾಕರಣ}" not in b]  # title already on the title page
        _merge_cross_page(body_blocks, blocks)
        body_blocks.append(f"% --- from {md_path.name} ---")
        body_blocks.extend(blocks)

    parts.append("\n\n".join(body_blocks) + "\n")
    parts.append("\\cleardoublepage\n" + render_back_cover_page())
    parts.append("\\end{document}\n")
    out_tex.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out_tex} (reflowed edition) from {len(md_files)} OCR markdown files.")


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    build_kbv_tex(base / "ocr", base / "kbv.tex")
    build_redux_tex(base / "ocr", base / "kbv-redux.tex")
