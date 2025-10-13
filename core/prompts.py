find_interface_prompt = """You are an expert in hardware design and SoC integration. 
Your task is to analyze a HDL module and identify the memory bus interface(s).

The possible bus types are: AHB, AXI, Avalon, Wishbone, or Custom.

You are provided:
1. A dictionary of known bus signals (required and optional) for each bus type.
2. The module declaration (with ports and comments).

Steps:
1. Compare the module’s signals against the dictionary of required/optional signals.
2. Allow for alternate names (e.g. "rw_address" ~= "adr", "write_request" ~= "write").
3. Use comments in the code if they mention the interface (e.g. "AHB master port").
4. Determine whether the processor exposes:
   - A single unified memory interface (shared instruction and data access).
   - Two separate memory interfaces (one for instruction fetch, one for data).
   Look for clues such as signal names containing "instr", "pc", "imem", "fetch", "idata" for instructions, and "data", "dmem", "store", "load" for data.
5. Validate signals against the true semantics of each bus standard before assigning confidence:
   - Both the name and the function must match (timing, purpose, driver). 
   - Check that the signal’s bit-width and input/output direction are consistent with the bus specification.
   - Treat `cyc` and `stb` signals from a Wishbone interface as potentially merged into a single signal (e.g., read_request can represent cyc & stb).
   - For Avalon interfaces, prefer mappings where separate `read` and `write` signals exist.
6. Decide which bus type(s) the module most closely matches.
7. If fewer than 70% of the required signals of any bus match, classify as "Custom" with Low confidence. 
Provide your reasoning first (step-by-step analysis following Steps 1–7), and then give the final structured result in the required JSON format:
{{
  "bus_type": One of [AHB, AXI, Avalon, Wishbone, Custom]
  "memory_interface": Single or Dual
}}

Dictionary of bus signals:
{{
    "Wishbone": {{
    "required": ["adr", "dat_i", "dat_o", "we", "cyc", "stb", "ack"],
    "optional": ["sel", "err", "rty", "stall"]
    }},

    "Avalon": {{
    "required": ["waitrequest", "address", "read", "readdata", "write", "writedata"],
    "optional": ["byteenable", "burstcount", "readdatavalid", "response", "chipselect"]
    }},

    "AXI": {{
    "required": ["araddr", "arvalid", "arready", "rdata", "rvalid", "rready",
                "awaddr", "awvalid", "awready", "wdata", "wvalid", "wready",
                "bresp", "bvalid", "bready"],
    "optional": ["arsize", "arburst", "arlen", "arprot", "arcache",
                "awsize", "awburst", "awlen", "awprot", "awcache",
                "wstrb", "wlast", "rlast"]
    }},

    "AHB": {{
    "required": ["haddr", "hwrite", "htrans", "hsize", "hready", "hresp"],
    "optional": ["hburst", "hprot", "hmastlock", "hmaster", "hexcl", "hexokay", "hwdata", "hrdata"]
    }}
}}

Module declaration:
{core_declaration}
"""

