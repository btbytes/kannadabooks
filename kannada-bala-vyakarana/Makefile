XELATEX := $(shell command -v xelatex 2>/dev/null || echo /Library/TeX/texbin/xelatex)
TEX_FILE := kbv.tex
PDF_FILE := kbv.pdf
TEX_ARTIFACTS := kbv.aux kbv.log kbv.out kbv.toc kbv.fls kbv.fdb_latexmk kbv.synctex.gz

.PHONY: all pdf tex clean distclean pages ocr help

all: pdf clean

help:
	@echo "Targets:"
	@echo "  make          Compile $(TEX_FILE) to $(PDF_FILE) and clean TeX artifacts"
	@echo "  make pdf      Compile $(TEX_FILE) to $(PDF_FILE)"
	@echo "  make tex      Regenerate $(TEX_FILE) from ocr/*.md via build_latex.py"
	@echo "  make clean    Remove intermediate TeX build artifacts (.aux, .log, .out, etc.)"
	@echo "  make pages    Convert PDF pages to thumb/full/bw WebP images and index.html"
	@echo "  make ocr      Run Kannada OCR on page images into ocr/*.md"

tex:
	python3 build_latex.py

pdf: $(PDF_FILE)

$(PDF_FILE): $(TEX_FILE) coverpage.png
	$(XELATEX) -interaction=nonstopmode -halt-on-error $(TEX_FILE)

clean:
	rm -f $(TEX_ARTIFACTS)

distclean: clean
	rm -f $(PDF_FILE)

pages:
	./convert_pages.py

ocr:
	./ocr_pages.py
