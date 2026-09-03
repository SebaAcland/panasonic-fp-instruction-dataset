(*
 ==============================================================================
 Library Name : ProcessControl_PID_Step_INT
 Target       : IEC 61131-3 Structured Text (ST) Decompiled from Panasonic FP
 Description  : Algoritmo completo de control PID paso a paso (Step / Floating)
                diseñado para actuadores motorizados (Válvulas motorizadas,
                comportas, relés de apertura/cierre adelante-atrás).
 ==============================================================================
*)

TYPE ProcessControl_PID_Step_INT_DUT :
    STRUCT
        (* --- Flags de Control y Estado Interno --- *)
        w_bForwardCoolingOld_bIsNotFirstScan : WORD; (* Bit 0: IsNotFirstScan, Bit 1: ForwardCoolingOld *)
        
        (* --- Variables de Tiempo y Estado de Pasos (DINT / ms o ciclos) --- *)
        diET                     : DINT := 0;      (* Tiempo transcurrido de ejecución *)
        diStepRunTime            : DINT := 0;      (* Tiempo de carrera/pulso calculado para el paso actual *)
        diStepRunTimeRemaining   : DINT := 0;      (* Tiempo restante del pulso activo *)
        
        (* --- Variables Históricas en Coma Flotante (Scan n-1) --- *)
        rPVn1                    : REAL := 0.0;    (* Valor del proceso en scan anterior (PV n-1) *)
        rEn1                     : REAL := 0.0;    (* Error en scan anterior (E n-1) *)
        rDn1                     : REAL := 0.0;    (* Término derivativo en scan anterior (D n-1) *)
        rMV_diff                 : REAL := 0.0;    (* Diferencial de salida manipulada (delta MV) *)
        
        (* --- Parámetros Históricos Enteros --- *)
        iDisturbanceOld          : INT  := 0;      (* Perturbación externa anterior *)
        iTOld                    : INT  := 0;      (* Tiempo de muestreo previo *)
    END_STRUCT
END_TYPE


FUNCTION_BLOCK FB_PID_Step_INT
VAR_INPUT
    bEnable            : BOOL;    (* Habilitación del bloque PID *)
    iSP                : INT;     (* Setpoint (Consigna) *)
    iPV                : INT;     (* Process Value (Variable de Proceso) *)
    iKp                : INT;     (* Ganancia Proporcional Kp (en centésimas o factor de escala) *)
    iTi                : INT;     (* Tiempo Integral Ti (en décimas de segundo) *)
    iTd                : INT;     (* Tiempo Derivativo Td (en décimas de segundo) *)
    iTs                : INT;     (* Tiempo de Muestreo / Scan Time Ts *)
    iMotorRunTime      : INT;     (* Tiempo total de carrera completa del motor/válvula (segundos) *)
    iMinPulseTime      : INT;     (* Tiempo mínimo de pulso permitido (ms) *)
    bForwardDirection  : BOOL;    (* Dirección: TRUE = Directo / Calentamiento, FALSE = Inverso / Enfriamiento *)
END_VAR

VAR_OUTPUT
    bCmd_Open_FW       : BOOL;    (* Salida digital: Pulso Abrir / Adelante (Forward) *)
    bCmd_Close_RV      : BOOL;    (* Salida digital: Pulso Cerrar / Reversa (Reverse) *)
    bRunning           : BOOL;    (* Indicador de pulso activo en ejecución *)
    iRemainingTime     : INT;     (* Tiempo restante del pulso actual *)
END_VAR

VAR_IN_OUT
    DUT                : ProcessControl_PID_Step_INT_DUT; (* Estructura interna de persistencia *)
END_VAR

VAR
    (* Variables temporales de cálculo matemático *)
    rSP                : REAL;
    rPV                : REAL;
    rKp                : REAL;
    rTi                : REAL;
    rTd                : REAL;
    rTs                : REAL;
    rError             : REAL;
    rP_term            : REAL;
    rI_term            : REAL;
    rD_term            : REAL;
    rDeltaMV           : REAL;
    rPulseTimeCalc     : REAL;
    bIsNotFirstScan    : BOOL;
    bDirectionChanged  : BOOL;
END_VAR

(* ============================================================================== *)
(* LÓGICA DE EJECUCIÓN DEL BLOQUE                                                 *)
(* ============================================================================== *)

