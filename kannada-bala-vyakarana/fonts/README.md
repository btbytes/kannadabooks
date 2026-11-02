# Fonts

Vendored so the book builds on any machine without installing fonts. `build_latex.py`
references these files via fontspec `Path=fonts/`.

| Family | Files | Role | Source |
|---|---|---|---|
| Tiro Kannada (Tiro Typeworks) | `TiroKannada-Regular.ttf`, `TiroKannada-Italic.ttf` | body text, Latin fallback | https://github.com/google/fonts/tree/main/ofl/tirokannada |
| Baloo Tamma 2 (Ek Type) | `BalooTamma2-{Regular,Medium,SemiBold,Bold,ExtraBold}.ttf` | cover title, chapter titles | https://github.com/google/fonts/tree/main/ofl/balootamma2 |

Baloo Tamma 2 is published as a variable font (`BalooTamma2[wght].ttf`). XeTeX cannot select
variable-font weights, so the static weights here were produced with
`python -m fontTools.varLib.instancer BalooTamma2[wght].ttf wght=400|500|600|700|800`.

Noto Sans Kannada (section heads, labels, badges, running heads) is taken from the system.

Both families are licensed under the SIL Open Font License 1.1; see `OFL-TiroKannada.txt`
and `OFL-BalooTamma2.txt`.
