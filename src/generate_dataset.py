import pymupdf
import json
import re

def parse_all_fp0h():
    pdf_path = "/home/seba/sadesa-app-scarpping-soplantes/panasonic-fp-instruction-dataset/docs/mn_fp0h_cpu_programming_pid_en.pdf"
    doc = pymupdf.open(pdf_path)
    
    basic_instructions = []
    high_level_instructions = []
    
    # 1.1 Basic Instructions: Pages 20 to 25 (index 19 to 24)
    for p_idx in range(19, 25):
        page = doc[p_idx]
        tabs = page.find_tables()
        for table in tabs.tables:
            for row in table.extract():
                cleaned = [re.sub(r'\s+', ' ', str(c).strip()) if c is not None else "" for c in row]
                if not cleaned or not cleaned[0] or "Mnemonic" in cleaned[0] or "Basic Instruction" in cleaned[0]:
                    continue
                
                # Formato típico: [Mnemonic, Description, Steps, RefPage]
                mnemonic = cleaned[0].replace("\n", " ").strip()
                desc = cleaned[1] if len(cleaned) > 1 else ""
                steps = cleaned[2] if len(cleaned) > 2 else ""
                ref_page = cleaned[3] if len(cleaned) > 3 else ""
                
                # Limpiar notas al pie ej (Note 1)
                desc = re.sub(r'\(Note \d+\)', '', desc).strip()
                
                basic_instructions.append({
                    "mnemonic": mnemonic,
                    "type": "basic",
                    "description": desc,
                    "steps": steps,
                    "manual_ref": ref_page,
                    "category": "Basic Instruction"
                })

    # 1.2 High-Level Instructions (Fxxx): Pages 26 to 43 (index 25 to 42)
    current_category = "High-level Instruction"
    for p_idx in range(25, 43):
        page = doc[p_idx]
        
        # Obtener encabezados de categoría si existen en el texto
        raw_text = page.get_text()
        for line in raw_text.split("\n"):
            line_s = line.strip()
            if line_s.endswith("instructions") or "instruction" in line_s.lower() and len(line_s) < 45:
                if not line_s.startswith("List of") and not line_s.startswith("1.2"):
                    current_category = line_s.replace("■", "").strip()
        
        tabs = page.find_tables()
        for table in tabs.tables:
            for row in table.extract():
                cleaned = [re.sub(r'\s+', ' ', str(c).strip()) if c is not None else "" for c in row]
                if not cleaned or not cleaned[0] or "Fun no." in cleaned[0] or "Mnemonic" in cleaned[0]:
                    continue
                
                # Columnas de High-Level: [Fun no. (Fxxx / Pxxx), Mnemonic, Operands, Name/Description, Steps, RefPage]
                fun_no = cleaned[0].strip()
                
                if len(cleaned) >= 5:
                    mnemonic_sym = cleaned[1].strip()
                    operands = cleaned[2].strip()
                    name_desc = cleaned[3].strip()
                    steps = cleaned[4].strip()
                    ref_page = cleaned[5] if len(cleaned) > 5 else ""
                elif len(cleaned) == 4:
                    mnemonic_sym = cleaned[1].strip()
                    operands = ""
                    name_desc = cleaned[2].strip()
                    steps = cleaned[3].strip()
                    ref_page = ""
                else:
                    continue
                
                if not fun_no.startswith("F") and not fun_no.startswith("P") and not fun_no.isdigit():
                    continue

                high_level_instructions.append({
                    "fun_no": fun_no,
                    "symbolic_mnemonic": mnemonic_sym,
                    "operands_syntax": operands,
                    "name": name_desc,
                    "steps": steps,
                    "category": current_category,
                    "manual_ref": ref_page,
                    "full_syntax": f"{fun_no} ({mnemonic_sym}){(' ' + operands) if operands else ''}"
                })

    dataset = {
        "metadata": {
            "title": "Panasonic FP0 / FP0H / FP Series Instruction & Step Code Knowledge Base",
            "source": "Panasonic FP0H CPU Programming Manual (WUMJ-FP0HPGR-091) & FP-Series Manual",
            "target": "LLM / AI Model fine-tuning & prompt enrichment for decompilation & subroutine analysis",
            "total_basic_instructions": len(basic_instructions),
            "total_high_level_instructions": len(high_level_instructions)
        },
        "memory_map": {
            "X": {"type": "Bit/Word (WX)", "desc": "Entrada digital física (External Input)"},
            "Y": {"type": "Bit/Word (WY)", "desc": "Salida digital física (External Output)"},
            "R": {"type": "Bit/Word (WR)", "desc": "Relé interno / Bandera de memoria (Internal Relay)"},
            "SR": {"type": "Bit/Word (WSR)", "desc": "Relé especial del sistema (Special Internal Relay, ej: R9010 Always ON)"},
            "T": {"type": "Bit/Word (TS/TP)", "desc": "Temporizador (Timer contact / Set value / Present value)"},
            "C": {"type": "Bit/Word (CS/CP)", "desc": "Contador (Counter contact / Set value / Present value)"},
            "DT": {"type": "Word (16-bit) / DWord (DDT 32-bit)", "desc": "Registro de datos generales (Data Register)"},
            "LD": {"type": "Word", "desc": "Registro de enlace local (Link Data Register)"},
            "FL": {"type": "Word", "desc": "Registro de memoria flash / archivos (File Register)"},
            "K": {"type": "Decimal Constant", "desc": "Constante numérica decimal entera (ej: K100, K-5)"},
            "H": {"type": "Hexadecimal Constant", "desc": "Constante hexadecimal (ej: H1F, HFFFF)"},
            "P": {"type": "Pointer / Label", "desc": "Puntero para subrutinas o saltos (ej: CALL P0, P0:)"}
        },
        "system_special_relays": {
            "R9010": "Siempre en ON (Normally ON relay)",
            "R9011": "Siempre en OFF (Normally OFF relay)",
            "R9013": "Primer ciclo de scan en ON (Initial scan pulse)",
            "R9014": "Error flag (Se activa si hay error de ejecución de instrucción)",
            "R9018": "Pulso de reloj de 1 segundo (1s clock pulse)",
            "R901A": "Resultado de comparación mayor que (>)",
            "R901B": "Resultado de comparación igual (=)",
            "R901C": "Resultado de comparación menor que (<)",
            "R901D": "Bandera de acarreo / Carry Flag (CY)"
        },
        "subroutine_and_flow_mechanics": {
            "CALL": "Llama a la subrutina Px. Al ejecutar, salta a la etiqueta Px y apila el contador de programa.",
            "RET": "Retorno de subrutina. Desapila y retorna a la instrucción siguiente al CALL.",
            "MC": "Master Control. Habilita o deshabilita la ejecución condicional de un bloque de programa.",
            "MCE": "Master Control End. Cierra el bloque Master Control.",
            "JP": "Salto incondicional o condicional a una etiqueta Px.",
            "LOOP": "Bucle con contador (usado con F168 o instrucciones de control)."
        },
        "basic_instructions": basic_instructions,
        "high_level_instructions": high_level_instructions
    }
    
    out_path = "/home/seba/sadesa-app-scarpping-soplantes/panasonic-fp-instruction-dataset/data/panasonic_fp_complete_dataset.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    print(f"Dataset generado exitosamente en {out_path}")
    print(f"- Instrucciones básicas: {len(basic_instructions)}")
    print(f"- Instrucciones de alto nivel (Fxxx): {len(high_level_instructions)}")

if __name__ == "__main__":
    parse_all_fp0h()
