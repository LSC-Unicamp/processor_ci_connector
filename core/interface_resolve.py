import re
import ast
import json
import logging
from core import send_prompt
from core.prompts import (
    wishbone_prompt,
    ahb_prompt,
    axi_prompt,
    find_interface_prompt,
)

logger = logging.getLogger(__name__)

def filter_connections_from_response(response):
    def clean_json_block(block: str):
        # Remove comments (// ...)
        block = re.sub(r'//.*', '', block)
        # Remove trailing commas
        block = re.sub(r',\s*}', '}', block)
        block = re.sub(r',\s*]', ']', block)
        return block.strip()

    # Regex to capture Connections and Defaults blocks (with optional ** markdown formatting)
    connections_match = re.search(
        r'\*{0,2}Connections\*{0,2}:\s*({.*?})', response, re.DOTALL
    )

    if not connections_match:
        logger.warning('Could not find Connections in the response.')
        return None

    connections_str = clean_json_block(connections_match.group(1))

    connections = json.loads(connections_str)

    return connections


def connect_interfaces(interface_info, processor_interface, model='qwen2.5:32b'):
    if interface_info['bus_type'] == 'Wishbone':
        prompt = wishbone_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )
    elif interface_info['bus_type'] == 'AHB':
        prompt = ahb_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )
    elif interface_info['bus_type'] == 'AXI':
        prompt = axi_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )
    else:
        logger.warning('Defaulting to Wishbone.')
        prompt = wishbone_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )

    logger.info(f"Consultando modelo {model} para conexões de interface...")

    success, response = send_prompt(prompt, model=model)

    logger.debug(f'Ollama response for connection: \n{response}\n\n')

    if not success:
        logger.error('Error communicating with the server.')
        return None, None

    connections = filter_connections_from_response(response)
    return connections


def filter_processor_interface_from_response(response: str) -> str:
    """
    It is expected a response with the following json format:
    {
        "bus_type": One of [AHB, AXI, Avalon, Wishbone, Custom],
        "memory_interface": Single or Dual,
    }
    This function extracts and returns only the JSON part of the response.
    """
    # --- 1. Find last {...} block ---
    start = response.rfind('{')
    end = response.rfind('}')
    if start == -1 or end == -1 or end < start:
        raise ValueError('No JSON object found in response.')
    candidate = response[start : end + 1]

    # --- 2. Small fixes for common LLM mistakes ---
    candidate = re.sub(
        r',\s*([}\]])', r'\1', candidate
    )  # remove trailing commas
    candidate = candidate.replace("'", '"')  # single → double quotes
    candidate = re.sub(
        r'([,{]\s*)(\w+)(\s*):', r'\1"\2"\3:', candidate
    )  # quote keys
    candidate = re.sub(
        r'//.*$', '', candidate, flags=re.MULTILINE
    )  # remove JavaScript-style comments

    # --- 3. Try parsing ---
    try:
        parsed = json.loads(candidate)
        logger.debug(f'Successfully parsed with json.loads: {parsed}')
    except json.JSONDecodeError:
        logger.warning('Failed to parse JSON with json.loads, trying ast.literal_eval...')
        try:
            # fallback: try Python dict style with ast.literal_eval
            parsed = ast.literal_eval(candidate)
            logger.debug(f'Successfully parsed with ast.literal_eval: {parsed}')
        except (ValueError, SyntaxError):
            logger.error(f'Failed to parse JSON from response: {candidate}')
            return False, {}

    # --- 4. Keep only expected keys ---
    allowed_keys = {'bus_type', 'memory_interface'}
    filtered = {k: parsed[k] for k in allowed_keys if k in parsed}

    return True, filtered


def extract_interface_and_memory_ports(core_declaration, model='qwen2.5:32b'):

    prompt = find_interface_prompt.format(core_declaration=core_declaration)

    logger.info(f"Consultando modelo {model} para identificar a interface do processador...")

    success, response = send_prompt(prompt, model=model)

    logger.debug(f'Ollama response for interface extraction: \n{response}\n\n')

    if not success:
        logger.error('Error communicating with the server.')
        return None

    ok, json_info = filter_processor_interface_from_response(response)
    return ok, json_info
