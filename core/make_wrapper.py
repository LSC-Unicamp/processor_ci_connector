import os
import re
import logging
from core import TEMPLATES_DIR
from core.defines import (
    CONTROLLER_SIGNALS_NON_OPEN,
    DATA_MEM_SIGNALS_NON_OPEN,
    TYPE_WORDS,
    OPERATORS,
    OUTPUT_SIGNALS,
)
from core.bus_defines import PROCESSOR_CI_WISHBONE_SIGNALS
from jinja2 import Environment, FileSystemLoader
from core.bus_defines import (
    ahb_adapter,
    ahb_data_adapter,
    axi4_adapter,
    axi4_data_adapter,
    axi4_lite_adapter,
    axi4_lite_data_adapter,
)

logger = logging.getLogger(__name__)


def is_identifier(tok):
    return bool(re.match(r'^[A-Za-z_]\w*$', tok))


def clean_token(tok):
    # remove leading/trailing whitespace
    tok = tok.strip()
    tok = tok.replace('(', '')
    tok = tok.replace(')', '')
    tok = tok.replace('[', '')
    tok = tok.replace(']', '')
    tok = tok.replace('{', '')
    tok = tok.replace('}', '')
    tok = tok.replace(';', '')
    return tok


def get_signals_to_create(expression: str):
    # split using operators as delimiters defineds in OPERATORS
    pattern = r'(' + '|'.join(re.escape(op) for op in OPERATORS) + r')'
    tokens = re.split(pattern, expression)

    tokens = [clean_token(tok) for tok in tokens]

    # remove whitespace and filter out empty tokens
    tokens = [tok.strip() for tok in tokens if is_identifier(tok)]
    return tokens


def create_signals_to_declare(signal_list, ports) -> str:
    """Gera declarações 'logic' para sinais com base em lista de sinais e portas (direction, name, width)."""
    # Mapeia nome da porta para largura
    port_widths = {p[1]: p[2] for p in ports}

    lines = []
    for signal in signal_list:
        width = port_widths.get(signal, 0)
        if width <= 1:
            lines.append(f'logic {signal};')
        else:
            lines.append(f'logic [{width-1}:0] {signal};')

    return '\n'.join(lines) + '\n'


def parse_parameters(params_block: str):
    """Extrai parâmetros de um bloco #( ... ) tolerando expressões complexas."""
    params = []
    if not params_block:
        return params

    # divide o bloco em "declarações de parâmetro" no nível superior
    param_entries = re.findall(
        r'parameter\s+[^,()]+(?:,[^,()]+)*', params_block, re.DOTALL
    )
    if not param_entries:  # fallback simples
        param_entries = params_block.split(',')

    for entry in param_entries:
        m = re.match(
            r'\s*parameter\s+([A-Za-z_]\w*)\s*=\s*(.+)', entry.strip()
        )
        if not m:
            continue
        name = m.group(1).strip()
        value = m.group(2).strip().rstrip(',')  # remove vírgulas de separação

        # balanceamento básico de {}
        if value.count('{') != value.count('}'):
            value = '0'
        elif '{' in value and '}' in value:
            # ainda pode ter concatenação complexa, protege
            if re.search(r'\{.*\{.*\}.*\}', value):  # nested braces
                value = '0'

        params.append((name, value))
    return params


def _split_top_level_commas(s: str):
    """Divide por vírgulas de nível superior (ignora vírgulas dentro de colchetes/parênteses/strings)."""
    parts, cur = [], []
    depth_paren = depth_brack = 0
    in_squote = in_dquote = esc = False
    for ch in s:
        if esc:
            cur.append(ch)
            esc = False
            continue
        if ch == '\\':
            cur.append(ch)
            esc = True
            continue
        if ch == "'" and not in_dquote:
            in_squote = not in_squote
            cur.append(ch)
            continue
        if ch == '"' and not in_squote:
            in_dquote = not in_dquote
            cur.append(ch)
            continue
        if in_squote or in_dquote:
            cur.append(ch)
            continue
        if ch == '[':
            depth_brack += 1
            cur.append(ch)
            continue
        if ch == ']':
            depth_brack = max(0, depth_brack - 1)
            cur.append(ch)
            continue
        if ch == '(':
            depth_paren += 1
            cur.append(ch)
            continue
        if ch == ')':
            depth_paren = max(0, depth_paren - 1)
            cur.append(ch)
            continue
        if ch == ',' and depth_brack == 0 and depth_paren == 0:
            part = ''.join(cur).strip()
            if part:
                parts.append(part)
            cur = []
            continue
        cur.append(ch)
    last = ''.join(cur).strip()
    if last:
        parts.append(last)
    return parts


