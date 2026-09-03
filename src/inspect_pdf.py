import fitz  # PyMuPDF
import sys

def inspect_pdf(filepath):
    doc = fitz.open(filepath)
    print(f"File: {filepath}, Pages: {len(doc)}")
    
    # Buscar índice o secciones con instrucciones
    for page_num in range(min(50, len(doc))):
        text = doc[page_num].get_text()
        if "Instruction List" in text or "Table of Instructions" in text or "Basic Instructions" in text or "High-level" in text:
            print(f"Potential instruction index on page {page_num + 1}")
            first_lines = "\n".join(text.split("\n")[:10])
            print(f"--- Page {page_num+1} sample ---\n{first_lines}\n")

if __name__ == "__main__":
    import os
    docs_dir = "/home/seba/sadesa-app-scarpping-soplantes/panasonic-fp-instruction-dataset/docs"
    for f in os.listdir(docs_dir):
        if f.endswith(".pdf"):
            inspect_pdf(os.path.join(docs_dir, f))
