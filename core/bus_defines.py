PROTOCOLS = {
    'wishbone': {
        'signals': {
            'cyc': (1, 1),
            'stb': (1, 1),
            'we': (1, 1),
            'ack': (1, 1),
            'adr': (8, 64),  # flexível
            'dat_i': (8, 512),
            'dat_o': (8, 512),
        }
    },
    'axi4-lite': {
        'signals': {
            'awaddr': (32, 64),
            'awvalid': (1, 1),
            'awready': (1, 1),
            'wdata': (32, 512),
            'wvalid': (1, 1),
            'wready': (1, 1),
            'araddr': (32, 64),
            'arvalid': (1, 1),
            'arready': (1, 1),
            'rdata': (32, 512),
            'rvalid': (1, 1),
            'rready': (1, 1),
        }
    },
    'ahb-lite': {
        'signals': {
            'haddr': (32, 64),
            'hwrite': (1, 1),
            'htrans': (2, 2),
            'hsize': (3, 3),
            'hready': (1, 1),
            'hrdata': (32, 512),
            'hwdata': (32, 512),
        }
    },
    'apb': {
        'signals': {
            'paddr': (32, 64),
            'psel': (1, 1),
            'penable': (1, 1),
            'pwrite': (1, 1),
            'prdata': (32, 512),
            'pwdata': (32, 512),
            'pready': (1, 1),
        }
    },
    'avalon': {
        'signals': {
            'address': (32, 64),
            'write': (1, 1),
            'read': (1, 1),
            'writedata': (32, 512),
            'readdata': (32, 512),
            'waitrequest': (1, 1),
            'chipselect': (1, 1),
        }
    },
    'axi-stream': {
        'signals': {
            'tdata': (8, 1024),
            'tvalid': (1, 1),
            'tready': (1, 1),
            'tlast': (1, 1),
            'tkeep': (1, 128),
        }
    },
    'tilelink-ul': {
        'signals': {
            'a_valid': (1, 1),
            'a_ready': (1, 1),
            'a_address': (32, 64),
            'a_opcode': (3, 3),
            'a_data': (32, 512),
            'd_valid': (1, 1),
            'd_ready': (1, 1),
            'd_opcode': (3, 3),
            'd_data': (32, 512),
        }
    },
}

PROCESSOR_CI_WISHBONE_SIGNALS = [
    'core_cyc',
    'core_stb',
    'core_we',
    'core_sel',
    'core_addr',
    'core_data_out',
    'core_data_in',
    'core_ack',
    'data_mem_cyc',
    'data_mem_stb',
    'data_mem_we',
    'data_mem_sel',
    'data_mem_addr',
    'data_mem_data_out',
    'data_mem_data_in',
    'data_mem_ack',
]


ahb_adapter = """
// AHB - Instruction bus
logic [31:0] HADDR;
logic        HWRITE;
logic [2:0]  HSIZE;
logic [2:0]  HBURST;
logic        HMASTLOCK;
logic [3:0]  HPROT;
logic [1:0]  HTRANS;
logic [31:0] HWDATA;
logic [31:0] HRDATA;
logic        HREADY;
logic        HRESP;

ahb_to_wishbone #( // bus adapter
    .ADDR_WIDTH(32),
    .DATA_WIDTH(32)
) ahb2wb_inst (
    // Clock & Reset
    .HCLK       (clk_core),
    .HRESETn    (~rst_core),

    // AHB interface
    .HADDR      (HADDR),
    .HTRANS     (HTRANS),
    .HWRITE     (HWRITE),
    .HSIZE      (HSIZE),
    .HBURST     (HBURST),
    .HPROT      (HPROT),
    .HLOCK      (HMASTLOCK),
    .HWDATA     (HWDATA),
    .HREADY     (HREADY),
    .HRDATA     (HRDATA),
    .HREADYOUT  (HREADY), // normalmente igual a HREADY em designs simples
    .HRESP      (HRESP),

    // Wishbone interface
    .wb_cyc     (core_cyc),
    .wb_stb     (core_stb),
    .wb_we      (core_we),
    .wb_wstrb   (core_sel),
    .wb_adr     (core_addr),
    .wb_dat_w   (core_data_out),
    .wb_dat_r   (core_data_in),
    .wb_ack     (core_ack)
);
"""

