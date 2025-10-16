import os
import re
import subprocess
import logging
from core import BUILD_DIR, INTERNAL_DIR
from core.defines import KEYWORDS


logger = logging.getLogger(__name__)


def run_ghdl_import(cpu_name, vhdl_files):
    """Importar todos os arquivos VHDL com GHDL -i."""
    logger.info('Importing VHDL files with GHDL (-i)...')
    cmd = [
        'ghdl',
        '-i',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
    ] + list(map(str, vhdl_files))
    logger.debug(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def run_ghdl_elaborate(cpu_name, top_module):
    """Elaborar com GHDL -m."""
    logger.info('Elaborating project with GHDL (-m)...')
    cmd = [
        'ghdl',
        '-m',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
        f'{top_module}',
    ]
    logger.debug(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def synthesize_to_verilog(cpu_name, output_file, top_module):
    """Sintetizar o VHDL com GHDL para Verilog."""
    logger.info(f'Synthesizing {cpu_name} to Verilog...')
    cmd = [
        'ghdl',
        'synth',
        '--latches',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
        '--out=verilog',
        top_module,
    ]
    logger.debug(f"[CMD] {' '.join(cmd)} > {output_file}")
    with open(output_file, 'w') as f:
        subprocess.run(cmd, stdout=f, check=True)


def convert_to_verilog(cpu_name, vhdl_files, top_module, output_file):
    run_ghdl_import(cpu_name, vhdl_files)
    run_ghdl_elaborate(cpu_name, top_module)
    synthesize_to_verilog(cpu_name, output_file, top_module)


def search_files(text_lines: str, files: list[str]):
    modules = set()
    pattern = re.compile(r'(\w+)\s*(\w+)\s*\(')
    # Verifica se algum módulo/entity é definido nesse arquivo

    module_pattern = re.compile(r'^\s*module\s+(\w+)\s*\(')

    extensions = ['.sv', '.v', '.vh', '.vhd']

    for line in text_lines:
        if line.strip() == '' or line.startswith('`line'):
            continue
        strip = line.strip()
        out = pattern.search(strip)
        module_out = module_pattern.search(strip)

        if strip.endswith('#('):
            split = strip.split(' ')
            if 'module' in split[0]:
                modules.add(split[1])
            else:
                modules.add(split[0])

        elif ' #(' in strip:
            split = strip.split(' ')
            if 'module' in split[0]:
                modules.add(split[1])
            else:
                modules.add(split[0])
        else:
            if module_out:
                modules.add(module_out.group(1))
            elif out and strip[-1] == '(' and not strip[0] == ')':
                modules.add(out.group(1))

    found_files = set()
    module_file_patterns = {
        name: re.compile(
            rf'^\s*module\s+{re.escape(name)}\b', re.IGNORECASE | re.MULTILINE
        )
        for name in modules
    }

    for file_path in files:
        try:
            with open(
                file_path, 'r', encoding='utf-8', errors='ignore'
            ) as f:
                content = f.read()
                if any(pattern.search(content) for pattern in module_file_patterns.values()):
                    found_files.add(os.path.abspath(file_path))
        except Exception:
            pass  # ignora erros de leitura

    return sorted(found_files)


def process_verilog(
    cpu_name: str,
    top_module: str,
    files: list[str],
    include_dirs: list[str],
    processor_path,
    context: int = 20,
    convert_to_verilog2005: bool = False,
    format_code: bool = False,
    get_files_in_project: bool = False,
):
    vhdl_files = []
    other_files = []

    os.makedirs(BUILD_DIR, exist_ok=True)

    for file_rel in files:
        src_file = os.path.join(processor_path, file_rel)
        if not os.path.exists(src_file):
            logger.warning(f'File not found: {src_file}')
            continue
        if file_rel.strip().split('.')[-1].lower() in ['vhdl', 'vhd']:
            vhdl_files.append(str(src_file))
        else:
            other_files.append(str(src_file))

    if vhdl_files:
        logger.debug('Found VHDL files:')
        for vhdl_file in vhdl_files:
            logger.debug(f' - {vhdl_file}')
        logger.info('Converting VHDL files to Verilog...')
        os.makedirs(BUILD_DIR, exist_ok=True)
        verilog_output = os.path.join(BUILD_DIR, f'{cpu_name}.v')
        convert_to_verilog(
            cpu_name,
            vhdl_files,
            top_module,
            verilog_output,
        )

        other_files.append(str(verilog_output))

    include_flags = []

    for inc_dir in include_dirs:
        inc_path = os.path.join(processor_path, inc_dir)

        # get all .v and /sv files in the include directory
        files = []

        # get all first level files
        for filename in os.listdir(inc_path):
            if filename.endswith(('.v', '.sv', '.vh')):
                files.append(os.path.join(inc_path, filename))

        other_files.extend(files)

        if os.path.exists(inc_path):
            include_flags.append(f'-I{inc_path}')
        else:
            logger.warning(f'Include directory not found: {inc_path}')

    logger.info('Preprocessing Verilog files with Verilator...')

    verilator_preprocess_cmd = [
        'verilator',
        '-E',  # pré-processamento
        '--top-module',
        f'{top_module}',
        '-DSIMULATION',
        '-DSYNTHESIS',
        '-DSYNTH',
        '-DEN_EXCEPT',
        '-DEN_RVZICSR',
        '--quiet',
        '-Wall',
        '-Wno-UNOPTFLAT',
        '-Wno-IMPLICIT',
        '-Wno-TIMESCALEMOD',
        '-Wno-UNUSED',
        *other_files,
        *include_flags,
    ]

    # Executa o comando e captura a saída
    proc = subprocess.run(
        verilator_preprocess_cmd, capture_output=True, text=True
    )

    output = proc.stdout

    if convert_to_verilog2005:
        logger.info('Converting to Verilog 2005 with verilog2verilog...')
        sv2v_cmd = ['sv2v']
        proc2 = subprocess.run(
            sv2v_cmd, input=output, capture_output=True, text=True
        )
        output = proc2.stdout

    if format_code:
        logger.info('Formatting Verilog code with Verible...')
        verible_cmd = ['verible-verilog-format', '--inplace', '--']
        proc3 = subprocess.run(
            verible_cmd, input=output, capture_output=True, text=True
        )
        output = proc3.stdout

    lines = output.splitlines()

    logging.debug(f'Verilator command: {" ".join(verilator_preprocess_cmd)}')

    logging.info('Filtering top module header...')

    header_lines = []
    inside_module = False
    inside_extended = False
    counter = 0
    top_string = f'module {top_module}'

    for line in lines:
        stripped = line.strip()
        if stripped == '' or stripped.startswith('`line'):
            continue
        if top_string in stripped:
            inside_module = True
        if inside_module:
            header_lines.append(line)
            if ');' in stripped:  # fim do header
                inside_extended = True
        if inside_extended:
            if counter == context:
                break
            counter += 1

    filtered_output = '\n'.join(
        line
        for line in lines
        if line.strip() != '' and not line.startswith('`line')
    )

    output_path = os.path.join(BUILD_DIR, f'{cpu_name}_processed.sv')

    logging.info(f'Saving processed Verilog code to {output_path}...')

    # Salva o resultado em um único arquivo
    with open(output_path, 'w') as f:
        f.write(filtered_output)

    header_str = '\n'.join(header_lines)

    files = []

    if get_files_in_project:
        files = search_files(lines, other_files)

    return header_str, other_files, include_flags, files


def simulate_to_check(
    cpu_name: str,
    files_list: list[str],
    include_flags: list[str],
    output_dir: str = 'outputs',
    second_memory: bool = False,
):
    logging.info('Compilando e executando simulação com Verilator...')

    current_dir = os.getcwd()

    top_module_file = f'{output_dir}/{cpu_name}.sv'

    top_module_file = os.path.join(current_dir, top_module_file)

    files_list.append(str(top_module_file))
    files_list += [
        os.path.join(INTERNAL_DIR, 'verification_top.sv'),
        os.path.join(INTERNAL_DIR, 'memory.sv'),
        os.path.join(INTERNAL_DIR, 'axi4_to_wishbone.sv'),
        os.path.join(INTERNAL_DIR, 'axi4lite_to_wishbone.sv'),
        os.path.join(INTERNAL_DIR, 'ahblite_to_wishbone.sv'),
    ]

    verilator_cmd = [
        'verilator',
        '--cc',
        '--exe',
        '--build',
        '--trace',
        '-Wno-fatal',
        '-DENABLE_SECOND_MEMORY' if second_memory else '',
        '-DSIMULATION',
        '-DSYNTHESIS',
        '-DSYNTH',
        '-DEN_EXCEPT',
        '-DEN_RVZICSR',
        '-Wall',
        '-Wno-UNOPTFLAT',
        '-Wno-IMPLICIT',
        '-Wno-TIMESCALEMOD',
        '-Wno-UNUSED',
        '--top-module',
        'verification_top',
        '--quiet',
        '--Mdir',
        'build',
        os.path.join(INTERNAL_DIR, 'soc_main.cpp'),
        *files_list,
        search_files * include_flags,
        '-CFLAGS',
        '-std=c++17',
    ]

    if second_memory:
        verilator_cmd.append('-DENABLE_SECOND_MEMORY')

    logger.debug(f"[CMD] {' '.join(verilator_cmd)}")
    subprocess.run(verilator_cmd, check=True, cwd=BUILD_DIR)

    expected_output = (0x3C, 0x5)

    sim_executable = os.path.join(BUILD_DIR, 'build', 'Vverification_top')
    if os.path.exists(sim_executable):
        logger.info('Executando simulação...')
        result = subprocess.run(
            [str(sim_executable)], check=True, capture_output=True, text=True
        )
        lines = result.stdout.splitlines()

        logger.debug('Full simulation output:')

        for line in lines:
            logger.debug(f'Simulation output: {line}')

        ok = False
        for line in lines:
            values = line.strip().split(',')
            if len(values) != 3:
                logger.warning(f'Unexpected output line: {line}')
                continue
            addr_str, data_str, cycle_str = values
            addr = int(addr_str, 16)
            data = int(data_str, 16)
            cycle = int(cycle_str)
            if (addr, data) == expected_output:
                ok = True
                logger.info(f'Expected output found: {line}')
            else:
                logger.warning(f'Unexpected output: {line}')

        if ok:
            logger.info(
                'Simulation completed successfully. The CPU is functioning correctly.'
            )
            logger.info(
                f'Address: 0x{expected_output[0]:08X}, Data: 0x{expected_output[1]:08X}'
            )
        else:
            logger.error(
                'Simulation completed, but the expected output was not found.'
            )
            logger.error(
                f'Expected: Address 0x{expected_output[0]:08X}, Data: 0x{expected_output[1]:08X}'
            )
            logger.error('Check the logs above for more details.')
    else:
        logger.error('Simulation executable not found.')
