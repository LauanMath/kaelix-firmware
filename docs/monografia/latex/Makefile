# Monografia no modelo do iCEV (abnTeX2). Ordem: pdflatex, bibtex, makeglossaries (siglas),
# makeindex (símbolos), pdflatex, pdflatex. Saída em build/.
# Os números vêm de values/ (make values) e as figuras de figuras_src/ e de ../../../experiments/figures/output/.

DOC := main
BUILD_DIR := build
TEX := pdflatex -interaction=nonstopmode -halt-on-error -output-directory=$(BUILD_DIR)

.PHONY: all values clean

all:
	mkdir -p $(BUILD_DIR)
	$(TEX) $(DOC)
	BIBINPUTS=.: BSTINPUTS=.: bibtex $(BUILD_DIR)/$(DOC)
	makeglossaries -d $(BUILD_DIR) $(DOC)
	makeindex $(BUILD_DIR)/$(DOC).nlo -s nomencl.ist -o $(BUILD_DIR)/$(DOC).nls
	$(TEX) $(DOC)
	$(TEX) $(DOC)

values:
	python3 scripts/build_field_values.py
	python3 scripts/build_results_values.py

clean:
	rm -rf $(BUILD_DIR)