ahb_data_adapter = """
// AHB - Data bus
// AHB - Instruction bus
logic [31:0] DATA_HADDR;
logic        DATA_HWRITE;
logic [2:0]  DATA_HSIZE;
logic [2:0]  DATA_HBURST;
logic        DATA_HMASTLOCK;
logic [3:0]  DATA_HPROT;
logic [1:0]  DATA_HTRANS;
logic [31:0] DATA_HWDATA;
logic [31:0] DATA_HRDATA;
logic        DATA_HREADY;
logic        DATA_HRESP;

ahb_to_wishbone #( // bus adapter
    .ADDR_WIDTH(32),
    .DATA_WIDTH(32)
) ahb2wb_inst (
    // Clock & Reset
    .HCLK       (clk_core),
    .HRESETn    (~rst_core),

    // AHB interface
    .HADDR      (DATA_HADDR),
    .HTRANS     (DATA_HTRANS),
    .HWRITE     (DATA_HWRITE),
    .HSIZE      (DATA_HSIZE),
    .HBURST     (DATA_HBURST),
    .HPROT      (DATA_HPROT),
    .HLOCK      (DATA_HMASTLOCK),
    .HWDATA     (DATA_HWDATA),
    .HREADY     (DATA_HREADY),
    .HRDATA     (DATA_HRDATA),
    .HREADYOUT  (DATA_HREADY), // normalmente igual a HREADY em designs simples
    .HRESP      (DATA_HRESP),

    // Wishbone interface
    .wb_cyc     (data_mem_cyc),
    .wb_stb     (data_mem_stb),
    .wb_we      (data_mem_we),
    .wb_wstrb   (data_mem_sel),
    .wb_adr     (data_mem_addr),
    .wb_dat_w   (data_mem_data_out),
    .wb_dat_r   (data_mem_data_in),
    .wb_ack     (data_mem_ack)
);
"""

axi4_lite_adapter = """
logic [31:0] AWADDR;
logic [2:0]  AWPROT;
logic        AWVALID;
logic        AWREADY;
logic [31:0] WDATA;
logic [3:0]  WSTRB;
logic        WVALID;
logic        WREADY;
logic [1:0]  BRESP;
logic        BVALID;
logic        BREADY;
logic [31:0] ARADDR;
logic [2:0]  ARPROT;
logic        ARVALID;
logic        ARREADY;
logic [31:0] RDATA;
logic [1:0]  RRESP;
logic        RVALID;
logic        RREADY;

AXI4Lite_to_Wishbone #(
    .ADDR_WIDTH           (32),
    .DATA_WIDTH           (32)
) u_AXI4Lite_to_Wishbone (
    .ACLK                 (clk_core),                      // 1 bit
    .ARESETN              (~rst_core),                     // 1 bit
    .AWADDR               (AWADDR),                        // ? bits
    .AWPROT               (AWPROT),                        // 3 bits
    .AWVALID              (AWVALID),                       // 1 bit
    .AWREADY              (AWREADY),                       // 1 bit
    .WDATA                (WDATA),                         // ? bits
    .WSTRB                (WSTRB),                         // ? bits
    .WVALID               (WVALID),                        // 1 bit
    .WREADY               (WREADY),                        // 1 bit
    .BRESP                (BRESP),                         // 2 bits
    .BVALID               (BVALID),                        // 1 bit
    .BREADY               (BREADY),                        // 1 bit
    .ARADDR               (ARADDR),                        // ? bits
    .ARPROT               (ARPROT),                        // 3 bits
    .ARVALID              (ARVALID),                       // 1 bit
    .ARREADY              (ARREADY),                       // 1 bit
    .RDATA                (RDATA),                         // ? bits
    .RRESP                (RRESP),                         // 2 bits
    .RVALID               (RVALID),                        // 1 bit
    .RREADY               (RREADY),                        // 1 bit
    .wb_adr_o             (core_addr),                     // ? bits
    .wb_dat_o             (core_data_out),                 // ? bits
    .wb_we_o              (core_we),                       // 1 bit
    .wb_stb_o             (core_stb),                      // 1 bit
    .wb_cyc_o             (core_cyc),                      // 1 bit
    .wb_sel_o             (core_sel),                      // ? bits
    .wb_dat_i             (core_data_in),                  // ? bits
    .wb_ack_i             (core_ack),                      // 1 bit
    .wb_err_i             (0),                             // 1 bit
);
"""

