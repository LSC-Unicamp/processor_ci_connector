import os
import subprocess
import logging
from core import BUILD_DIR, INTERNAL_DIR


logger = logging.getLogger(__name__)


def run_ghdl_import(cpu_name, vhdl_files):
    """Importar todos os arquivos VHDL com GHDL -i."""
    logger.info('Importando arquivos VHDL com GHDL (-i)...')
    cmd = [
        'ghdl',
        '-i',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
    ] + list(map(str, vhdl_files))
    logger.info(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def run_ghdl_elaborate(cpu_name, top_module):
    """Elaborar com GHDL -m."""
    logger.info('Elaborando projeto com GHDL (-m)...')
    cmd = [
        'ghdl',
        '-m',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
        f'{top_module}',
    ]
    logger.info(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def synthesize_to_verilog(cpu_name, output_file, top_module):
    """Sintetizar o VHDL com GHDL para Verilog."""
    logger.info(f'Sintetizando {cpu_name} para Verilog...')
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
    logger.info(f"[CMD] {' '.join(cmd)} > {output_file}")
    with open(output_file, 'w') as f:
        subprocess.run(cmd, stdout=f, check=True)


def convert_to_verilog(cpu_name, vhdl_files, top_module, output_file):
    run_ghdl_import(cpu_name, vhdl_files)
    run_ghdl_elaborate(cpu_name, top_module)
    synthesize_to_verilog(cpu_name, output_file, top_module)


def process_verilog(
    cpu_name: str,
    top_module: str,
    files: list[str],
    include_dirs: list[str],
    processor_path,
    context: int = 20,
    convert_to_verilog2005: bool = False,
    format_code: bool = False,
):
    vhdl_files = []
    other_files = []

    os.makedirs(BUILD_DIR, exist_ok=True)

    for file_rel in files:
        src_file = os.path.join(processor_path, file_rel)
        if not os.path.exists(src_file):
            logger.warning(f'Arquivo não encontrado: {src_file}')
            continue
        if file_rel.strip().split('.')[-1].lower() in ['vhdl', 'vhd']:
            vhdl_files.append(str(src_file))
        else:
            other_files.append(str(src_file))

    if vhdl_files:
        logger.info('Arquivos VHDL encontrados:')
        for vhdl_file in vhdl_files:
            logger.debug(f' - {vhdl_file}')
        logger.info('Convertendo VHDL para Verilog...')
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
        if os.path.exists(inc_path):
            include_flags.append(f'-I{inc_path}')
        else:
            logger.warning(f'Diretório de include não encontrado: {inc_path}')

    logger.info('Pré-processando arquivos Verilog com Verilator...')

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
        logger.info('Convertendo para Verilog 2005 com verilog2verilog...')
        sv2v_cmd = ['sv2v']
        proc2 = subprocess.run(
            sv2v_cmd, input=output, capture_output=True, text=True
        )
        output = proc2.stdout

    if format_code:
        logger.info('Formatando código Verilog com Verible...')
        verible_cmd = ['verible-verilog-format', '--inplace', '--']
        proc3 = subprocess.run(
            verible_cmd, input=output, capture_output=True, text=True
        )
        output = proc3.stdout

    lines = output.splitlines()

    logging.debug(f'Comando Verilator: {" ".join(verilator_preprocess_cmd)}')

    logging.info('Filtrando cabeçalho do módulo superior...')

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

    logging.info('Salvando código Verilog processado...')

    output_path = os.path.join(BUILD_DIR, f'{cpu_name}_processed.sv')

    # Salva o resultado em um único arquivo
    with open(output_path, 'w') as f:
        f.write(filtered_output)

    header_str = '\n'.join(header_lines)

    return header_str, other_files, include_flags


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
        *include_flags,
        '-CFLAGS',
        '-std=c++17',
    ]

    if second_memory:
        verilator_cmd.append('-DENABLE_SECOND_MEMORY')

    logger.info(f"[CMD] {' '.join(verilator_cmd)}")
    subprocess.run(verilator_cmd, check=True, cwd=BUILD_DIR)

    expected_output = (0x3C, 0x5)

    sim_executable = os.path.join(BUILD_DIR, 'build', 'Vverification_top')
    if os.path.exists(sim_executable):
        logger.info('Executando simulação...')
        result = subprocess.run(
            [str(sim_executable)], check=True, capture_output=True, text=True
        )
        lines = result.stdout.splitlines()

        logger.debug('Saída completa da simulação:')

        for line in lines:
            logger.debug(f'Saída da simulação: {line}')

        ok = False
        for line in lines:
            values = line.strip().split(',')
            if len(values) != 3:
                logger.warning(f'Linha de saída inesperada: {line}')
                continue
            addr_str, data_str, cycle_str = values
            addr = int(addr_str, 16)
            data = int(data_str, 16)
            cycle = int(cycle_str)
            if (addr, data) == expected_output:
                ok = True
                logger.info(f'Saída esperada encontrada: {line}')
            else:
                logger.warning(f'Saída inesperada: {line}')

        if ok:
            logger.info(
                'Simulação concluída com sucesso. A CPU está funcionando corretamente.'
            )
            logger.info(
                f'Endereço: 0x{expected_output[0]:08X}, Dado: 0x{expected_output[1]:08X}'
            )
        else:
            logger.error(
                'Simulação concluída, mas a saída esperada não foi encontrada.'
            )
            logger.error(
                f'Esperado: Endereço 0x{expected_output[0]:08X}, Dado: 0x{expected_output[1]:08X}'
            )
            logger.error('Verifique os logs acima para mais detalhes.')
    else:
        logger.error('Executável de simulação não encontrado.')
