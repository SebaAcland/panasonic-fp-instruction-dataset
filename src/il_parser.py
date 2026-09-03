"""
Panasonic FP Series IL / Step Code Parser
Interpreta código nemónico / pasos de programa generado por FPWIN Pro / FPWIN GR.
"""
import json
import re

class FPILParser:
    def __init__(self, dataset_path="data/panasonic_fp_instructions.json"):
        with open(dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)
        self.instructions_map = {inst["code"]: inst for inst in self.dataset["instructions"]}

    def parse_line(self, line: str):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith(";"):
            return None

        # Regex para parsear formato estándar: [PASO] MNEMÓNICO [OPERANDOS]
        # Ejemplos:
        # "0  ST  X0"
        # "1  AN  R0"
        # "2  OT  Y0"
        # "3  F0 (MV), K10, DT0"
        # "4  CALL P0"
        match = re.match(r"^(\d+)?\s*([A-Za-z0-9_/]+(?:\s*\([A-Za-z0-9_]+\))?)\s*(.*)$", line)
        if not match:
            return {"raw": line, "error": "Unrecognized format"}

        step, mnemonic, operands_raw = match.groups()
        
        # Limpiar nemónico
        mnemonic_clean = mnemonic.split()[0].upper()
        
        # Procesar operandos separados por coma o espacio
        operands = [op.strip() for op in re.split(r'[, ]+', operands_raw) if op.strip()] if operands_raw else []

        meta = self.instructions_map.get(mnemonic_clean, {})

        return {
            "step": int(step) if step else None,
            "mnemonic": mnemonic_clean,
            "full_mnemonic": mnemonic,
            "operands": operands,
            "info": meta.get("description", "Unknown / High-level instruction"),
            "category": meta.get("category", "General"),
            "iec_equivalent": meta.get("iec_equivalent", None)
        }

    def parse_program(self, program_text: str):
        lines = program_text.strip().split("\n")
        parsed = []
        for line in lines:
            res = self.parse_line(line)
            if res:
                parsed.append(res)
        return parsed

if __name__ == "__main__":
    sample_program = """
    0 ST X0
    1 AN/ R10
    2 OR X1
    3 OT Y0
    4 ST X2
    5 CALL P0
    6 F0 (MV), K100, DT10
    """
    parser = FPILParser("panasonic-fp-instruction-dataset/data/panasonic_fp_instructions.json")
    result = parser.parse_program(sample_program)
    print(json.dumps(result, indent=2, ensure_ascii=False))
