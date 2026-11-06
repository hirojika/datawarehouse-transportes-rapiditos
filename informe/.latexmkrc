# Configuración de latexmk para el informe. La leen `latexmk informe.tex`
# (desde la carpeta informe/) y la receta de LaTeX Workshop de .vscode/.
#
# - LuaLaTeX por omisión ($pdf_mode = 4). `latexmk -pdf` sigue usando pdfLaTeX.
# - latexmk ejecuta BibTeX con referencias.bib y repite las pasadas hasta que
#   las referencias cruzadas (Tabla 1.1, Figura 3.1) y las citas ([1]) quedan
#   resueltas. Con una sola pasada de LaTeX aparecen "??" y "[?]".
# - $bibtex_use = 2: `latexmk -c` también borra el .bbl, que se regenera.
$pdf_mode = 4;
$bibtex_use = 2;