def generate_instance(
    code: str,
    mapping: dict,
    second_memory: bool = False,
    instance_name: str = 'u_instancia',
    use_adapter: bool = False,
):
    """
    Gera uma instância Verilog/SystemVerilog a partir de um `module` (com suporte a parâmetros).
    - mapping pode conter:
        * mapping[local_name] = module_port_name  (ex.: 'sys_clk':'clk')
        * mapping[module_port_name] = "<expr>"    (ex.: 'core_sel': "4'b1111")
      Valores None são ignorados.
    - Entradas sem match -> 1'b0
    - Entradas terminadas em _en ou _valid -> 1'b1
    - Debug/trace inputs -> 1'b0
    - Saídas/inout sem match -> ()
    """

    controller_signals_non_open = CONTROLLER_SIGNALS_NON_OPEN

    if second_memory:
        controller_signals_non_open.update(DATA_MEM_SIGNALS_NON_OPEN)

    assign_list = []
    create_list = []
    created_signals = set()

    controller_signals_non_open_keys = list(controller_signals_non_open.keys())
    mapping_keys = list(mapping.keys())

    if not use_adapter:
        for key in controller_signals_non_open_keys:
            if key not in mapping_keys:
                assign_list.append(
                    f'assign {key} = {controller_signals_non_open[key]};'
                )
            elif (
                mapping[key] is None
                or mapping[key] == ''
                or mapping[key] == 'null'
                or mapping[key] == 'None'
            ):
                assign_list.append(
                    f'assign {key} = {controller_signals_non_open[key]};'
                )

        if (
            'data_mem_cyc' in mapping_keys
            and 'data_mem_stb' in mapping_keys
            and second_memory
        ):
            if (
                mapping['data_mem_cyc'] == mapping['data_mem_stb']
                and mapping['data_mem_cyc'] is not None
                and is_identifier(mapping['data_mem_cyc'])
            ):
                assign_list.append('assign data_mem_cyc = 1;')

        if 'core_cyc' in mapping_keys and 'core_stb' in mapping_keys:
            if (
                mapping['core_cyc'] == mapping['core_stb']
                and mapping['core_cyc'] is not None
                and is_identifier(mapping['core_cyc'])
            ):
                assign_list.append('assign core_cyc = 1;')

    # localizar module <name> #( ... )? ( ... ) ;
    header_pat = re.compile(
        r'\bmodule\s+([A-Za-z_]\w*)'  # nome do módulo
        r'(?:\s+import\s+[^;]+;\s*)*'  # zero ou mais imports
        r'(?:\s*#\s*\((?P<params>.*?)\)\s*)?'  # bloco opcional de parâmetros #( ... )
        r'\s*\(\s*(?P<ports>.*?)\s*\)\s*;',  # bloco de portas ( ... );
        re.DOTALL,
    )
    m = header_pat.search(code)
    if not m:
        raise ValueError(
            'Não foi possível localizar o cabeçalho do módulo (module ... #( ... )? ( ... );).'
        )

    module_name = m.group(1)
    params_block = m.group('params') or ''
    ports_block = m.group('ports') or ''

    # -----------------------
    # parse parâmetros (parameter ...)
    # -----------------------
    params = parse_parameters(params_block)
    # params = []
    # if params_block:
    #     for pname, pval in re.findall(
    #         r'parameter\s+([A-Za-z_]\w*)\s*=\s*([^,)+]+)', params_block
    #     ):
    #         params.append((pname.strip(), pval.strip()))

    # -----------------------
    # parse portas
    # -----------------------
    chunks = _split_top_level_commas(ports_block)
    ports = []
    current_dir = None

    for chunk in chunks:
        s = chunk.strip()
        if not s:
            continue

        # Detecta direção
        dm = re.match(r'^(input|output|inout)\b(.*)$', s, re.IGNORECASE)
        if dm:
            current_dir = dm.group(1).lower()
            rest = dm.group(2).strip()
        else:
            if current_dir is None:
                continue
            rest = s

        # Captura range [msb:lsb] e nome da porta
        # Ex: logic [31:0] data_i, data_j
        # Regex captura opcional [msb:lsb] e identificador
        matches = re.findall(r'(\[[^\]]+\])?\s*([A-Za-z_]\w*)', rest)
        for range_str, name in matches:
            if name.lower() in TYPE_WORDS:
                continue
            # calcula largura
            if range_str:
                m = re.match(r'\[(\d+)\s*:\s*(\d+)\]', range_str)
                if m:
                    msb = int(m.group(1))
                    lsb = int(m.group(2))
                    width = abs(msb - lsb) + 1
                else:
                    width = 1
            else:
                width = 1
            ports.append((current_dir, name, width))

    # -----------------------
    # interpretar mapping
    # -----------------------
    reverse_map = {}
    const_map = {}

    for key, val in mapping.items():
        if val is None:
            continue
        if isinstance(val, str) and is_identifier(val):
            reverse_map[val] = key
        else:
            if isinstance(key, str) and is_identifier(key):
                const_map[key] = val
                signals_to_create = get_signals_to_create(val)
                signals_to_create = [
                    s for s in signals_to_create if s not in created_signals
                ]
                if signals_to_create:
                    decl = create_signals_to_declare(signals_to_create, ports)
                    created_signals.update(signals_to_create)
                    create_list.append(decl)

                if not key in OUTPUT_SIGNALS:
                    assign_list.append(f'assign {key} = {val};')
                else:
                    for s in signals_to_create:
                        assign_list.append(f'assign {s} = {key};')

    # -----------------------
    # gerar instância (formatação alinhada)
    # -----------------------
    port_names = [p for (_, p, _) in ports]
    max_port_len = max((len(p) for p in port_names), default=0)
    max_param_len = max((len(p[0]) for p in params), default=0)

    lines = []
    # parâmetros
    if params:
        lines.append(f'{module_name} #(')
        for name, val in params:
            lines.append(f'    .{name:<{max_param_len}} ({val}),')
        lines[-1] = lines[-1].rstrip(',')
        lines.append(f') {instance_name} (')
    else:
        lines.append(f'{module_name} {instance_name} (')

    # portas
    for direction, port, width in ports:
        if direction == 'input' and (
            'clk' in port.lower() or 'clock' in port.lower()
        ):
            conn = 'clk_core'
        elif direction == 'input' and (
            'rst_n' in port.lower()
            or 'reset_n' in port.lower()
            or 'rstn' in port.lower()
            or 'resetn' in port.lower()
            or 'nrst' in port.lower()
            or 'nreset' in port.lower()
            or 'rstb' in port.lower()
            or 'resetb' in port.lower()
            or 'brst' in port.lower()
            or 'breset' in port.lower()
            or 'rst_b' in port.lower()
            or 'reset_b' in port.lower()
            or 'rstz' in port.lower()
            or 'resetz' in port.lower()
            or 'zrst' in port.lower()
            or 'zreset' in port.lower()
            or 'rst_z' in port.lower()
            or 'reset_z' in port.lower()
        ):
            conn = '~rst_core'
        elif direction == 'input' and (
            'rst' in port.lower() or 'reset' in port.lower()
        ):
            conn = 'rst_core'
        elif port in reverse_map:
            if (
                direction == 'input'
                and is_identifier(reverse_map[port])
                and reverse_map[port] not in PROCESSOR_CI_WISHBONE_SIGNALS
            ):
                conn = '0'
            elif port in created_signals:
                conn = port
                if direction == 'input':
                    assign_list.append(f'assign {port} = {reverse_map[port]};')
                else:
                    assign_list.append(f'assign {reverse_map[port]} = {port};')
            else:
                conn = reverse_map[port]
        elif port in const_map:
            conn = const_map[port]
        elif port in created_signals:
            conn = port
        elif direction == 'input':
            pl = port.lower()
            if 'dbg_' in pl or 'trace_' in pl or 'trc_' in pl or 'jtag' in pl:
                conn = '0'
            elif (
                pl.endswith('_en')
                or pl.endswith('_valid')
                or 'poweron' in pl
                or 'start_' in pl
            ):
                conn = '1'
            else:
                conn = '0'
        else:
            conn = ''  # outputs/inout -> vazio

        if conn != '':
            lines.append(f'    .{port:<{max_port_len}} ({conn}),')
        else:
            lines.append(f'    .{port:<{max_port_len}} (),')

    if lines:
        lines[-1] = lines[-1].rstrip(',')
    lines.append(');')

    return '\n'.join(lines), '\n'.join(assign_list), '\n'.join(create_list)


