# TCC --- compilação completa.
#
# Ordem: pdflatex -> bibtex -> makeglossaries (siglas) -> makeindex (símbolos)
#        -> pdflatex -> pdflatex.
# As figuras NÃO são geradas aqui: vêm de ../../experiments/figures/output/,
# regeneradas pelo pipeline em experiments/figures/scripts/.

DOC := principal
TEX := pdflatex -interaction=nonstopmode -halt-on-error

.PHONY: all limpo

all: $(DOC).pdf

$(DOC).pdf: $(wildcard *.tex) ../relatorio/referencias.bib
	$(TEX) $(DOC)
	bibtex $(DOC)
	makeglossaries $(DOC)
	makeindex $(DOC).nlo -s nomencl.ist -o $(DOC).nls
	$(TEX) $(DOC)
	$(TEX) $(DOC)

limpo:
	rm -f $(DOC).{aux,bbl,blg,brf,glo,gls,glg,acn,acr,alg,ist,nlo,nls,ilg,idx,ind,lof,lot,log,out,toc,xdy} capitulo*.aux appen*.aux
