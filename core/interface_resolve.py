import re
import ast
import json
from core import send_prompt
from core.prompts import (
    wishbone_prompt,
    ahb_prompt,
    axi_prompt,
    find_interface_prompt,
)


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
        print('Could not find Connections in the response.')
        return None

    connections_str = clean_json_block(connections_match.group(1))

    connections = json.loads(connections_str)

    return connections


def connect_interfaces(interface_info, processor_interface):
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
        print('Defaulting to Wishbone.')
        prompt = wishbone_prompt.format(
            processor_interface=processor_interface,
            memory_interface=interface_info['memory_interface'],
        )

    success, response = send_prompt(prompt)
    if not success:
        print('Error communicating with the server.')
        return None, None

    connections = filter_connections_from_response(response)
    return connections


def filter_processor_interface_from_response(response: str) -> str:
    """
    It is expected a response with the following json format:
    {
        "bus_type": One of [AHB, AXI, Avalon, Wishbone, Custom],
        "memory_interface": Single or Dual,
        "confidence": High/Medium/Low (based on number of matches and comments)
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
    except json.JSONDecodeError:
        try:
            # fallback: try Python dict style with ast.literal_eval
            parsed = ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            raise ValueError(
                f'Failed to parse JSON from response: {candidate}'
            )

    # --- 4. Keep only expected keys ---
    allowed_keys = {'bus_type', 'memory_interface', 'confidence'}
    filtered = {k: parsed[k] for k in allowed_keys if k in parsed}

    return filtered


def extract_interface_and_memory_ports(core_declaration, model='qwen2.5:32b'):

    prompt = find_interface_prompt.format(core_declaration=core_declaration)
    success, response = send_prompt(prompt, model=model)

    if not success:
        print('Error communicating with the server.')
        return None

    json_info = filter_processor_interface_from_response(response)
    return json_info