axi4_lite_data_adapter = """
logic [31:0] DATA_AWADDR;
logic [2:0]  DATA_AWPROT;
logic        DATA_AWVALID;
logic        DATA_AWREADY;
logic [31:0] DATA_WDATA;
logic [3:0]  DATA_WSTRB;
logic        DATA_WVALID;
logic        DATA_WREADY;
logic [1:0]  DATA_BRESP;
logic        DATA_BVALID;
logic        DATA_BREADY;
logic [31:0] DATA_ARADDR;
logic [2:0]  DATA_ARPROT;
logic        DATA_ARVALID;
logic        DATA_ARREADY;
logic [31:0] DATA_RDATA;
logic [1:0]  DATA_RRESP;
logic        DATA_RVALID;
logic        DATA_RREADY;

AXI4Lite_to_Wishbone #(
    .ADDR_WIDTH           (32),
    .DATA_WIDTH           (32)
) u_data_AXI4Lite_to_Wishbone (
    .ACLK                 (DATA_ACLK),                     // 1 bit
    .ARESETN              (DATA_ARESETN),                  // 1 bit
    .AWADDR               (DATA_AWADDR),                   // ? bits
    .AWPROT               (DATA_AWPROT),                   // 3 bits
    .AWVALID              (DATA_AWVALID),                  // 1 bit
    .AWREADY              (DATA_AWREADY),                  // 1 bit
    .WDATA                (DATA_WDATA),                    // ? bits
    .WSTRB                (DATA_WSTRB),                    // ? bits
    .WVALID               (DATA_WVALID),                   // 1 bit
    .WREADY               (DATA_WREADY),                   // 1 bit
    .BRESP                (DATA_BRESP),                    // 2 bits
    .BVALID               (DATA_BVALID),                   // 1 bit
    .BREADY               (DATA_BREADY),                   // 1 bit
    .ARADDR               (DATA_ARADDR),                   // ? bits
    .ARPROT               (DATA_ARPROT),                   // 3 bits
    .ARVALID              (DATA_ARVALID),                  // 1 bit
    .ARREADY              (DATA_ARREADY),                  // 1 bit
    .RDATA                (DATA_RDATA),                    // ? bits
    .RRESP                (DATA_RRESP),                    // 2 bits
    .RVALID               (DATA_RVALID),                   // 1 bit
    .RREADY               (DATA_RREADY),                   // 1 bit
    .wb_adr_o             (data_mem_addr),                 // ? bits
    .wb_dat_o             (data_mem_data_out),             // ? bits
    .wb_we_o              (data_mem_we),                   // 1 bit
    .wb_stb_o             (data_mem_stb),                  // 1 bit
    .wb_cyc_o             (data_mem_cyc),                  // 1 bit
    .wb_sel_o             (data_mem_sel),                  // ? bits
    .wb_dat_i             (data_mem_data_in),              // ? bits
    .wb_ack_i             (data_mem_ack),                  // 1 bit
    .wb_err_i             (0),                             // 1 bit
);
"""

axi4_adapter = """
logic [3:0]  AXI_AWID;
logic [31:0] AXI_AWADDR;
logic        AXI_AWVALID;
logic        AXI_AWREADY;
logic [3:0]  AXI_BID;
logic [1:0]  AXI_BRESP;
logic        AXI_BVALID;
logic        AXI_BREADY;
logic [3:0]  AXI_ARID;
logic [31:0] AXI_ARADDR;
logic        AXI_ARVALID;
logic        AXI_ARREADY;
logic [3:0]  AXI_RID;
logic [31:0] AXI_RDATA;
logic [1:0]  AXI_RRESP;
logic        AXI_RVALID;
logic        AXI_RREADY; 

axi4_to_wishbone_simple #(
    .ADDR_WIDTH           (32),
    .DATA_WIDTH           (32),
    .ID_WIDTH             (4)
) u_axi4_to_wishbone_simple (
    .clk                  (clk_core),                      // 1 bit
    .rst_n                (~rst_core),                     // 1 bit
    .AXI_AWID             (AXI_AWID),                      // ? bits
    .AXI_AWADDR           (AXI_AWADDR),                    // ? bits
    .AXI_AWVALID          (AXI_AWVALID),                   // 1 bit
    .AXI_AWREADY          (AXI_AWREADY),                   // 1 bit
    .AXI_WDATA            (AXI_WDATA),                     // ? bits
    .AXI_WSTRB            (AXI_WSTRB),                     // ? bits
    .AXI_WVALID           (AXI_WVALID),                    // 1 bit
    .AXI_WREADY           (AXI_WREADY),                    // 1 bit
    .AXI_BID              (AXI_BID),                       // ? bits
    .AXI_BRESP            (AXI_BRESP),                     // 2 bits
    .AXI_BVALID           (AXI_BVALID),                    // 1 bit
    .AXI_BREADY           (AXI_BREADY),                    // 1 bit
    .AXI_ARID             (AXI_ARID),                      // ? bits
    .AXI_ARADDR           (AXI_ARADDR),                    // ? bits
    .AXI_ARVALID          (AXI_ARVALID),                   // 1 bit
    .AXI_ARREADY          (AXI_ARREADY),                   // 1 bit
    .AXI_RID              (AXI_RID),                       // ? bits
    .AXI_RDATA            (AXI_RDATA),                     // ? bits
    .AXI_RRESP            (AXI_RRESP),                     // 2 bits
    .AXI_RVALID           (AXI_RVALID),                    // 1 bit
    .AXI_RREADY           (AXI_RREADY),                    // 1 bit
    .WB_CYC               (core_cyc),                      // 1 bit
    .WB_STB               (core_stb),                      // 1 bit
    .WB_WE                (core_we),                       // 1 bit
    .WB_ADDR              (core_addr),                     // ? bits
    .WB_WDATA             (core_data_out),                 // ? bits
    .WB_SEL               (core_sel),                      // ? bits
    .WB_RDATA             (core_data_in),                  // ? bits
    .WB_ACK               (core_ack),                      // 1 bit
);
"""

