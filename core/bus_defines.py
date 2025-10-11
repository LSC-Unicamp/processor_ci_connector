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


ahb_adapter = """
// AHB - Instruction bus
logic [31:0] haddr;
logic        hwrite;
logic [2:0]  hsize;
logic [2:0]  hburst;
logic        hmastlock;
logic [3:0]  hprot;
logic [1:0]  htrans;
logic [31:0] hwdata;
logic [31:0] hrdata;
logic        hready;
logic        hresp;

ahb_to_wishbone #( // bus adapter
    .ADDR_WIDTH(32),
    .DATA_WIDTH(32)
) ahb2wb_inst (
    // Clock & Reset
    .HCLK       (clk_core),
    .HRESETn    (~rst_core),

    // AHB interface
    .HADDR      (haddr),
    .HTRANS     (htrans),
    .HWRITE     (hwrite),
    .HSIZE      (hsize),
    .HBURST     (hburst),
    .HPROT      (hprot),
    .HLOCK      (hmastlock),
    .HWDATA     (hwdata),
    .HREADY     (hready),
    .HRDATA     (hrdata),
    .HREADYOUT  (hready), // normalmente igual a HREADY em designs simples
    .HRESP      (hresp),

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
logic [31:0] data_haddr;
logic        data_hwrite;
logic [2:0]  data_hsize;
logic [2:0]  data_hburst;
logic        data_hmastlock;
logic [3:0]  data_hprot;
logic [1:0]  data_htrans;
logic [31:0] data_hwdata;
logic [31:0] data_hrdata;
logic        data_hready;
logic        data_hresp;

ahb_to_wishbone #( // bus adapter
    .ADDR_WIDTH(32),
    .DATA_WIDTH(32)
) ahb2wb_inst (
    // Clock & Reset
    .HCLK       (clk_core),
    .HRESETn    (~rst_core),

    // AHB interface
    .HADDR      (data_haddr),
    .HTRANS     (data_htrans),
    .HWRITE     (data_hwrite),
    .HSIZE      (data_hsize),
    .HBURST     (data_hburst),
    .HPROT      (data_hprot),
    .HLOCK      (data_hmastlock),
    .HWDATA     (data_hwdata),
    .HREADY     (data_hready),
    .HRDATA     (data_hrdata),
    .HREADYOUT  (data_hready), // normalmente igual a HREADY em designs simples
    .HRESP      (data_hresp),

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
"""

axi4_lite_data_adapter = """
"""

axi4_adapter = """
"""

axi4_data_adapter = """
"""

avalon_adapter = """
"""

avalon_data_adapter = """
"""
