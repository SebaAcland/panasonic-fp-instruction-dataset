"""
Panasonic FP Series IL & Program Step Decompiler / Analyzer
Soporta:
1. Parsear código nemónico crudo / pasos de programa de FPWIN Pro y FPWIN GR.
2. Formato en línea simple (ej. "0 ST X0", "F0 (MV) K10 DT0") y formato multilínea indentado con comentarios (*...*).
3. Normalización y resolución de alias IEC de comparación (ST_EQ, AND_GT, ANF_LT, etc.) y flancos (ST↑, AN^, etc.).
4. Detección automática de subrutinas (SUB Px ... RET o Px: ... RET).
5. Mapeo OPCIONAL de tabla de símbolos/tags exportada en CSV desde FPWIN Pro.
6. Enriquecimiento de cada instrucción con metadatos del dataset y nombres de variables reales.
7. Exportación a JSON estructurado para LLMs / IA.
"""
import json
import re
import os

class PanasonicFPDecompiler:
    def __init__(self, dataset_path=None, symbols_csv_path=None):
        if dataset_path is None:
            dataset_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "panasonic_fp_complete_dataset.json"
            )
        with open(dataset_path, "r", encoding="utf-8") as f:
            self.db = json.load(f)

        # Mapeos de búsqueda rápida de instrucciones
        self.basic_map = {}
        for item in self.db["basic_instructions"]:
            mnem = item["mnemonic"].strip().upper()
            self.basic_map[mnem] = item
            norm_mnem = re.sub(r"\s+", "", mnem)
            self.basic_map[norm_mnem] = item

        self.high_map = {item["fun_no"].upper(): item for item in self.db["high_level_instructions"]}
        self.symbolic_map = {
            item["symbolic_mnemonic"].upper(): item 
            for item in self.db["high_level_instructions"] if item.get("symbolic_mnemonic")
        }

        # Diccionario de alias para nombres exportados por FPWIN Pro
        self.comparison_aliases = {
            "ST_EQ": "ST=", "ST_NE": "ST<>", "ST_GT": "ST>", "ST_GE": "ST>=", "ST_LT": "ST<", "ST_LE": "ST<=",
            "STD_EQ": "STD=", "STD_NE": "STD<>", "STD_GT": "STD>", "STD_GE": "STD>=", "STD_LT": "STD<", "STD_LE": "STD<=",
            "STF_EQ": "STF=", "STF_NE": "STF<>", "STF_GT": "STF>", "STF_GE": "STF>=", "STF_LT": "STF<", "STF_LE": "STF<=",
            "AN_EQ": "AN=", "AN_NE": "AN<>", "AN_GT": "AN>", "AN_GE": "AN>=", "AN_LT": "AN<", "AN_LE": "AN<=",
            "AND_EQ": "AND=", "AND_NE": "AND<>", "AND_GT": "AND>", "AND_GE": "AND>=", "AND_LT": "AND<", "AND_LE": "AND<=",
            "ANF_EQ": "ANF=", "ANF_NE": "ANF<>", "ANF_GT": "ANF>", "ANF_GE": "ANF>=", "ANF_LT": "ANF<", "ANF_LE": "ANF<=",
            "OR_EQ": "OR=", "OR_NE": "OR<>", "OR_GT": "OR>", "OR_GE": "OR>=", "OR_LT": "OR<", "OR_LE": "OR<=",
            "ORD_EQ": "ORD=", "ORD_NE": "ORD<>", "ORD_GT": "ORD>", "ORD_GE": "ORD>=", "ORD_LT": "ORD<", "ORD_LE": "ORD<=",
            "ST^": "ST↑", "ST_UP": "ST↑", "STV": "ST↓", "ST_DOWN": "ST↓",
            "AN^": "AN↑", "AN_UP": "AN↑", "ANV": "AN↓", "AN_DOWN": "AN↓",
            "OR^": "OR↑", "OR_UP": "OR↑", "ORV": "OR↓", "OR_DOWN": "OR↓",
            "OT^": "OT↑", "OT_UP": "OT↑", "OTV": "OT↓", "OT_DOWN": "OT↓"
        }

        # Cargar tabla de símbolos si se proporciona
        self.symbol_table = {}
        if symbols_csv_path:
            self.load_symbols_csv(symbols_csv_path)

    def load_symbols_csv(self, csv_path: str):
        """Carga tabla de tags desde CSV exportado por FPWIN Pro."""
        for enc in ["utf-16le", "utf-8", "latin1"]:
            try:
                with open(csv_path, "r", encoding=enc) as f:
                    lines = f.readlines()
                    break
            except Exception:
                continue
        
        count = 0
        for line in lines:
            parts = [p.strip().strip('"') for p in line.strip().split(",")]
            if len(parts) >= 5:
                tag_name = parts[1]
                iec_addr = parts[2]
                hw_addr = parts[3].upper()
                dtype = parts[4]
                comment = parts[6] if len(parts) > 6 else ""
                
                if hw_addr:
                    self.symbol_table[hw_addr] = {
                        "tag": tag_name,
                        "dtype": dtype,
                        "iec": iec_addr,
                        "comment": comment
                    }
                    count += 1
        return count

    def _resolve_instruction_info(self, raw_token: str):
        token = raw_token.strip().upper()
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

    def _tag_operand(self, operand_str: str):
        """Enriquece un operando de hardware con su Tag si existe en la tabla de símbolos."""
        op_clean = operand_str.strip().upper()
        if op_clean in self.symbol_table:
            info = self.symbol_table[op_clean]
            return {
                "raw": operand_str,
                "tag": info["tag"],
                "dtype": info["dtype"],
                "comment": info["comment"]
            }
        return {"raw": operand_str}

    def analyze_file(self, file_path: str):
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

            step_match = re.match(r"^(\d+)\s+(.*)$", line)
            if step_match:
                step_val = int(step_match.group(1))
                line_content = step_match.group(2).strip()
            else:
                step_val = step_counter
                line_content = line

            sub_match = re.match(r"^(?:SUB\s+)?(P\d+):?$", line_content, re.IGNORECASE)
            if sub_match and not line_content.upper().startswith("CALL"):
                sub_label = sub_match.group(1).upper()
                current_subroutine = sub_label
                subroutines[current_subroutine] = []
                step_counter += 1
                i += 1
                continue

            comment_match = re.search(r"\(\*(.*?)\*\)", line_content)
            inline_comment = comment_match.group(1).strip() if comment_match else None
            line_cleaned = re.sub(r"\(\s*\*.*?\*\s*\)", "", line_content).strip()

            parts = line_cleaned.split(None, 1)
            mnemonic_token = parts[0].strip() if parts else ""
            inline_operands = parts[1].strip() if len(parts) > 1 else ""

            raw_operands = []
            if inline_operands:
                raw_operands.extend([op.strip() for op in re.split(r"[, ]+", inline_operands) if op.strip()])

            j = i + 1
            while j < total_lines:
                next_line = lines[j]
                if next_line.startswith("	") or next_line.startswith("  "):
                    op_clean = re.sub(r"\(\s*\*.*?\*\s*\)", "", next_line).strip()
                    if op_clean and not op_clean.startswith("//"):
                        raw_operands.append(op_clean)
                    j += 1
                else:
                    break

            i = j

            resolved_token, inst_type, details = self._resolve_instruction_info(mnemonic_token)
            tagged_operands = [self._tag_operand(op) for op in raw_operands]

            step_obj = {
                "step": step_val,
                "raw_mnemonic": mnemonic_token,
                "resolved_mnemonic": resolved_token,
                "inline_comment": inline_comment,
                "operands": tagged_operands,
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
            "subroutines_count": len(subroutines),
            "symbols_loaded": len(self.symbol_table)
        }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Descompilador y Analizador de Nemónicos / IL de Panasonic FP Series"
    )
    parser.add_argument(
        "code_file",
        nargs="?",
        default="/mnt/c/Users/Usuario/Desktop/AcuamixPelambre Código de Programa.txt",
        help="Ruta al archivo de código nemónico exportado (.txt)"
    )
    parser.add_argument(
        "--symbols-csv", "-s",
        default=None,
        help="Ruta opcional al archivo CSV de variables exportado desde FPWIN Pro"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Ruta opcional para guardar el resultado estructurado en formato JSON"
    )

    args = parser.parse_args()

    # Si no se pasó CSV por flag, chequear si existe el CSV con el mismo nombre en la misma carpeta
    symbols_csv = args.symbols_csv
    if symbols_csv is None and args.code_file:
        auto_csv = os.path.splitext(args.code_file)[0] + ".csv"
        # También chequear nombre base sin " Código de Programa"
        clean_base = re.sub(r"\s+Código\s+de\s+Programa$", "", os.path.splitext(args.code_file)[0], flags=re.IGNORECASE)
        alt_csv = clean_base + ".csv"
        if os.path.exists(auto_csv):
            symbols_csv = auto_csv
        elif os.path.exists(alt_csv):
            symbols_csv = alt_csv

    decompiler = PanasonicFPDecompiler(symbols_csv_path=symbols_csv)
    if symbols_csv and os.path.exists(symbols_csv):
        print(f"Símbolos cargados desde: {symbols_csv} ({len(decompiler.symbol_table)} variables)")
    else:
        print("Modo: Análisis de direcciones físicas puras (sin CSV de símbolos)")

    if os.path.exists(args.code_file):
        print(f"Analizando archivo de código: {args.code_file} ...")
        result = decompiler.analyze_file(args.code_file)
        print(f"Total de pasos analizados: {result['total_steps']}")
        print(f"Pasos en flujo principal: {len(result['main_flow_steps'])}")
        print(f"Subrutinas encontradas: {list(result['subroutines'].keys())}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f_out:
                json.dump(result, f_out, indent=2, ensure_ascii=False)
            print(f"Resultado guardado en: {args.output}")
        else:
            # Muestra en consola
            print("\n--- Muestra de primeros 6 pasos tageados ---")
            for step in result["main_flow_steps"][:6]:
                comment = f" ({step['inline_comment']})" if step['inline_comment'] else ""
                print(f"Paso {step['step']}: {step['resolved_mnemonic']}{comment}")
                for op in step['operands']:
                    tag = f" -> {op['tag']} ({op['dtype']})" if 'tag' in op else ""
                    print(f"    {op['raw']}{tag}")
    else:
        print(f"Error: El archivo de código no existe: {args.code_file}")