axi4_data_adapter = """
logic [3:0]  DATA_AXI_AWID;
logic [31:0] DATA_AXI_AWADDR;
logic        DATA_AXI_AWVALID;
logic        DATA_AXI_AWREADY;
logic [3:0]  DATA_AXI_BID;
logic [1:0]  DATA_AXI_BRESP;
logic        DATA_AXI_BVALID;
logic        DATA_AXI_BREADY;
logic [3:0]  DATA_AXI_ARID;
logic [31:0] DATA_AXI_ARADDR;
logic        DATA_AXI_ARVALID;
logic        DATA_AXI_ARREADY;
logic [3:0]  DATA_AXI_RID;
logic [31:0] DATA_AXI_RDATA;
logic [1:0]  DATA_AXI_RRESP;
logic        DATA_AXI_RVALID;
logic        DATA_AXI_RREADY; 

axi4_to_wishbone_simple #(
    .ADDR_WIDTH           (32),
    .DATA_WIDTH           (32),
    .ID_WIDTH             (4)
) u_axi4_to_wishbone_simple (
    .clk                  (clk_core),                      // 1 bit
    .rst_n                (~rst_core),                     // 1 bit
    .AXI_AWID             (DATA_AXI_AWID),                 // ? bits
    .AXI_AWADDR           (DATA_AXI_AWADDR),               // ? bits
    .AXI_AWVALID          (DATA_AXI_AWVALID),              // 1 bit
    .AXI_AWREADY          (DATA_AXI_AWREADY),              // 1 bit
    .AXI_WDATA            (DATA_AXI_WDATA),                // ? bits
    .AXI_WSTRB            (DATA_AXI_WSTRB),                // ? bits
    .AXI_WVALID           (DATA_AXI_WVALID),               // 1 bit
    .AXI_WREADY           (DATA_AXI_WREADY),               // 1 bit
    .AXI_BID              (DATA_AXI_BID),                  // ? bits
    .AXI_BRESP            (DATA_AXI_BRESP),                // 2 bits
    .AXI_BVALID           (DATA_AXI_BVALID),               // 1 bit
    .AXI_BREADY           (DATA_AXI_BREADY),               // 1 bit
    .AXI_ARID             (DATA_AXI_ARID),                 // ? bits
    .AXI_ARADDR           (DATA_AXI_ARADDR),               // ? bits
    .AXI_ARVALID          (DATA_AXI_ARVALID),              // 1 bit
    .AXI_ARREADY          (DATA_AXI_ARREADY),              // 1 bit
    .AXI_RID              (DATA_AXI_RID),                  // ? bits
    .AXI_RDATA            (DATA_AXI_RDATA),                // ? bits
    .AXI_RRESP            (DATA_AXI_RRESP),                // 2 bits
    .AXI_RVALID           (DATA_AXI_RVALID),               // 1 bit
    .AXI_RREADY           (DATA_AXI_RREADY),               // 1 bit
    .WB_CYC               (data_mem_cyc),                  // 1 bit
    .WB_STB               (data_mem_stb),                  // 1 bit
    .WB_WE                (data_mem_we),                   // 1 bit
    .WB_ADDR              (data_mem_addr),                 // ? bits
    .WB_WDATA             (data_mem_data_out),             // ? bits
    .WB_SEL               (data_mem_sel),                  // ? bits
    .WB_RDATA             (data_mem_data_in),              // ? bits
    .WB_ACK               (data_mem_ack),                  // 1 bit
);
"""
