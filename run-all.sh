#!/bin/bash
. env/bin/activate

CORES=("riskow" "Grande-Risco-5" "tinyriscv" "rvx" "rpu" "darkriscv" "kronos" "SuperScalar-RISCV-CPU" \
       "riscado-v" "Risco-5" "Baby-Risco-5" "nerv" "airisc_core_complex" "picorv32" \
       "riscv" "Hazard3" "leaf" "zero-riscy" "RPU" "fedar-f1-rv64im" "harv" "mor1kx" \
       "potato" "riscv-atom" "Sprintrv" "mriscv" "rv3n" "cve2" "RS5" "serv" "VexRiscv")
#riscv, rpu , zero-riscy, leaf, kronos, sprintrv, VexRiscv, rs5

LOG_DIR=logs
mkdir -p "$LOG_DIR"

for core in "${CORES[@]}"; do
    echo "Processing core: $core"
    python main.py -p "$core" -P "/eda/processadores/$core" -n 0 -m gpt-oss:20b -v > "$LOG_DIR/$core.log" 2>&1
    if [ $? -ne 0 ]; then
        echo "Error processing core: $core. Check the log file $LOG_DIR/$core.log for details."
    else
        echo "Successfully processed core: $core"
    fi
done
