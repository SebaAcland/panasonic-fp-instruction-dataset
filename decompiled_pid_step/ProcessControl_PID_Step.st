(*
 ==============================================================================
 Library Name : ProcessControl_PID_Step_INT (Copia Fiel Exacta 1:1)
 Target       : IEC 61131-3 Structured Text (ST)
 Source       : Descompilación de SUB 13 (Pasos 1157 a 1335) de Panasonic FP
 Description  : Algoritmo de control PID paso a paso (Step / Floating)
                incorporando la lectura del temporizador de hardware DT90019 (1ms),
                acumulador delta diET (DT3374), filtro derivativo con polo Ti/4,
                detección de inversión por XOR, clamping de carrera y empaquetado de DUT.
 ==============================================================================
*)

TYPE ProcessControl_PID_Step_INT_DUT :
    STRUCT
        (* DT3268: Bit 0 = IsNotFirstScan, Bit 1 = ForwardDirectionOld *)
        w_bForwardCoolingOld_bIsNotFirstScan : WORD := 16#0000;
        
        (* DDT3269: Tiempo acumulado de integración/ejecución (ms) *)
        diET                     : DINT := 0;
        
        (* DDT3271: PV en scan anterior (PV n-1) *)
        rPVn1                    : REAL := 0.0;
        
        (* DDT3273: Error en scan anterior (E n-1) *)
        rEn1                     : REAL := 0.0;
        
        (* DDT3275: Término derivativo en scan anterior (D n-1) *)
        rDn1                     : REAL := 0.0;
        
        (* DDT3277: Diferencial de salida manipulada (delta MV) *)
        rMV_diff                 : REAL := 0.0;
        
        (* DDT3279: Tiempo total de pulso calculado para el paso actual *)
        diStepRunTime            : DINT := 0;
        
        (* DDT3281: Tiempo restante del pulso activo *)
        diStepRunTimeRemaining   : DINT := 0;
        
        (* DT3283: Perturbación anterior *)
        iDisturbanceOld          : INT  := 0;
        
        (* DT3284: Timestamp de scan previo (DT90019 n-1) *)
        iTOld                    : INT  := 0;
    END_STRUCT
END_TYPE


FUNCTION_BLOCK FB_PID_Step_INT
VAR_INPUT
    bEnable            : BOOL;    (* Habilitación del bloque PID *)
    iSP                : INT;     (* Setpoint (Consigna) *)
    iPV                : INT;     (* Process Value (Variable de Proceso) *)
    iKp                : INT;     (* Ganancia Proporcional Kp *)
    iTi                : INT;     (* Tiempo Integral Ti *)
    iTd                : INT;     (* Tiempo Derivativo Td *)
    iTs                : INT;     (* Tiempo de Muestreo Ts *)
    iMotorRunTime      : INT;     (* Tiempo total de carrera del motor/válvula *)
    iMinPulseTime      : INT;     (* Tiempo mínimo de pulso permitido *)
    bForwardDirection  : BOOL;    (* TRUE = Directo / Calentamiento, FALSE = Inverso / Enfriamiento *)
    iCurrentTimer_ms   : INT;     (* Lectura actual del reloj de hardware (Equivalente a DT90019 en Panasonic) *)
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
    (* Registros de trabajo temporal 32-bit (Equivalentes a DT3417..DT3473) *)
    diDeltaTime_ms     : DINT;    (* DT3415: DT90019 actual - DT3389 previo *)
    diTs_x4            : DINT;    (* DT3417 = Ts * 4 *)
    diTi_x4            : DINT;    (* DT3419 = Ti * 4 *)
    diMotorRun_x4      : DINT;    (* DT3421 = MotorRunTime * 4 *)
    diMinPulse_x4      : DINT;    (* DT3425 = MinPulseTime * 4 *)
    diSampling_x4      : DINT;    (* DT3427 = Sampling * 4 *)
    
    (* Variables en coma flotante (Equivalentes a DT3430..DT3471) *)
    rSP                : REAL;    (* DT3430 = FLT(iSP) *)
    rPV                : REAL;    (* DT3432 = FLT(iPV) *)
    rKp                : REAL;    (* DT3358 = FLT(iKp) *)
    rTi_f              : REAL;    (* DT3395 = FLT(diTi_x4) *)
    rTs_f              : REAL;    (* DT3393 = FLT(diTs_x4) *)
    rError             : REAL;    (* DT3411 = Error actual *)
    rP_term            : REAL;    (* DT3409 = Término proporcional *)
    rI_term            : REAL;    (* DT3403 = Término integral *)
    rD_term            : REAL;    (* DT3401 = Término derivativo filtrado *)
    rDeltaMV           : REAL;    (* DT3405 = delta_MV total *)
    rDeltaMV_prev      : REAL;    (* DT3382 = delta_MV previo *)
    rAbsDeltaMV        : REAL;    (* DT3469 = FABS(delta_MV) *)
    rPulseCalc         : REAL;    (* DT3471 = Cálculo de pulso *)
    
    (* Flags booleanas internas (Equivalentes a R500..R58C) *)
    bIsNotFirstScan    : BOOL;    (* R58B / Bit 0 de DT3373 *)
    bDirCurrentSign    : BOOL;    (* R508: rDeltaMV > 0.0 *)
    bDirPrevSign       : BOOL;    (* R509: rDeltaMV_prev > 0.0 *)
    bDirectionChanged  : BOOL;    (* R54B: XOR entre bDirCurrentSign y bDirPrevSign *)
    diPulseSteps_x4    : DINT;    (* DT3384: Pulso en unidades x4 *)
    diAccumResidual_x4 : DINT;    (* DT3386: Pulso acumulado residual *)
    diMaxAllowed_x4    : DINT;    (* DT3469: DT3421 - DT3425 *)
