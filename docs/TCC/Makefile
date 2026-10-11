# TCC --- compilação completa.
#
# Ordem: pdflatex -> bibtex -> makeglossaries (siglas) -> makeindex (símbolos)
#        -> pdflatex -> pdflatex.
# As figuras NÃO são geradas aqui: vêm de ../../experiments/figures/output/,
# regeneradas pelo pipeline em experiments/figures/scripts/.

DOC := tcc
TEX := pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build
BUILD_DIR := build

.PHONY: all clean

all: $(BUILD_DIR)/$(DOC).pdf

# Garante que o diretório build existe antes de compilar
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/$(DOC).pdf: $(wildcard *.tex) referencias.bib | $(BUILD_DIR)
	$(TEX) $(DOC)
	bibtex $(BUILD_DIR)/$(DOC)
	makeglossaries -d $(BUILD_DIR) $(DOC)
	makeindex $(BUILD_DIR)/$(DOC).nlo -s nomencl.ist -o $(BUILD_DIR)/$(DOC).nls
	$(TEX) $(DOC)
	$(TEX) $(DOC)

clean:
	rm -rf $(BUILD_DIR)