wishbone_prompt = """You are a hardware engineer. Your task is to connect a processor interface to a wrapper interface following the rules of a Wishbone memory-mapped bus. You will be given:

1. A processor interface (Verilog/VHDL module).
2. A wrapper interface (Verilog/VHDL module).
3. The Wishbone specification with required and optional signals.
4. Information about single or dual memory interfaces.

Your task has two parts:

---
**Part 1: Indentify dual memory interfaces**
- Identify which interface is the instruction interface and which is the data interface.
- Use the name of the signals to perform this. Look for keywords such as "instr", "pc", "data".

**Part 2: Map signals to the wrapper**

- Use comments in the code if they mention the interface (e.g. "AHB master port")
- Match inputs to inputs and outputs to outputs.
- Connect signals with the same bit width.
- Use the Wishbone mapping:
    "Wishbone": {{
        "required": ["adr", "dat_i", "dat_o", "we", "cyc", "stb", "ack"],
        "optional": ["sel", "err", "rty", "stall"]
    }}
- Allow for alternate names (e.g. "rw_address" ~= "adr", "write_request" ~= "write")
- If needed, generate expressions to convert signals (e.g., `"core_we": "wstrb != 0"`, `"core_stb & core_cyc": "read_request | write_request"`)
- If the sel signal is missing, complete it with "4'b1111".
- If an input signal is missing (e.g. ack) leave it open using `null`
- Treat `cyc` and `stb` signals from a Wishbone interface as potentially merged into a single signal (e.g., read_request can represent cyc & stb). 
- Use the results of part 1 to fill the memory interfaces. In case of single interface, leave data-memory signals (data_mem_*) unconnected (use `null`).
- Associate instruction bus signals to `core_*` and data bus signals to `data_mem_*` (if dual memory interface), use the part 1 results.

Example JSON format:
{{
  "core_cyc": "cyc_o",
  "core_stb": "stb_o",
  "core_we": "we_o",
  "core_addr": "addr_o",
  "core_data_out": "data_o",
  "core_data_in": "data_i",
  "core_ack": "ack_i",
  "core_sel": "4'b1111",
  "data_mem_cyc": null,
  ...
}}

---

Wrapper interface:
module processorci_top (
    input logic sys_clk, // Clock de sistema
    input logic rst_n,   // Reset do sistema

    `ifndef SIMULATION
    // UART pins
    input  logic rx,
    output logic tx,

    // SPI pins
    input  logic sck,
    input  logic cs,
    input  logic mosi,
    output logic miso,

    //SPI control pins
    input  logic rw,
    output logic intr

    `else
    output logic        core_cyc,      // Indica uma transação ativa
    output logic        core_stb,      // Indica uma solicitação ativa
    output logic        core_we,       // 1 = Write, 0 = Read

    output logic [31:0] core_addr,     // Endereço
    output logic [3:0]  core_sel,     // Máscara de escrita (byte enable)
    output logic [31:0] core_data_out, // Dados de entrada (para escrita)
    input  logic [31:0] core_data_in,  // Dados de saída (para leitura)

    input  logic        core_ack       // Confirmação da transação

    `ifdef ENABLE_SECOND_MEMORY
,
    output logic        data_mem_cyc,
    output logic        data_mem_stb,
    output logic        data_mem_we,
    output logic [3:0]  data_mem_sel,
    output logic [31:0] data_mem_addr,
    output logic [31:0] data_mem_data_out,
    input  logic [31:0] data_mem_data_in,
    input  logic        data_mem_ack
    `endif

    `endif
);

logic clk_core, rst_core;
`ifdef SIMULATION
assign clk_core = sys_clk;
assign rst_core = ~rst_n;
`else

Processor interface:

{processor_interface}

Memory interface: {memory_interface}

---

**Final output format**

You must first give your reasoning and then output the json in this format:

```
Connections:
{{
    "sys_clk" : "clk",
    ...
}}
```
"""

############################################################################

ahb_prompt = """You are a hardware engineer. Your task is to connect a processor interface to a wrapper interface following the rules of a Wishbone memory-mapped bus. You will be given:

1. A processor interface (Verilog/VHDL module).
2. A adapter interface (Verilog/VHDL module).
3. The AHB specification with required and optional signals.
4. Information about single or dual memory interfaces.

Your task has two parts:

---

**Part 1: Map signals to the adapter**

- Create a JSON where the key is the adapter signal and the value is the processor signal or an expression to generate it.
- It's a connection: match processor outputs to adapter inputs and vice-versa.
- Use comments in the code if they mention the interface (e.g. "AHB master port")
- Both the name and the function must match (timing, purpose, driver).
- Connect signals with the same bit width.
- Use the AHB mapping:
    "AHB": {{
    "required": ["haddr", "hwrite", "htrans", "hsize", "hready", "hresp"],
    "optional": ["hburst", "hprot", "hmastlock", "hmaster", "hexcl", "hexokay", "hwdata", "hrdata"]
    }}
- Allow for alternate names (e.g. "rw_address" ~= "adr", "write_request" ~= "write").
- If an input signal is missing (e.g. ack) leave it open using `null`
- Check the reset signal polarity and invert if needed (e.g. "rst_n": "!reset").
- If there is a dual memory interface, consider two adapters and put a prefix (adapter_instr or adapter_data) before the AHB signal.

Example format:
{{
  "haddr": "HADDR",
  "hwrite": "HWRITE",
  "htrans": "HTRANS",
  "hsize": "HSIZE",
  "hburst": "HBURST",
  "hprot": "HPROT",
  "hmastlock": "HMASTLOCK",
  "hexcl": "HEXCL",
  "hready": "HREADY",
  "hresp": "HRESP",
  "hexokay": "HEXOKAY",
  "hwdata": "HWDATA",
  "hrdata": "HRDATA",
  ...
}}
or
{{
  "haddr": "haddr",
  "htrans": "htrans",
  "hwrite": "hwrite",
  "hsize": "hsize",
  "hburst": "hburst",
  "hprot": "hprot",
  "hmastlock": "hlock",
  "hwdata": "hwdata",
  "hready": "hready",
  "hrdata": "hrdata",
  "hreadyout": "hreadyout",
  "hresp": "hresp",
    ...
}}

---

Adapter interface:
module ahb_to_wishbone #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    input logic                   HCLK,
    input logic                   HRESETn,

    // AHB Interface
    input  logic [ADDR_WIDTH-1:0] HADDR,
    input  logic [1:0]            HTRANS,
    input  logic                  HWRITE,
    input  logic [2:0]            HSIZE,
    input  logic [2:0]            HBURST,
    input  logic [3:0]            HPROT,
    input  logic                  HLOCK,
    input  logic [DATA_WIDTH-1:0] HWDATA,
    input  logic                  HREADY,
    output logic [DATA_WIDTH-1:0] HRDATA,
    output logic                  HREADYOUT,
    output logic [1:0]            HRESP,

    // Wishbone Interface
    output logic                  wb_cyc,
    output logic                  wb_stb,
    output logic                  wb_we,
    output logic [3:0]            wb_wstrb,
    output logic [ADDR_WIDTH-1:0] wb_adr,
    output logic [DATA_WIDTH-1:0] wb_dat_w,
    input  logic [DATA_WIDTH-1:0] wb_dat_r,
    input  logic                  wb_ack
);

- For dual memory interface, second memory adapter use DATA_ prefix in signal names (e.g., DATA_HADDR, DATA_HWRITE, ...)

Processor interface:

{processor_interface}

Memory interface: {memory_interface}

---

**Final output format**

You must first give your reasoning and then output the json in this format:

```
Connections:
{{
    "clk_core" : "clk",
    ...
}}
```
"""