END_VAR

(* ============================================================================== *)
(* INICIO DE EJECUCIÓN (SUB 13)                                                    *)
(* ============================================================================== *)

IF NOT bEnable THEN
    bCmd_Open_FW   := FALSE;
    bCmd_Close_RV  := FALSE;
    bRunning       := FALSE;
    iRemainingTime := 0;
    DUT.diStepRunTimeRemaining := 0;
    DUT.w_bForwardCoolingOld_bIsNotFirstScan := 16#0000;
    DUT.iTOld      := iCurrentTimer_ms;
    RETURN;
END_IF;

(* Paso 1166-1171: Extracción de Flags de inicialización *)
bIsNotFirstScan := (DUT.w_bForwardCoolingOld_bIsNotFirstScan AND 16#0001) <> 0;

(* Pasos 1174-1182: Escalado de Tiempos por K4 y Protecciones Anti-División por Cero *)
diTs_x4       := INT_TO_DINT(iTs) * 4;
diTi_x4       := INT_TO_DINT(iTi) * 4;
diMotorRun_x4 := INT_TO_DINT(iMotorRunTime) * 4;
IF diMotorRun_x4 < 1 THEN
    diMotorRun_x4 := 1; (* Protección Paso 1177-1178: STD> K1 *)
END_IF;

diMinPulse_x4 := INT_TO_DINT(iMinPulseTime) * 4;
IF diMinPulse_x4 < 4 THEN
    diMinPulse_x4 := 4; (* Protección Paso 1181-1182: STD> K4 *)
END_IF;

(* Pasos 1192-1197: Cálculo de delta de tiempo transcurrido con temporizador de 1ms *)
diDeltaTime_ms := INT_TO_DINT(iCurrentTimer_ms - DUT.iTOld);
IF diDeltaTime_ms < 0 THEN
    diDeltaTime_ms := diDeltaTime_ms + 65536; (* Manejo de overflow en timer 16-bit *)
END_IF;
DUT.diET  := DUT.diET + diDeltaTime_ms;
DUT.iTOld := iCurrentTimer_ms;

(* Pasos 1162-1165 / 1184-1185: Conversiones a punto flotante (FLT) *)
rSP   := INT_TO_REAL(iSP);
rPV   := INT_TO_REAL(iPV);
rKp   := INT_TO_REAL(iKp);
rTs_f := DINT_TO_REAL(diTs_x4);
rTi_f := DINT_TO_REAL(diTi_x4);

(* Pasos 1196-1210: Cálculo del Error según sentido de operación *)
IF bForwardDirection THEN
    rError := rSP - rPV;
ELSE
    rError := rPV - rSP;
END_IF;

(* Pasos 1211-1270: Ecuación PID Incremental (Delta MV) *)
IF NOT bIsNotFirstScan THEN
    (* Primer scan: Inicialización de memorias a cero *)
    DUT.rPVn1     := rPV;
    DUT.rEn1      := rError;
    DUT.rDn1      := 0.0;
    rDeltaMV      := 0.0;
    rDeltaMV_prev := 0.0;
    diAccumResidual_x4 := 0;
    DUT.diET      := 0;
ELSE
    rDeltaMV_prev := DUT.rMV_diff;

    (* Término Proporcional Incremental *)
    rP_term := rError - DUT.rEn1;

    (* Término Integral Incremental *)
    IF diTi_x4 <> 0 THEN
        rI_term := (rError * rTs_f) / rTi_f;
    ELSE
        rI_term := 0.0;
    END_IF;

    (* Término Derivativo Incremental Filtrado *)
    IF diTi_x4 <> 0 AND (rTs_f + (rTi_f / 4.0)) <> 0.0 THEN
        rD_term := ( (rKp * (rTi_f / 4.0) * (rError - DUT.rEn1)) - (rTs_f * DUT.rDn1) ) / (rTs_f + (rTi_f / 4.0));
    ELSE
        rD_term := 0.0;
    END_IF;

    (* delta_MV Total *)
    rDeltaMV := rKp * (rP_term + rI_term) + rD_term;
END_IF;

(* Pasos 1252-1269: Detección de Inversión de Sentido por Circuito Lógico XOR *)
bDirCurrentSign := rDeltaMV > 0.0;
bDirPrevSign    := rDeltaMV_prev > 0.0;
bDirectionChanged := (bDirCurrentSign AND NOT bDirPrevSign) OR (NOT bDirCurrentSign AND bDirPrevSign);

(* Si la dirección cambió, resetea el tiempo acumulado residual *)
IF bDirectionChanged THEN
    diAccumResidual_x4 := 0;
END_IF;

(* Pasos 1272-1276: Cálculo de Tiempo de Pulso con FABS y Redondeo DROFF *)
rAbsDeltaMV := ABS(rDeltaMV);
rPulseCalc  := rAbsDeltaMV * DINT_TO_REAL(diMotorRun_x4);
diPulseSteps_x4 := diAccumResidual_x4 + REAL_TO_DINT(rPulseCalc);

(* Pasos 1278-1280: Clamping de Fin de Carrera / Pulso Máximo *)
diMaxAllowed_x4 := diMotorRun_x4 - diMinPulse_x4;
IF diPulseSteps_x4 >= diMaxAllowed_x4 THEN
    diPulseSteps_x4 := diMaxAllowed_x4;
END_IF;

(* Pasos 1286-1294: Verificación contra Tiempo Mínimo de Pulso *)
IF diPulseSteps_x4 > diMinPulse_x4 THEN
    diAccumResidual_x4 := diPulseSteps_x4 - diMinPulse_x4;
    IF diAccumResidual_x4 < 0 THEN
        diAccumResidual_x4 := 0; (* Protección contra signo negativo Paso 1291-1293 *)
    END_IF;
    
    (* Pasos 1295-1299: Disparo de Salidas Forward / Reverse *)
    IF rDeltaMV > 0.0 THEN
        bCmd_Open_FW  := TRUE;
        bCmd_Close_RV := FALSE;
    ELSE
        bCmd_Open_FW  := FALSE;
        bCmd_Close_RV := TRUE;
    END_IF;
    bRunning := TRUE;
ELSE
    bCmd_Open_FW  := FALSE;
    bCmd_Close_RV := FALSE;
    bRunning      := FALSE;
END_IF;

(* Pasos 1314-1317: Interlock de Seguridad Anti-Overlap de Hardware *)
IF bCmd_Open_FW AND bCmd_Close_RV THEN
    bCmd_Open_FW  := FALSE;
    bCmd_Close_RV := FALSE;
    bRunning      := FALSE;
END_IF;

(* Paso 1319-1320: Desescalado dividiendo por K4 (DDIV) *)
DUT.diStepRunTime          := diPulseSteps_x4 / 4;
DUT.diStepRunTimeRemaining := DUT.diStepRunTime;
iRemainingTime             := DINT_TO_INT(DUT.diStepRunTimeRemaining);

(* Pasos 1321-1335: Actualización de Memorias en el DUT *)
DUT.rPVn1    := rPV;
DUT.rEn1     := rError;
DUT.rDn1     := rD_term;
DUT.rMV_diff := rDeltaMV;

(* Empaquetado de Flags en Palabra w_bForwardCoolingOld_bIsNotFirstScan *)
DUT.w_bForwardCoolingOld_bIsNotFirstScan := 16#0000;
DUT.w_bForwardCoolingOld_bIsNotFirstScan := DUT.w_bForwardCoolingOld_bIsNotFirstScan OR 16#0001; (* Bit 0: IsNotFirstScan = TRUE *)
IF bForwardDirection THEN
    DUT.w_bForwardCoolingOld_bIsNotFirstScan := DUT.w_bForwardCoolingOld_bIsNotFirstScan OR 16#0002; (* Bit 1: Forward = TRUE *)
END_IF;

END_FUNCTION_BLOCK
