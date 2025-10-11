import os
import subprocess
from core import BUILD_DIR, INTERNAL_DIR


def run_ghdl_import(cpu_name, vhdl_files):
    """Importar todos os arquivos VHDL com GHDL -i."""
    print('[INFO] Importando arquivos VHDL com GHDL (-i)...')
    cmd = [
        'ghdl',
        '-i',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
    ] + list(map(str, vhdl_files))
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def run_ghdl_elaborate(cpu_name, top_module):
    """Elaborar com GHDL -m."""
    print('[INFO] Elaborando projeto com GHDL (-m)...')
    cmd = [
        'ghdl',
        '-m',
        '--std=08',
        f'--work={cpu_name}',
        f'--workdir={BUILD_DIR}',
        f'-P{BUILD_DIR}',
        f'{top_module}',
    ]
    print(f"[CMD] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def synthesize_to_verilog(cpu_name, output_file, top_module):
    """Sintetizar o VHDL com GHDL para Verilog."""
    print(f'[INFO] Sintetizando {cpu_name} para Verilog...')
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
    print(f"[CMD] {' '.join(cmd)} > {output_file}")
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
):
    vhdl_files = []
    other_files = []

    os.makedirs(BUILD_DIR, exist_ok=True)

    for file_rel in files:
        src_file = os.path.join(processor_path, file_rel)
        if not os.path.exists(src_file):
            print(f'[AVISO] Arquivo não encontrado: {src_file}')
            continue
        if file_rel.strip().split('.')[-1].lower() in ['vhdl', 'vhd']:
            vhdl_files.append(str(src_file))
        else:
            other_files.append(str(src_file))


    if vhdl_files:
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
            print(f'[AVISO] Diretório de include não encontrado: {inc_path}')

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
    lines = proc.stdout.splitlines()

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

    # Salva o resultado em um único arquivo
    with open(output_path, 'w') as f:
        f.write(filtered_output)

    header_str = '\n'.join(header_lines)

    return header_str, other_files, include_flags


def simulate_to_check(
    cpu_name: str, files_list: list[str], include_flags: list[str]
):
    current_dir = os.getcwd()

    top_module_file = f'{cpu_name}.sv'
    
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
        '--Mdir',
        'build',
        os.path.join(INTERNAL_DIR, 'soc_main.cpp'),
        *files_list,
        *include_flags,
        '-CFLAGS',
        '-std=c++17',
    ]

    print(f"[CMD] {' '.join(verilator_cmd)}")
    subprocess.run(verilator_cmd, check=True, cwd=BUILD_DIR)

    sim_executable = os.path.join(BUILD_DIR, 'build', 'Vverification_top')
    if os.path.exists(sim_executable):
        print('[INFO] Executando simulação...')
        subprocess.run([str(sim_executable)], check=True)
    else:
        print('[ERRO] Executável de simulação não encontrado.')
