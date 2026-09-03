# Panasonic FP Series Instruction Dataset & IL Decompiler

Dataset completo, extractor técnico y descompilador estructurado para programas en código nemónico / lista de instrucciones (IL) de PLCs **Panasonic Serie FP** (FP0, FP0H, FP0R, FP-X, FP-Sigma, FP2, FP2SH, FP10SH).

Diseñado especialmente para ingeniería inversa, migración de proyectos y enriquecimiento de contexto para **Modelos de Inteligencia Artificial (LLMs)**.

---

## 🚀 Características Principales

1. **Dataset Completo de Instrucciones:**
   - **Instrucciones Básicas (Sequence & Control):** Contactos Form A/B (`ST`, `AN`, `OR`), contactos negados (`ST/`, `AN/`, `OR/`), salidas (`OT`, `KP`, `SET`, `RST`), relés maestros (`MC`/`MCE`), saltos y subrutinas (`CALL`, `SUB`, `RET`, `JP`, `LBL`, `LOOP`).
   - **Flancos Ascendentes y Descendentes:** Detección de transiciones en manuales y software (`ST↑`, `ST↓`, `AN↑`, `AN↓`, `OR↑`, `OR↓`, `DF`, `DF/`).
   - **Instrucciones de Alto Nivel (F / P):** Aritmética entera y flotante (`F20` a `F39`, `F310` a `F336`), transferencias de datos (`F0 MV`, `F1 DMV`, `F10 BKMV`), temporizadores de 32-bit (`F183 DSTM`), comparadores (`F60 CMP`, `F61 DCMP`), corrimientos y lógicas de bits (`F101`, `F130 BTS`, `F132`, `F133`).
   - **Alias IEC de Comparación:** Resolución automática de operadores exportados por FPWIN Pro (`ST_EQ`, `AND_GT`, `ANF_LT`, `STD_GE`, etc.).

2. **Descompilador & Analizador (`src/il_parser.py`):**
   - Procesa volcados exportados de **Control FPWIN Pro** y **FPWIN GR**.
   - Soporta formato de una línea (`0 ST X0`) y formato multilínea con comentarios inline `(*...*)` y operandos en cascada.
   - Detecta y aísla subrutinas (`SUB Px ... RET` / `Px: ... RET`).
   - Mapeo **opcional de variables/tags** a partir del archivo CSV exportado desde FPWIN Pro (`DTxxxx` / `Rxxxx` -> nombres reales de variables).
   - Generación de estructura JSON estandarizada para IA.

---

## 📁 Estructura del Repositorio

```text
├── data/
│   ├── panasonic_fp_complete_dataset.json  # Base de datos completa con sintaxis, pasos y descripciones
│   ├── panasonic_fp_instructions.json      # Dataset base
│   └── acuamix_parsed.json                 # Ejemplo de volcado parseado y enriquecido
├── docs/
│   ├── FP-Series_ProgrammingManual.pdf     # Manual técnico oficial de programación FP
│   └── mn_fp0h_cpu_programming_pid_en.pdf  # Manual FP0H CPU & PID
├── src/
│   ├── il_parser.py                        # Descompilador y analizador CLI con enriquecimiento de tags
│   ├── build_full_dataset.py               # Generador del dataset consolidado
│   └── extract_fp0h_instructions.py        # Extractor desde manuales PDF
└── README.md
```

---

## 🛠️ Uso del Descompilador CLI (`il_parser.py`)

### 1. Ver Ayuda y Parámetros
```bash
python3 src/il_parser.py --help
```

### 2. Analizar un archivo de código puro (Direcciones Físicas)
```bash
python3 src/il_parser.py "/ruta/al/codigo_de_programa.txt"
```

### 3. Analizar y Mapear Tags Simbólicos desde CSV de FPWIN Pro
```bash
python3 src/il_parser.py "/ruta/al/codigo_de_programa.txt" -s "/ruta/al/archivo_variables.csv"
```
*(Nota: Si el archivo CSV está en la misma carpeta y comparte el nombre base, el descompilador lo detecta automáticamente).*

### 4. Exportar el resultado a JSON para LLMs / Procesamiento
```bash
python3 src/il_parser.py "/ruta/al/codigo_de_programa.txt" -s "/ruta/al/archivo_variables.csv" -o output_parsed.json
```

---

## 📊 Formato del JSON Generado

Cada paso del programa queda estructurado con su número de paso, nemónico normalizado, comentario del software, detalles técnicos del manual y operandos enriquecidos con su tag:

```json
{
  "step": 7,
  "raw_mnemonic": "F0",
  "resolved_mnemonic": "F0",
  "inline_comment": "MV",
  "operands": [
    {
      "raw": "K15"
    },
    {
      "raw": "DT3249",
      "tag": "Main.g_iToleranciaIngreso",
      "dtype": "INT",
      "comment": ""
    }
  ],
  "type": "high_level",
  "details": {
    "fun_no": "F0",
    "symbolic_mnemonic": "MV",
    "operands_syntax": "S, D",
    "name": "16-bit data move",
    "steps": "3",
    "category": "Data transfer instructions",
    "manual_ref": "P.3-25",
    "full_syntax": "F0 (MV) S, D"
  }
}
```

---

## 📖 Cómo Exportar desde Control FPWIN Pro

1. **Exportar Código Nemónico:**
   - Abre el nodo **Program code (Código de programa)** en el árbol del proyecto.
   - Ve a **Object -> Export program code...** y guarda como archivo `.txt`.
2. **Exportar Tabla de Variables (Tags):**
   - Ve a **Project -> Export -> Variables as CSV file -> Global variables...**
   - Guarda el archivo `.csv`.
