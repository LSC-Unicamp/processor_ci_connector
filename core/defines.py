CONTROLLER_SIGNALS_NON_OPEN = {
    'core_data_out': '0',
    'core_stb': '1',
    'core_cyc': '1',
    'core_we': '0',
}

OUTPUT_SIGNALS = {
    'core_ack',
    'core_data_in',
    'data_mem_ack',
    'data_mem_data_in',
}

DATA_MEM_SIGNALS_NON_OPEN = {
    'data_mem_data_out': '0',
    'data_mem_stb': '0',
    'data_mem_cyc': '0',
    'data_mem_we': '0',
}

TYPE_WORDS = {
    'reg',
    'wire',
    'logic',
    'signed',
    'unsigned',
    'integer',
    'bit',
    'byte',
    'int',
    'shortint',
}

OPERATORS = {
    '==',
    '!=',
    '===',
    '!==',
    '<=',
    '>=',
    '&&',
    '||',
    '<<',
    '>>',
    '+',
    '-',
    '*',
    '/',
    '%',
    '&',
    '|',
    '^',
    '~',
    '!',
    '<',
    '>',
    '=',
    ',',
}