############################################################################

axi_prompt = """You are a hardware engineer. Your task is to connect a processor interface to a wrapper interface following the rules of a Wishbone memory-mapped bus. You will be given:

1. A processor interface (Verilog/VHDL module).
2. A adapter interface (Verilog/VHDL module).
3. The AHB specification with required and optional signals.
4. Information about single or dual memory interfaces.

Your task has two parts:

---

**Part 1: Map signals to the adapter**

- Create a JSON where the key is the adapter signal and the value is the processor signal or an expression to generate it.
- It's a connection: match processor outputs to adapter inputs and vice-versa.
- Use comments in the code if they mention the interface (e.g. "AHB master port")
- Both the name and the function must match (timing, purpose, driver).
- Connect signals with the same bit width.
- Use the AXI mapping:
    "AXI": {{
    "required": ["araddr", "arvalid", "arready", "rdata", "rvalid", "rready",
                "awaddr", "awvalid", "awready", "wdata", "wvalid", "wready",
                "bresp", "bvalid", "bready"],
    "optional": ["arsize", "arburst", "arlen", "arprot", "arcache",
                "awsize", "awburst", "awlen", "awprot", "awcache",
                "wstrb", "wlast", "rlast"]
    }}
- Allow for alternate names (e.g. "rw_address" ~= "adr", "write_request" ~= "write").
- Check the reset signal polarity and invert if needed (e.g. "rst_n": "!reset").
- If there is a dual memory interface, consider two adapters and put a prefix (adapter_instr or adapter_data) before the AXI signal.

Example format:
{{
  "clk_core": "clk",
  "!rst_core": "reset_n",
  "awaddr": "s_awaddr",
  ...
}}
or
{{
  "clk_core": "HCLK",
  "!rst_core": "HRESETn",
  "adapter_instr_awaddr": "instr_mem_awaddr",
  "adapter_data_awaddr": "data_mem_awaddr",
  ...
}}

---

Adapter interface:
module AXI4Lite_to_Wishbone #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    input  logic                  ACLK,
    input  logic                  ARESETN,

    // AXI4-Lite Slave Interface
    input  logic [ADDR_WIDTH-1:0] AWADDR,
    input  logic [2:0]            AWPROT,
    input  logic                  AWVALID,
    output logic                  AWREADY,

    input  logic [DATA_WIDTH-1:0] WDATA,
    input  logic [(DATA_WIDTH/8)-1:0] WSTRB,
    input  logic                  WVALID,
    output logic                  WREADY,

    output logic [1:0]            BRESP,
    output logic                  BVALID,
    input  logic                  BREADY,

    input  logic [ADDR_WIDTH-1:0] ARADDR,
    input  logic [2:0]            ARPROT,
    input  logic                  ARVALID,
    output logic                  ARREADY,

    output logic [DATA_WIDTH-1:0] RDATA,
    output logic [1:0]            RRESP,
    output logic                  RVALID,
    input  logic                  RREADY,

    // Wishbone Master Interface
    output logic [ADDR_WIDTH-1:0] wb_adr_o,
    output logic [DATA_WIDTH-1:0] wb_dat_o,
    output logic                  wb_we_o,
    output logic                  wb_stb_o,
    output logic                  wb_cyc_o,
    output logic [(DATA_WIDTH/8)-1:0] wb_sel_o,
    input  logic [DATA_WIDTH-1:0] wb_dat_i,
    input  logic                  wb_ack_i,
    input  logic                  wb_err_i
);

- For dual memory interface, second memory adapter use DATA_ prefix in signal names (e.g., DATA_AWADDR, DATA_AWPROT, ...)

Processor interface:

{processor_interface}

Memory interface: {memory_interface}

---

**Final output format**

You must first give your reasoning and then output the json in this format:

```
Connections:
{{
    "clk_core" : "clk",
    ...
}}
```
"""