def generate_wrapper(
    cpu_name: str,
    instance_code: str,
    bus_type: str,
    second_memory: bool,
    output_dir='outputs',
    signal_mappings: str = '',
    create_signals: str = '',
):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template('wrapper.j2')

    logger.info(f'Bus type: {bus_type}, Second memory: {second_memory}')

    adapter = ''

    if bus_type == 'AHB':
        adapter = ahb_adapter
        if second_memory:
            adapter += '\n' + ahb_data_adapter
    elif bus_type == 'AXI':
        adapter = axi4_adapter
        if second_memory:
            adapter += '\n' + axi4_data_adapter
    elif bus_type == 'AXI-Lite':
        adapter = axi4_lite_adapter
        if second_memory:
            adapter += '\n' + axi4_lite_data_adapter
    # elif bus_type == 'Avalon':
    #     adapter = avalon_adapter
    #     if second_memory:
    #         adapter += '\n' + avalon_data_adapter

    output = template.render(
        {
            'processor_instance': instance_code,
            'bus_type': bus_type,
            'second_memory': second_memory,
            'bus_adapter': adapter,
            'signal_mappings': signal_mappings,
            'create_signals': create_signals,
        }
    )

    os.makedirs(output_dir, exist_ok=True)

    output_path = f'{output_dir}/{cpu_name}.sv'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
