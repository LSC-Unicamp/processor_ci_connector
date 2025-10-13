#include <verilated.h>
#include <verilated_vcd_c.h>
#include "Vverification_top.h"

#define CLOCK_PERIOD 20 // 25 MHz -> 40 ns por ciclo
#define SIMULATION_CYCLES 4000
const uint32_t TARGET_ADDR = 60;   // Endereço que você quer monitorar
const uint32_t TARGET_DATA = 5; // Valor que você quer monitorar

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
        #ifdef ENABLE_SECOND_MEMORY
        if (top->data_mem_cyc && top->data_mem_stb && top->data_mem_we) {
            if (top->data_mem_addr == TARGET_ADDR) {
                printf("0x%08X,0x%08X,%d\n",
                            top->data_mem_addr, top->data_mem_data_out, i);
            }
        }
        #else
        if (top->core_cyc && top->core_stb && top->core_we) {
            if (top->core_addr == TARGET_ADDR) {
                printf("0x%08X,0x%08X,%d\n",
                            top->core_addr, top->core_data_out, i);
            }
        }
        #endif

        trace->dump(i * CLOCK_PERIOD);
    }
    
    trace->close();
    delete top;
    delete trace;
    return 0;
}
