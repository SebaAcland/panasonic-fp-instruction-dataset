"""
Panasonic FP Series IL & Program Step Decompiler / Analyzer
Capaz de:
1. Parsear código nemónico crudo / pasos de programa de FPWIN Pro / FPWIN GR.
2. Identificar y agrupar llamadas a subrutinas (CALL Px ... RET).
3. Enriquecer cada instrucción con su descripción, operandos y mapa de memoria.
4. Generar formato estructurado para LLMs / IA.
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

        # Mapeos rápidos
        self.basic_map = {item["mnemonic"].upper(): item for item in self.db["basic_instructions"]}
        self.high_map = {item["fun_no"].upper(): item for item in self.db["high_level_instructions"]}
        # Mapeo alternativo por nemónico simbólico (ej: "MV" -> F0)
        self.symbolic_map = {item["symbolic_mnemonic"].upper(): item for item in self.db["high_level_instructions"] if item.get("symbolic_mnemonic")}

    def parse_line(self, line: str):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith(";") or line.startswith("#"):
            return None

        # Regex flexible para capturar:
        # Formato 1: "0 ST X0" o "120 F0 (MV), K10, DT0"
        # Formato 2: "ST X0" o "CALL P1"
        # Formato 3: "P0:" o "P0" (Etiqueta)
        step_match = re.match(r"^(\d+)\s+(.*)$", line)
        step = None
        instruction_body = line
        if step_match:
            step = int(step_match.group(1))
            instruction_body = step_match.group(2).strip()

        # Etiqueta de puntero / subrutina (ej: P0: o P0)
        if re.match(r"^P\d+:?$", instruction_body):
            label = instruction_body.rstrip(":")
            return {
                "step": step,
                "type": "label",
                "label": label,
                "description": f"Etiqueta de subrutina o salto {label}"
            }

        # Separar Nemónico de Operandos
        parts = instruction_body.split(None, 1)
        mnemonic_token = parts[0].strip()
        operands_str = parts[1].strip() if len(parts) > 1 else ""

        # Manejar formato "F0 (MV)" como un solo token si viene con paréntesis
        if "(" in instruction_body and not "(" in operands_str:
            match_f = re.match(r"^(F\d+\s*\([A-Za-z0-9_+-]+\)|P\d+\s*\([A-Za-z0-9_+-]+\))\s*(.*)$", instruction_body)
            if match_f:
                mnemonic_token = match_f.group(1).strip()
                operands_str = match_f.group(2).strip()

        # Limpiar operandos
        operands = [op.strip() for op in re.split(r'[, ]+', operands_str) if op.strip()]

        # Buscar en la base de datos
        key = mnemonic_token.split()[0].upper()
        info = None
        inst_type = "unknown"

        if key in self.basic_map:
            info = self.basic_map[key]
            inst_type = "basic"
        elif key in self.high_map:
            info = self.high_map[key]
            inst_type = "high_level"
        elif key in self.symbolic_map:
            info = self.symbolic_map[key]
            inst_type = "high_level"

        return {
            "step": step,
            "raw": line,
            "instruction": mnemonic_token,
            "operands": operands,
            "type": inst_type,
            "details": info
        }

    def analyze_program(self, program_code: str):
        lines = program_code.strip().split("\n")
        parsed_steps = []
        subroutines = {}
        current_subroutine = None

        for line in lines:
            parsed = self.parse_line(line)
            if not parsed:
                continue

            # Detectar subrutinas Px ... RET
            if parsed.get("type") == "label":
                current_subroutine = parsed["label"]
                subroutines[current_subroutine] = []
                continue
            
            if current_subroutine:
                subroutines[current_subroutine].append(parsed)
                if parsed.get("instruction", "").upper() == "RET":
                    current_subroutine = None
            else:
                parsed_steps.append(parsed)

        return {
            "main_flow_steps": parsed_steps,
            "subroutines": subroutines,
            "subroutines_count": len(subroutines)
        }

if __name__ == "__main__":
    sample_decompiled_code = """
    0 ST X0
    1 AN/ R10
    2 OT Y0
    3 ST X1
    4 CALL P0
    5 F0 (MV), K100, DT10
    6 F22 (ADD), DT10, K5, DT20
    7 ED

    P0:
    100 ST R0
    101 OT Y1
    102 RET
    """
    decompiler = PanasonicFPDecompiler()
    analysis = decompiler.analyze_program(sample_decompiled_code)
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
