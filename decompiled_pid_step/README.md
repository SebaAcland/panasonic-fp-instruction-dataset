# Decompilación & Análisis: Biblioteca Cerrada `ProcessControl_PID_Step`

Este directorio contiene la ingeniería inversa completa, el desglose mnemónico y la reconstrucción en **Texto Estructurado (IEC 61131-3 ST)** de la biblioteca protegida/cerrada de control PID paso a paso de Panasonic FP.

---

## 📂 Contenido del Directorio

* **`sub13_raw_disassembly.json`**: Desensamblado paso a paso de las 179 instrucciones nativas (`SUB 13` a `RET`) extraídas de la memoria del PLC.
* **`ProcessControl_PID_Step.st`**: Reconstrucción limpia en Texto Estructurado (ST) estándar, lista para compilar en cualquier software (FPWIN Pro, CODESYS, TwinCAT, TIA Portal).

---

## ⚙️ Estructura del DUT (`ProcessControl_PID_Step_INT_DUT`)

La estructura interna mapeada en la memoria (`DT3268` a `DT3284`) contiene los siguientes campos:

| Campo | Tipo | Ubicación Memoria | Descripción |
| :--- | :--- | :--- | :--- |
| `w_bForwardCoolingOld_bIsNotFirstScan` | `WORD` | `DT3268` | Máscara de flags (Bit 0: primer scan, Bit 1: dirección) |
| `diET` | `DINT` | `DDT3269` | Tiempo transcurrido acumulado de ejecución |
| `rPVn1` | `REAL` | `DDT3271` | Valor del proceso en el ciclo anterior ($PV_{n-1}$) |
| `rEn1` | `REAL` | `DDT3273` | Error en el ciclo anterior ($E_{n-1}$) |
| `rDn1` | `REAL` | `DDT3275` | Término derivativo filtrado del ciclo anterior ($D_{n-1}$) |
| `rMV_diff` | `REAL` | `DDT3277` | Diferencial de salida calculado ($\Delta MV$) |
| `diStepRunTime` | `DINT` | `DDT3279` | Tiempo total de pulso calculado para el paso activo |
| `diStepRunTimeRemaining`| `DINT` | `DDT3281` | Tiempo restante del pulso en ejecución |
| `iDisturbanceOld` | `INT` | `DT3283` | Valor previo de perturbación |
| `iTOld` | `INT` | `DT3284` | Tiempo de muestreo del scan previo |

---

## 🧠 Funcionamiento del Algoritmo

1. **Formato Velocidad (Incremental $\Delta MV$):**
   A diferencia de un PID de posición clásico que calcula la apertura absoluta ($0-100\%$), el **PID Step** calcula el cambio necesario de posición:
   $$\Delta MV = K_p (E_n - E_{n-1}) + K_p \frac{T_s}{T_i} E_n + D_n$$
2. **Conversión a Tiempo de Pulso:**
   Multiplica $\Delta MV$ por el tiempo total de carrera del motor para determinar cuántos milisegundos debe activarse la salida:
   $$\text{Tiempo Pulso} = |\Delta MV| \times \text{Tiempo Carrera Motor}$$
3. **Discriminación de Salidas:**
   - Si $\Delta MV > 0 \rightarrow$ Activa salida **Abrir / Adelante (FW)** durante el tiempo calculado.
   - Si $\Delta MV < 0 \rightarrow$ Activa salida **Cerrar / Reversa (RV)** durante el tiempo calculado.
   - Si el tiempo calculado es menor a `iMinPulseTime`, no conmuta los relés para evitar desgaste mecánico.
