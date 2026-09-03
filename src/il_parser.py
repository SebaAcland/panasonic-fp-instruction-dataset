"""
Panasonic FP Series IL & Program Step Decompiler / Analyzer
Soporta:
1. Parsear código nemónico crudo / pasos de programa de FPWIN Pro y FPWIN GR.
2. Formato en línea simple (ej. "0 ST X0", "F0 (MV) K10 DT0") y formato multilínea indentado con comentarios (*...*).
3. Normalización y resolución de alias IEC de comparación (ST_EQ, AND_GT, ANF_LT, etc.) y flancos (ST↑, AN^, etc.).
4. Detección automática de subrutinas (SUB Px ... RET o Px: ... RET).
5. Enriquecimiento de cada instrucción con metadatos del dataset y mapa de operandos.
6. Exportación a JSON estructurado para LLMs / IA.
"""
import json
import re
import os

class PanasonicFPDecompiler:
    def __init__(self, dataset_path=None):
        if dataset_path is None:
            dataset_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "panasonic_fp_complete_dataset.json"
            )
        with open(dataset_path, "r", encoding="utf-8") as f:
            self.db = json.load(f)

        # Mapeos de búsqueda rápida
        self.basic_map = {}
        for item in self.db["basic_instructions"]:
            mnem = item["mnemonic"].strip().upper()
            self.basic_map[mnem] = item
            # Normalizar sin espacios internos (ej "AN =" -> "AN=")
            norm_mnem = re.sub(r"\s+", "", mnem)
            self.basic_map[norm_mnem] = item

        self.high_map = {item["fun_no"].upper(): item for item in self.db["high_level_instructions"]}
        self.symbolic_map = {
            item["symbolic_mnemonic"].upper(): item 
            for item in self.db["high_level_instructions"] if item.get("symbolic_mnemonic")
        }

        # Diccionario de alias para nombres exportados por FPWIN Pro
        self.comparison_aliases = {
            # 16-bit Start
            "ST_EQ": "ST=", "ST_NE": "ST<>", "ST_GT": "ST>", "ST_GE": "ST>=", "ST_LT": "ST<", "ST_LE": "ST<=",
            # 32-bit Start
            "STD_EQ": "STD=", "STD_NE": "STD<>", "STD_GT": "STD>", "STD_GE": "STD>=", "STD_LT": "STD<", "STD_LE": "STD<=",
            # Real/Float Start
            "STF_EQ": "STF=", "STF_NE": "STF<>", "STF_GT": "STF>", "STF_GE": "STF>=", "STF_LT": "STF<", "STF_LE": "STF<=",
            # 16-bit AND
            "AN_EQ": "AN=", "AN_NE": "AN<>", "AN_GT": "AN>", "AN_GE": "AN>=", "AN_LT": "AN<", "AN_LE": "AN<=",
            # 32-bit AND
            "AND_EQ": "AND=", "AND_NE": "AND<>", "AND_GT": "AND>", "AND_GE": "AND>=", "AND_LT": "AND<", "AND_LE": "AND<=",
            # Real/Float AND
            "ANF_EQ": "ANF=", "ANF_NE": "ANF<>", "ANF_GT": "ANF>", "ANF_GE": "ANF>=", "ANF_LT": "ANF<", "ANF_LE": "ANF<=",
            # 16-bit OR
            "OR_EQ": "OR=", "OR_NE": "OR<>", "OR_GT": "OR>", "OR_GE": "OR>=", "OR_LT": "OR<", "OR_LE": "OR<=",
            # 32-bit OR
            "ORD_EQ": "ORD=", "ORD_NE": "ORD<>", "ORD_GT": "ORD>", "ORD_GE": "ORD>=", "ORD_LT": "ORD<", "ORD_LE": "ORD<=",
            # Flancos alternativos
            "ST^": "ST↑", "ST_UP": "ST↑", "STV": "ST↓", "ST_DOWN": "ST↓",
            "AN^": "AN↑", "AN_UP": "AN↑", "ANV": "AN↓", "AN_DOWN": "AN↓",
            "OR^": "OR↑", "OR_UP": "OR↑", "ORV": "OR↓", "OR_DOWN": "OR↓",
            "OT^": "OT↑", "OT_UP": "OT↑", "OTV": "OT↓", "OT_DOWN": "OT↓"
        }

    def _resolve_instruction_info(self, raw_token: str):
        token = raw_token.strip().upper()
        # Resolver alias
        token = self.comparison_aliases.get(token, token)
        norm_token = re.sub(r"\s+", "", token)

        if token in self.basic_map:
            return token, "basic", self.basic_map[token]
        if norm_token in self.basic_map:
            return norm_token, "basic", self.basic_map[norm_token]
        if token in self.high_map:
            return token, "high_level", self.high_map[token]
        if token in self.symbolic_map:
            return token, "high_level", self.symbolic_map[token]

        return raw_token, "unknown", None

    def analyze_file(self, file_path: str):
        """Lee un archivo de código exportado probando UTF-8 y UTF-16LE."""
        raw_text = None
        for enc in ["utf-16le", "utf-8", "latin1"]:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    raw_text = f.read()
                    break
            except (UnicodeError, UnicodeDecodeError):
                continue
        if raw_text is None:
            raise ValueError(f"No se pudo decodificar el archivo: {file_path}")
        return self.analyze_program(raw_text)

    def analyze_program(self, program_code: str):
        lines = program_code.splitlines()
        parsed_steps = []
        subroutines = {}
        current_subroutine = None

        i = 0
        step_counter = 0
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i].replace("﻿", "").strip()
            if not line or line.startswith("//") or line.startswith("#"):
                i += 1
                continue

            # Detectar número de paso inicial si existe (ej. "0 ST X0")
            step_match = re.match(r"^(\d+)\s+(.*)$", line)
            if step_match:
                step_val = int(step_match.group(1))
                line_content = step_match.group(2).strip()
            else:
                step_val = step_counter
                line_content = line

            # Caso 1: Definición de Subrutina SUB P0 o P0:
            sub_match = re.match(r"^(?:SUB\s+)?(P\d+):?$", line_content, re.IGNORECASE)
            if sub_match and not line_content.upper().startswith("CALL"):
                sub_label = sub_match.group(1).upper()
                current_subroutine = sub_label
                subroutines[current_subroutine] = []
                step_counter += 1
                i += 1
                continue

            # Limpiar comentarios tipo (*DCMP*) o (*MV*)
            comment_match = re.search(r"\(\*(.*?)\*\)", line_content)
            inline_comment = comment_match.group(1).strip() if comment_match else None
            line_cleaned = re.sub(r"\(\s*\*.*?\*\s*\)", "", line_content).strip()

            parts = line_cleaned.split(None, 1)
            mnemonic_token = parts[0].strip() if parts else ""
            inline_operands = parts[1].strip() if len(parts) > 1 else ""

            # Recolectar operandos en líneas siguientes si vienen indentadas
            operands = []
            if inline_operands:
                operands.extend([op.strip() for op in re.split(r"[, ]+", inline_operands) if op.strip()])

            # Revisar siguientes líneas indentadas que corresponden a operandos
            j = i + 1
            while j < total_lines:
                next_line = lines[j]
                if next_line.startswith("	") or next_line.startswith("  "):
                    op_clean = re.sub(r"\(\s*\*.*?\*\s*\)", "", next_line).strip()
                    if op_clean and not op_clean.startswith("//"):
                        operands.append(op_clean)
                    j += 1
                else:
                    break

            i = j  # Avanzar al siguiente comando

            # Resolver nemónico e información técnica
            resolved_token, inst_type, details = self._resolve_instruction_info(mnemonic_token)

            step_obj = {
                "step": step_val,
                "raw_mnemonic": mnemonic_token,
                "resolved_mnemonic": resolved_token,
                "inline_comment": inline_comment,
                "operands": operands,
                "type": inst_type,
                "details": details
            }

            if current_subroutine:
                subroutines[current_subroutine].append(step_obj)
                if resolved_token == "RET":
                    current_subroutine = None
            else:
                parsed_steps.append(step_obj)

            step_counter += 1

        return {
            "total_steps": step_counter,
            "main_flow_steps": parsed_steps,
            "subroutines": subroutines,
            "subroutines_count": len(subroutines)
        }

if __name__ == "__main__":
    sample_path = "/mnt/c/Users/Usuario/Desktop/AcuamixPelambre Código de Programa.txt"
    decompiler = PanasonicFPDecompiler()
    
    if os.path.exists(sample_path):
        print(f"Analizando archivo real: {sample_path} ...")
        result = decompiler.analyze_file(sample_path)
        print(f"Total de instrucciones/pasos analizados: {result['total_steps']}")
        print(f"Pasos en flujo principal: {len(result['main_flow_steps'])}")
        print(f"Subrutinas encontradas: {list(result['subroutines'].keys())}")
        
        # Muestra de las primeras 3 instrucciones parseadas
        print("\n--- Muestra de pasos estructurados ---")
        print(json.dumps(result["main_flow_steps"][:3], indent=2, ensure_ascii=False))
