import os
import sys
import json
import argparse
from core.hdl_process import process_verilog, simulate_to_check
from core.interface_resolve import (
    extract_interface_and_memory_ports,
    connect_interfaces,
)
from core.make_wrapper import generate_instance, generate_wrapper

DEFAULT_CONFIG_PATH = '/eda/processor_ci/config'
PROCESSOR_CI_PATH = os.getenv('PROCESSOR_CI_PATH', '/eda/processor_ci')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Processador CI  Conector',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '-c',
        '--config',
        type=str,
        default=DEFAULT_CONFIG_PATH,
        help='Caminho para o diretório de configuração',
    )
    parser.add_argument(
        '-p',
        '--processor',
        type=str,
        help='Nome do processador (ex: Grande-Risco-5)',
        required=True,
    )
    parser.add_argument(
        '-n',
        '--context',
        type=int,
        default=10,
        help='Number of context lines to include',
    )
    parser.add_argument(
        '-m',
        '--model',
        type=str,
        default='qwen3:14b',
        help='Model to use for the LLM',
    )
    parser.add_argument(
        '-P',
        '--processor-path',
        type=str,
        required=True,
        help='Path to the processor source code',
    )

    args = parser.parse_args()

    config_path = os.path.join(args.config, f'{args.processor}.json')
    config_data = {}
    with open(config_path, 'r', encoding='utf-8') as file:
        config_data = json.load(file)

    files = config_data.get('files', [])
    include_dirs = config_data.get('include_dirs', [])
    top_module = config_data.get('top_module', args.processor)

    header, other_files, include_flags = process_verilog(
        args.processor,
        top_module,
        files,
        include_dirs,
        args.processor_path,
        context=args.context,
    )

    interface_and_ports = None

    ok = False
    tentativas = 0
    # Tenta 3 vezes obter um json valido
    while not ok and tentativas < 3:
        tentativas += 1
        ok, interface_and_ports = extract_interface_and_memory_ports(
            header, args.model
        )
    
    if tentativas == 3 and not ok:
        print("Erro ao parsear json")
        sys.exit(1)
        

    connections = connect_interfaces(interface_and_ports, header)

    instance = generate_instance(header, connections, "Processor")

    print(f"Generated instance: \n{instance}")

    generate_wrapper(
        args.processor,
        instance,
        interface_and_ports['bus_type'],
        interface_and_ports.get('memory_interface', '') == 'Dual',
    )

    simulate_to_check(args.processor, other_files, include_flags)


if __name__ == '__main__':
    main()
