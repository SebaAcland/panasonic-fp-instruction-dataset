import pymupdf
import json
import re

def extract_tables_from_fp0h():
    pdf_path = "/home/seba/sadesa-app-scarpping-soplantes/panasonic-fp-instruction-dataset/docs/mn_fp0h_cpu_programming_pid_en.pdf"
    doc = pymupdf.open(pdf_path)
    
    # 1.1 List of Basic Instruction Words (pages 20 to 25 -> index 19 to 24)
    # 1.2 List of High-level Instructions (pages 26 to 43 -> index 25 to 42)
    
    extracted_instructions = []
    
    # Extraer de las páginas de índice
    for p_idx in range(19, 43):
        page = doc[p_idx]
        tabs = page.find_tables()
        if tabs.tables:
            for table in tabs.tables:
                df_rows = table.extract()
                for row in df_rows:
                    cleaned_row = [str(c).strip() if c is not None else "" for c in row]
                    # Filtramos encabezados
                    if not cleaned_row or "Mnemonic" in cleaned_row or "Fun no." in cleaned_row:
                        continue
                    extracted_instructions.append({
                        "page": p_idx + 1,
                        "raw_row": cleaned_row
                    })
        else:
            # Si find_tables no detecta, procesamos texto
            lines = [l.strip() for l in page.get_text().split("\n") if l.strip()]
            extracted_instructions.append({
                "page": p_idx + 1,
                "lines": lines
            })

    print(f"Total raw items / tables extracted from FP0H index: {len(extracted_instructions)}")
    return extracted_instructions

if __name__ == "__main__":
    items = extract_tables_from_fp0h()
    print("Primeros 5 elementos:", items[:5])
