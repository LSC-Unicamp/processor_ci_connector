`timescale 1ns / 1ps

`undef TRACE_EXECUTION
`define SYNTHESIS 1

module verification_top (
    input logic clk,  // Clock de sistema
    input logic rst_n, // Reset do sistema

    output logic        core_cyc,      // Indica uma transação ativa
    output logic        core_stb,      // Indica uma solicitação ativa
    output logic        core_we,       // 1 = Write, 0 = Read

    output logic [3:0]  core_sel,      // Seletores de byte
    output logic [31:0] core_addr,     // Endereço
    output logic [31:0] core_data_out // Dados de entrada (para escrita)

    `ifdef ENABLE_SECOND_MEMORY
,
    output logic        data_mem_cyc,
    output logic        data_mem_stb,
    output logic        data_mem_we,
    output logic [3:0]  data_mem_sel,
    output logic [31:0] data_mem_addr,
    output logic [31:0] data_mem_data_out
    `endif
);


logic [31:0] core_data_in;  // Dados de saída (para leitura)
logic        core_ack;      // Confirmação da transação

`ifdef ENABLE_SECOND_MEMORY
logic [31:0] data_mem_data_in;
logic        data_mem_ack;
`endif

processorci_top ptop (
    .sys_clk           (clk),     
    .rst_n             (rst_n),   

    .core_cyc          (core_cyc),
    .core_stb          (core_stb),
    .core_we           (core_we),
    .core_addr         (core_addr),
    .core_data_out     (core_data_out),
    .core_data_in      (core_data_in),
    .core_ack          (core_ack)

    `ifdef ENABLE_SECOND_MEMORY
    ,
    .data_mem_cyc      (data_mem_cyc),
    .data_mem_stb      (data_mem_stb),
    .data_mem_we       (data_mem_we),
    .data_mem_addr     (data_mem_addr),
    .data_mem_data_out (data_mem_data_out),
    .data_mem_data_in  (data_mem_data_in),
    .data_mem_ack      (data_mem_ack)
    `endif
);

// Instância da primeira memória
Memory #(
    .MEMORY_FILE ("/eda/processor_ci/internal/memory.hex"), // Arquivo de memória inicial
    .MEMORY_SIZE (4096)
) Memory (
    .clk    (clk),
    
    .cyc_i  (core_cyc),
    .stb_i  (core_stb),
    .we_i   (core_we),
    
    .addr_i (core_addr),
    .data_i (core_data_out),
    .data_o (core_data_in),

    .ack_o  (core_ack)
);

`ifdef ENABLE_SECOND_MEMORY
// Instância da segunda memória
Memory #(
    .MEMORY_FILE (""),
    .MEMORY_SIZE (4096)
) SecondMemory (
    .clk    (clk),
    
    .cyc_i  (data_mem_cyc),
    .stb_i  (data_mem_stb),
    .we_i   (data_mem_we),

    .addr_i (data_mem_addr),
    .data_i (data_mem_data_out),
    .data_o (data_mem_data_in),

    .ack_o  (data_mem_ack)
);
`endif

endmodule