IF NOT bEnable THEN
    bCmd_Open_FW   := FALSE;
    bCmd_Close_RV  := FALSE;
    bRunning       := FALSE;
    iRemainingTime := 0;
    DUT.diStepRunTimeRemaining := 0;
    DUT.w_bForwardCoolingOld_bIsNotFirstScan := 16#0000; (* Reset primer scan *)
    RETURN;
END_IF;

(* 1. Extraer flags de inicialización *)
bIsNotFirstScan := (DUT.w_bForwardCoolingOld_bIsNotFirstScan AND 16#0001) <> 0;

(* 2. Conversión de entradas enteras a coma flotante para cálculo de alta precisión *)
rSP := INT_TO_REAL(iSP);
rPV := INT_TO_REAL(iPV);
rKp := INT_TO_REAL(iKp);
rTi := INT_TO_REAL(iTi);
rTd := INT_TO_REAL(iTd);
rTs := INT_TO_REAL(iTs);

(* 3. Cálculo del Error actual *)
IF bForwardDirection THEN
    rError := rSP - rPV; (* Modo Directo *)
ELSE
    rError := rPV - rSP; (* Modo Inverso *)
END_IF;

(* 4. Algoritmo PID en formato Velocidad / Incremental (Delta MV) *)
IF NOT bIsNotFirstScan THEN
    (* Primer ciclo de scan: Inicializar memorias sin salto de derivativo *)
    DUT.rPVn1 := rPV;
    DUT.rEn1  := rError;
    DUT.rDn1  := 0.0;
    rDeltaMV  := 0.0;
    DUT.w_bForwardCoolingOld_bIsNotFirstScan := DUT.w_bForwardCoolingOld_bIsNotFirstScan OR 16#0001;
ELSE
    (* Término Proporcional Incremental: Kp * (E_n - E_{n-1}) *)
    rP_term := rKp * (rError - DUT.rEn1);

    (* Término Integral Incremental: Kp * (Ts / Ti) * E_n *)
    IF rTi > 0.0 THEN
        rI_term := rKp * (rTs / rTi) * rError;
    ELSE
        rI_term := 0.0;
    END_IF;

    (* Término Derivativo Incremental con Filtro *)
    IF rTd > 0.0 AND rTs > 0.0 THEN
        rD_term := (rTd / (rTd + rTs)) * (DUT.rDn1 - rKp * (rPV - DUT.rPVn1));
    ELSE
        rD_term := 0.0;
    END_IF;

    (* Diferencial de salida total: delta_MV = P + I + D *)
    rDeltaMV := rP_term + rI_term + rD_term;
END_IF;

(* 5. Conversión de Delta MV a tiempo de accionamiento de pulso (Step Time) *)
(* Tiempo de pulso = |delta_MV| * (Tiempo total carrera motor / Rango escala) *)
IF iMotorRunTime > 0 THEN
    rPulseTimeCalc := ABS(rDeltaMV) * INT_TO_REAL(iMotorRunTime);
    DUT.diStepRunTime := REAL_TO_DINT(rPulseTimeCalc);
ELSE
    DUT.diStepRunTime := 0;
END_IF;

(* 6. Discriminación de sentido de giro y disparo de salidas *)
(* Si el tiempo de pulso supera el mínimo físico permitido *)
IF DUT.diStepRunTime >= INT_TO_DINT(iMinPulseTime) THEN
    IF rDeltaMV > 0.0 THEN
        bCmd_Open_FW  := TRUE;
        bCmd_Close_RV := FALSE;
    ELSIF rDeltaMV < 0.0 THEN
        bCmd_Open_FW  := FALSE;
        bCmd_Close_RV := TRUE;
    ELSE
        bCmd_Open_FW  := FALSE;
        bCmd_Close_RV := FALSE;
    END_IF;
    bRunning := TRUE;
    DUT.diStepRunTimeRemaining := DUT.diStepRunTime;
ELSE
    bCmd_Open_FW  := FALSE;
    bCmd_Close_RV := FALSE;
    bRunning      := FALSE;
    DUT.diStepRunTimeRemaining := 0;
END_IF;

(* 7. Actualización de memorias para el siguiente scan (Scan n-1) *)
DUT.rPVn1 := rPV;
DUT.rEn1  := rError;
DUT.rDn1  := rD_term;
DUT.rMV_diff := rDeltaMV;
iRemainingTime := DINT_TO_INT(DUT.diStepRunTimeRemaining);

END_FUNCTION_BLOCK
