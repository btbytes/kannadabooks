XELATEX := $(shell command -v xelatex 2>/dev/null || echo /Library/TeX/texbin/xelatex)
TEX_FILE := kbv.tex
PDF_FILE := kbv.pdf
TEX_ARTIFACTS := kbv.aux kbv.log kbv.out kbv.toc kbv.fls kbv.fdb_latexmk kbv.synctex.gz
REDUX_TEX := kbv-redux.tex
REDUX_PDF := kbv-redux.pdf
REDUX_CROP_PDF := kbv-redux-crop.pdf
REDUX_ARTIFACTS := kbv-redux.aux kbv-redux.log kbv-redux.out kbv-redux.toc kbv-redux-crop.aux kbv-redux-crop.log kbv-redux-crop.out kbv-redux-crop.toc

.PHONY: all book pdf tex tex-from-ocr clean distclean pages ocr help redux redux-crop

all: help

book: pdf clean

help:
	@echo "Targets:"
	@echo "  make          Show this help"
	@echo "  make book     Compile $(TEX_FILE) to $(PDF_FILE) and clean TeX artifacts"
	@echo "  make pdf      Compile $(TEX_FILE) to $(PDF_FILE)"
	@echo "  make tex      Assemble $(TEX_FILE) and $(REDUX_TEX) from the per-page tex/*.tex files"
	@echo "  make tex-from-ocr  One-time: regenerate tex/*.tex from ocr/*.md (overwrites page edits)"
	@echo "  make redux    Compile the reflowed edition $(REDUX_TEX) to $(REDUX_PDF) (6x9in, two passes for the contents)"
	@echo "  make redux-crop  Same, with crop/trim marks on a 7x10in sheet -> $(REDUX_CROP_PDF)"
	@echo "  make clean    Remove intermediate TeX build artifacts (.aux, .log, .out, etc.)"
	@echo "  make pages    Convert PDF pages to thumb/full/bw WebP images and index.html"
	@echo "  make ocr      Run Kannada OCR on page images into ocr/*.md"

tex:
	python3 build_latex.py

tex-from-ocr:
	python3 build_latex.py --from-ocr --force

pdf: $(PDF_FILE)

$(PDF_FILE): $(TEX_FILE) $(wildcard tex/*.tex)
	$(XELATEX) -interaction=nonstopmode -halt-on-error $(TEX_FILE)

redux: $(REDUX_PDF)

$(REDUX_PDF): $(REDUX_TEX) $(wildcard tex/*.tex)
	$(XELATEX) -interaction=nonstopmode -halt-on-error $(REDUX_TEX)
	$(XELATEX) -interaction=nonstopmode -halt-on-error $(REDUX_TEX)

redux-crop: $(REDUX_CROP_PDF)

$(REDUX_CROP_PDF): $(REDUX_TEX) $(wildcard tex/*.tex)
	$(XELATEX) -interaction=nonstopmode -halt-on-error -jobname=kbv-redux-crop "\\def\\kbvcropmarks{1}\\input{$(REDUX_TEX)}"
	$(XELATEX) -interaction=nonstopmode -halt-on-error -jobname=kbv-redux-crop "\\def\\kbvcropmarks{1}\\input{$(REDUX_TEX)}"

clean:
	rm -f $(TEX_ARTIFACTS) $(REDUX_ARTIFACTS)

distclean: clean
	rm -f $(PDF_FILE) $(REDUX_PDF) $(REDUX_CROP_PDF)

pages:
	./convert_pages.py

ocr:
	./ocr_pages.py
