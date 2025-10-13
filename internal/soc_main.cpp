#include <verilated.h>
#include <verilated_vcd_c.h>
#include "Vverification_top.h"

#define CLOCK_PERIOD 20         // 25 MHz -> 40 ns por ciclo
#define SIMULATION_CYCLES 4000  // Número total de ciclos de clock para simulação
#define TARGET_ADDR 60          // Endereço que você quer monitorar
#define TARGET_DATA 5           // Valor que você quer monitorar

int main(int argc, char **argv, char **env) {
    Verilated::commandArgs(argc, argv);
    Vverification_top *top = new Vverification_top;
    
    VerilatedVcdC *trace = new VerilatedVcdC;
    Verilated::traceEverOn(true);
    
    top->trace(trace, 100);
    trace->set_time_unit("1ns");  // Define a resolução mínima de 1ns
    trace->open("build/top.vcd");
    
    
    // Inicializa sinais
    top->clk = 0;
    top->rst_n = 0;
    
    // Reset
    int i = 0;
    for (i = 0; i < 10; i++) {
        top->clk = !top->clk;
        top->eval();
        trace->dump(i * CLOCK_PERIOD);
    }
    top->rst_n = 1;
    
    // Simulação
    for (; i < SIMULATION_CYCLES; i++) {
        top->clk = !top->clk;
        top->eval();

        // MONITORAMENTO DE MEMÓRIA
        if (top->cyc && top->stb && top->we) {
            if (top->addr == TARGET_ADDR) {
                printf("0x%08X,0x%08X,%d\n",
                            top->addr, top->data_out, i);
            }
        }

        trace->dump(i * CLOCK_PERIOD);
    }
    
    trace->close();
    delete top;
    delete trace;
    return 0;
}
