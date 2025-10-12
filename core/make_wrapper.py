import re
from core import TEMPLATES_DIR
from jinja2 import Environment, FileSystemLoader
from core.bus_defines import (
    ahb_adapter,
    ahb_data_adapter,
    axi4_adapter,
    axi4_data_adapter,
    axi4_lite_adapter,
    axi4_lite_data_adapter,
    avalon_adapter,
    avalon_data_adapter,
)


def _split_top_level_commas(s: str):
    """Divide por vírgulas de nível superior (ignora vírgulas dentro de colchetes/parênteses/strings)."""
    parts, cur = [], []
    depth_paren = depth_brack = 0
    in_squote = in_dquote = esc = False
    for ch in s:
        if esc:
            cur.append(ch); esc = False; continue
        if ch == '\\':
            cur.append(ch); esc = True; continue
        if ch == "'" and not in_dquote:
            in_squote = not in_squote; cur.append(ch); continue
        if ch == '"' and not in_squote:
            in_dquote = not in_dquote; cur.append(ch); continue
        if in_squote or in_dquote:
            cur.append(ch); continue
        if ch == '[': depth_brack += 1; cur.append(ch); continue
        if ch == ']': depth_brack = max(0, depth_brack-1); cur.append(ch); continue
        if ch == '(': depth_paren += 1; cur.append(ch); continue
        if ch == ')': depth_paren = max(0, depth_paren-1); cur.append(ch); continue
        if ch == ',' and depth_brack == 0 and depth_paren == 0:
            part = ''.join(cur).strip()
            if part: parts.append(part)
            cur = []
            continue
        cur.append(ch)
    last = ''.join(cur).strip()
    if last:
        parts.append(last)
    return parts


def generate_instance(code: str, mapping: dict, instance_name='u_instancia'):
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

    # localizar module <name> #( ... )? ( ... ) ;
    header_pat = re.compile(
        r'\bmodule\s+([A-Za-z_]\w*)'                # module name
        r'(?:\s*#\s*\((?P<params>.*?)\)\s*)?'       # optional params block
        r'\(\s*(?P<ports>.*?)\s*\)\s*;',            # ports block up to the terminating ');'
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
    params = []
    if params_block:
        for pname, pval in re.findall(
            r'parameter\s+([A-Za-z_]\w*)\s*=\s*([^,)+]+)', params_block
        ):
            params.append((pname.strip(), pval.strip()))

    # -----------------------
    # parse portas
    # -----------------------
    chunks = _split_top_level_commas(ports_block)
    ports = []
    current_dir = None

    type_words = {
        'reg', 'wire', 'logic', 'signed', 'unsigned', 'integer',
        'bit', 'byte', 'int', 'shortint'
    }

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

        # Remove ranges e tipos
        rest = re.sub(r'\[[^\]]+\]', '', rest)
        tokens = [t.strip(',;') for t in rest.split() if t.strip(',;')]

        for t in tokens:
            if t.lower() in type_words:
                continue
            if not re.match(r'^[A-Za-z_]\w*$', t):
                continue
            ports.append((current_dir, t))

    # -----------------------
    # interpretar mapping
    # -----------------------
    reverse_map = {}
    const_map = {}

    def is_identifier(tok):
        return bool(re.match(r'^[A-Za-z_]\w*$', tok))

    for key, val in mapping.items():
        if val is None:
            continue
        if isinstance(val, str) and is_identifier(val):
            reverse_map[val] = key
        else:
            if isinstance(key, str) and is_identifier(key):
                const_map[key] = val

    # -----------------------
    # gerar instância (formatação alinhada)
    # -----------------------
    port_names = [p for (_, p) in ports]
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
    for direction, port in ports:
        if port in reverse_map:
            conn = reverse_map[port]
        elif port in const_map:
            conn = const_map[port]
        elif direction == 'input':
            pl = port.lower()
            if 'dbg_' in pl or 'trace_' in pl:
                conn = "1'b0"
            elif pl.endswith('_en') or pl.endswith('_valid'):
                conn = "1'b1"
            else:
                conn = "1'b0"
        else:
            conn = ''  # outputs/inout -> vazio

        if conn != '':
            lines.append(f'    .{port:<{max_port_len}} ({conn}),')
        else:
            lines.append(f'    .{port:<{max_port_len}} (),')

    if lines:
        lines[-1] = lines[-1].rstrip(',')
    lines.append(');')

    return '\n'.join(lines)




def generate_wrapper(
    cpu_name: str, instance_code: str, bus_type: str, second_memory: bool
):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template('wrapper.j2')

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
    elif bus_type == 'Avalon':
        adapter = avalon_adapter
        if second_memory:
            adapter += '\n' + avalon_data_adapter

    output = template.render(
        {
            'processor_instance': instance_code,
            'bus_type': bus_type,
            'second_memory': second_memory,
            'bus_adapter': adapter,
        }
    )

    os.makedirs('outputs', exist_ok=True)

    output_path = f'outputs/{cpu_name}.sv'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
