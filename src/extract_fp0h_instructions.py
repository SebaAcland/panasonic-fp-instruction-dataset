import pymupdf
import json
import re

pdf_path = "/home/seba/sadesa-app-scarpping-soplantes/panasonic-fp-instruction-dataset/docs/mn_fp0h_cpu_programming_pid_en.pdf"
doc = pymupdf.open(pdf_path)

# Las páginas 19 a 43 contienen el sumario completo de instrucciones básicas y de alto nivel (F)
# 19 en PDF (0-indexed es 18 hasta 42)
pages_range = range(18, 43)

instructions = []

for p in pages_range:
    text = doc[p].get_text("text")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # Extraer entradas de tablas
    # Buscamos patrones de instrucciones de alto nivel Fxxx o básicas
    # Ejemplo en FP0H: "F0", "MV", "S, D", "16-bit data transfer", "3", ...
    # O procesar bloques
    pass

print(f"Manual FP0H cargado con {len(doc)} páginas.")
