import os
import re
import logging
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


def _is_vhdl_pkg_file(path: str) -> bool:
    """Check if a VHDL file is likely a package file based on naming conventions."""
    p = path.lower()
    base = os.path.basename(p)
    return (
        base.endswith("_pkg.vhd")
        or base.endswith("_pkg.vhdl")
        or base.endswith("_types.vhd")
        or base.endswith("_types.vhdl")
        or base.endswith("types.vhd")
        or base.endswith("types.vhdl")
        or base.endswith("_pack.vhd")
        or base.endswith("_pack.vhdl")
        or base.endswith("_package.vhd")
        or base.endswith("_package.vhdl")
        or "/pkg/" in p.replace("\\", "/")
        or "package" in base
    )

def _is_pkg_file(path: str) -> bool:
    p = path.lower()
    base = os.path.basename(p)
    return (
        base.endswith("_pkg.sv")
        or base.endswith("_pkg.svh")
        or base.endswith("_types.sv")
        or base.endswith("types.sv")
        or base.endswith("_types.svh")
        or base.endswith("types.svh")
        or base.endswith("_config.sv")
        or base.endswith("_config.svh")
        or "config_and_types" in base
        or "/pkg/" in p.replace("\\", "/")
    )


def _order_sv_files(files: List[str], repo_root: str | None = None) -> List[str]:
    """
    Order SystemVerilog files based on dependencies.
    
    Dependencies considered:
    1. Package imports (packages must come before files that import them)
    2. Module instantiations (instantiated modules must come before instantiating modules)
    3. Define dependencies (files with defines must come before files that check them)
    
    The result should have:
    - Package/type files first
    - Lower-level modules next
    - Top module(s) last
    """
    if not repo_root:
        indexed = list(enumerate(files))
        indexed.sort(key=lambda t: (0 if _is_pkg_file(t[1]) else 1, t[0]))
        return [f for _i, f in indexed]

    logger.debug(f"Ordering {len(files)} files with repo_root: {repo_root}")

    pkg_decl_re = re.compile(r"^\s*package\s+(\w+)\s*;", re.MULTILINE | re.IGNORECASE)
    import_re = re.compile(r"^\s*import\s+([a-zA-Z_]\w*)\s*::\s*\*\s*;", re.MULTILINE | re.IGNORECASE)
    import_list_re = re.compile(r"^\s*import\s+([^;]+);", re.MULTILINE | re.IGNORECASE)
    namespace_ref_re = re.compile(r"\b([a-zA-Z_]\w+)::[a-zA-Z_]\w+", re.MULTILINE)
    ifdef_error_re = re.compile(r"^\s*`ifdef\s+(\w+)\s*\n\s*`error", re.MULTILINE | re.IGNORECASE)
    define_re = re.compile(r"^\s*`define\s+(\w+)", re.MULTILINE | re.IGNORECASE)
    
    # Regex to detect module declarations
    module_decl_re = re.compile(r"^\s*module\s+([a-zA-Z_]\w*)", re.MULTILINE | re.IGNORECASE)
    # Regex to detect module instantiations - simpler pattern that catches "ModuleName #(" or "ModuleName instanceName ("
    # This handles cases where #( is on the same line or next line
    module_inst_re = re.compile(r"^\s*([a-zA-Z_]\w+)\s+(?:#\s*\(|([a-zA-Z_]\w+)\s*\()", re.MULTILINE)

    def _read(file_path: str) -> str:
        try:
            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                path = file_path
            else:
                path = os.path.join(repo_root, file_path)
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception as e:
            return ""

    file_to_imports: Dict[str, Set[str]] = {f: set() for f in files}
    file_to_module_instantiations: Dict[str, Set[str]] = {f: set() for f in files}
    module_to_file: Dict[str, str] = {}
    pkg_to_file: Dict[str, str] = {}
    define_to_file: Dict[str, str] = {}
    file_to_forbidden_defines: Dict[str, Set[str]] = {f: set() for f in files}

    # First pass: detect module declarations, package declarations and defines
    for f in files:
        text = _read(f)
        if not text:
            logger.debug(f"Could not read file: {f}")
            continue

        # Detect module declarations
        for m in module_decl_re.finditer(text):
            module_name = m.group(1)
            module_to_file[module_name] = f
            logger.debug(f"Found module '{module_name}' in {os.path.basename(f)}")
            break  # Only take the first module declaration per file

        for m in pkg_decl_re.finditer(text):
            pkg_to_file[m.group(1)] = f
            logger.debug(f"Found package '{m.group(1)}' in {os.path.basename(f)}")
            break

        for m in define_re.finditer(text):
            define_to_file[m.group(1)] = f

        for m in ifdef_error_re.finditer(text):
            file_to_forbidden_defines[f].add(m.group(1))

    logger.debug(f"Detected {len(module_to_file)} modules: {list(module_to_file.keys())}")
    logger.debug(f"Detected {len(pkg_to_file)} packages: {list(pkg_to_file.keys())}")

    # Second pass: detect imports, module instantiations, and dependencies
    for f in files:
        text = _read(f)
        if not text:
            continue

        # Detect package imports
        for m in import_re.finditer(text):
            file_to_imports[f].add(m.group(1))

        for m in import_list_re.finditer(text):
            for seg in m.group(1).split(','):
                seg = seg.strip()
                if '::' in seg:
                    pkg = seg.split('::', 1)[0].strip()
                    if re.match(r"^[a-zA-Z_]\w*$", pkg):
                        file_to_imports[f].add(pkg)

        for m in namespace_ref_re.finditer(text):
            pkg = m.group(1)
            if pkg in pkg_to_file:
                file_to_imports[f].add(pkg)
        
        # Detect module instantiations
        # Need to handle multi-line instantiations like:
        #   ModuleName #(
        #       params
        #   ) instance_name (
        # Strategy: Look for "ModuleName" followed by either "#(" or "instance_name ("
        # where ModuleName matches a known module
        keywords = {'module', 'endmodule', 'if', 'else', 'case', 'for', 'while', 'initial', 'always', 'always_comb', 'always_ff', 'assign', 'logic', 'reg', 'wire', 'input', 'output', 'inout', 'parameter', 'localparam', 'function', 'task', 'generate', 'endgenerate', 'begin', 'end', 'return'}
        
        # Simple approach: look for lines that start with a module name followed by whitespace and either # or an identifier
        for module_name in module_to_file.keys():
            # Pattern: start of line, optional whitespace, module name, whitespace, then either #( or identifier (
            pattern = rf'^\s*{re.escape(module_name)}\s+(?:#|\w+\s*\()'
            if re.search(pattern, text, re.MULTILINE):
                # Make sure it's not the module declaration itself
                if module_to_file[module_name] != f:
                    file_to_module_instantiations[f].add(module_name)
                    logger.debug(f"{os.path.basename(f)} instantiates module '{module_name}'")

        
        if file_to_imports[f]:
            logger.debug(f"{os.path.basename(f)} imports: {file_to_imports[f]}")

    # Identify which modules are instantiated (i.e., not top-level)
    instantiated_modules = set()
    for f, modules in file_to_module_instantiations.items():
        instantiated_modules.update(modules)
    
    # Find modules that are never instantiated (potential top modules)
    top_modules = set(module_to_file.keys()) - instantiated_modules
    top_module_files = {module_to_file[m] for m in top_modules}
    
    if top_modules:
        logger.debug(f"Top modules (never instantiated): {top_modules}")
    
    nodes = list(files)
    adj: Dict[str, Set[str]] = {f: set() for f in nodes}
    indeg: Dict[str, int] = {f: 0 for f in nodes}

    # Package dependency edges: provider → importer
    for f, imports in file_to_imports.items():
        for pkg in imports:
            provider = pkg_to_file.get(pkg)
            if provider and provider != f:
                if f not in adj[provider]:
                    adj[provider].add(f)
                    indeg[f] += 1

    # Module instantiation edges: instantiated module → instantiating module
    # (the instantiated module must be compiled before the module that uses it)
    for f, instantiated_modules in file_to_module_instantiations.items():
        for module_name in instantiated_modules:
            provider = module_to_file.get(module_name)
            if provider and provider != f:
                if f not in adj[provider]:
                    adj[provider].add(f)
                    indeg[f] += 1
                    logger.debug(f"Dependency: {os.path.basename(provider)} must come before {os.path.basename(f)}")

    # Ifdef define dependency edges: checker → definer
    for f, forbidden in file_to_forbidden_defines.items():
        for define in forbidden:
            definer = define_to_file.get(define)
            if definer and definer != f:
                if definer not in adj[f]:
                    adj[f].add(definer)
                    indeg[definer] += 1

    # --- Topological sort (Kahn's algorithm) ---
    # Priority: packages (0) < regular modules (1) < top modules (2)
    def get_priority(f):
        if _is_pkg_file(f):
            return 0
        elif f in top_module_files:
            return 2
        else:
            return 1
    
    index_map = {f: i for i, f in enumerate(nodes)}
    zero_indeg = sorted(
        [n for n in nodes if indeg[n] == 0],
        key=lambda x: (get_priority(x), index_map[x])
    )
    ordered: List[str] = []

    while zero_indeg:
        n = zero_indeg.pop(0)
        ordered.append(n)
        for m in sorted(adj[n], key=lambda x: index_map[x]):
            indeg[m] -= 1
            if indeg[m] == 0:
                zero_indeg.append(m)
                zero_indeg.sort(key=lambda x: (get_priority(x), index_map[x]))

    if len(ordered) != len(nodes):
        remaining = [n for n in nodes if n not in ordered]
        logger.warning(f"Topological sort incomplete: {len(remaining)} files have circular dependencies")
        ordered.extend(sorted(remaining, key=lambda x: index_map[x]))

    logger.debug(f"File ordering complete: {len(ordered)} files ordered")
    return ordered


def _order_vhdl_files(files: List[str], repo_root: str | None = None) -> List[str]:
    """
    Order VHDL files based on dependencies.
    
    VHDL dependency rules:
    1. Packages must come before entities/architectures that use them
    2. Entities must come before architectures that implement them
    3. Entity/architecture pairs must come before entities that instantiate them
    4. Library 'use' clauses determine package dependencies
    
    The result should have:
    - Package files first
    - Lower-level entities/architectures next
    - Top entity/architecture last
    """
    if not repo_root:
        # Simple fallback: packages first, then by original order
        indexed = list(enumerate(files))
        indexed.sort(key=lambda t: (0 if _is_vhdl_pkg_file(t[1]) else 1, t[0]))
        return [f for _i, f in indexed]

    logger.debug(f"Ordering {len(files)} VHDL files with repo_root: {repo_root}")

    # VHDL patterns (case-insensitive)
    # Package declaration: package <name> is
    pkg_decl_re = re.compile(r"^\s*package\s+(\w+)\s+is\b", re.MULTILINE | re.IGNORECASE)
    # Entity declaration: entity <name> is
    entity_decl_re = re.compile(r"^\s*entity\s+(\w+)\s+is\b", re.MULTILINE | re.IGNORECASE)
    # Architecture declaration: architecture <arch_name> of <entity_name> is
    arch_decl_re = re.compile(r"^\s*architecture\s+\w+\s+of\s+(\w+)\s+is\b", re.MULTILINE | re.IGNORECASE)
    # Use clause: use <library>.<package>.<item> or use <library>.<package>.all
    use_clause_re = re.compile(r"^\s*use\s+(\w+)\.(\w+)\.", re.MULTILINE | re.IGNORECASE)
    # Component declaration: component <name> is (for instantiation detection)
    component_re = re.compile(r"^\s*component\s+(\w+)\b", re.MULTILINE | re.IGNORECASE)
    # Direct entity instantiation: <instance_name> : entity <library>.<entity_name>
    entity_inst_re = re.compile(r"^\s*\w+\s*:\s*entity\s+(\w+)\.(\w+)", re.MULTILINE | re.IGNORECASE)
    # Component instantiation: <instance_name> : <component_name>
    comp_inst_re = re.compile(r"^\s*\w+\s*:\s*(\w+)\s+(?:port|generic)\s+map", re.MULTILINE | re.IGNORECASE)

    def _read(file_path: str) -> str:
        try:
            if os.path.isabs(file_path):
                path = file_path
            else:
                path = os.path.join(repo_root, file_path)
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception as e:
            logger.debug(f"Could not read file {file_path}: {e}")
            return ""

    # Data structures
    file_to_packages: Dict[str, Set[str]] = {f: set() for f in files}  # packages used by file
    file_to_entities_used: Dict[str, Set[str]] = {f: set() for f in files}  # entities instantiated
    pkg_to_file: Dict[str, str] = {}  # package name -> file that declares it
    entity_to_file: Dict[str, str] = {}  # entity name -> file that declares it
    file_to_declared_entity: Dict[str, str] = {}  # file -> entity name declared in it

    # First pass: detect package and entity declarations
    for f in files:
        text = _read(f)
        if not text:
            logger.debug(f"Could not read file: {f}")
            continue

        # Find package declarations
        for m in pkg_decl_re.finditer(text):
            pkg_name = m.group(1).lower()  # VHDL is case-insensitive
            pkg_to_file[pkg_name] = f
            logger.debug(f"Found package '{m.group(1)}' in {os.path.basename(f)}")
            break  # Usually one package per file

        # Find entity declarations
        for m in entity_decl_re.finditer(text):
            entity_name = m.group(1).lower()
            entity_to_file[entity_name] = f
            file_to_declared_entity[f] = entity_name
            logger.debug(f"Found entity '{m.group(1)}' in {os.path.basename(f)}")
            break  # Usually one entity per file (architecture can be in same file)

    logger.debug(f"Detected {len(pkg_to_file)} packages: {list(pkg_to_file.keys())}")
    logger.debug(f"Detected {len(entity_to_file)} entities: {list(entity_to_file.keys())}")

    # Second pass: detect dependencies (use clauses, instantiations)
    for f in files:
        text = _read(f)
        if not text:
            continue

        # Find package dependencies via use clauses
        for m in use_clause_re.finditer(text):
            library = m.group(1).lower()
            package = m.group(2).lower()
            
            # Skip standard IEEE libraries
            if library in ['ieee', 'std']:
                continue
            
            # If it's from 'work' library or matches a known package, track it
            if library == 'work' and package in pkg_to_file:
                file_to_packages[f].add(package)
                logger.debug(f"{os.path.basename(f)} uses package '{package}'")
            elif package in pkg_to_file:
                file_to_packages[f].add(package)
                logger.debug(f"{os.path.basename(f)} uses package '{package}'")

        # Find entity instantiations (direct entity instantiation)
        for m in entity_inst_re.finditer(text):
            library = m.group(1).lower()
            entity = m.group(2).lower()
            
            if library == 'work' and entity in entity_to_file:
                file_to_entities_used[f].add(entity)
                logger.debug(f"{os.path.basename(f)} instantiates entity '{entity}' (direct)")

        # Find component instantiations
        # First collect component declarations in this file
        components_in_file = set()
        for m in component_re.finditer(text):
            components_in_file.add(m.group(1).lower())
        
        # Then find component instantiations
        for m in comp_inst_re.finditer(text):
            comp_name = m.group(1).lower()
            # If this component matches a known entity (and wasn't declared in this file)
            if comp_name in entity_to_file and comp_name not in components_in_file:
                file_to_entities_used[f].add(comp_name)
                logger.debug(f"{os.path.basename(f)} instantiates entity '{comp_name}' (component)")

    # Identify which entities are instantiated (not top-level)
    instantiated_entities = set()
    for f, entities in file_to_entities_used.items():
        instantiated_entities.update(entities)
    
    # Find entities that are never instantiated (potential top entities)
    top_entities = set(entity_to_file.keys()) - instantiated_entities
    top_entity_files = {entity_to_file[e] for e in top_entities}
    
    if top_entities:
        logger.debug(f"Top entities (never instantiated): {top_entities}")

    # Build dependency graph
    nodes = list(files)
    adj: Dict[str, Set[str]] = {f: set() for f in nodes}
    indeg: Dict[str, int] = {f: 0 for f in nodes}

    # Package dependency edges: package file → files that use it
    for f, packages in file_to_packages.items():
        for pkg in packages:
            provider = pkg_to_file.get(pkg)
            if provider and provider != f:
                if f not in adj[provider]:
                    adj[provider].add(f)
                    indeg[f] += 1
                    logger.debug(f"Package dependency: {os.path.basename(provider)} → {os.path.basename(f)}")

    # Entity instantiation edges: instantiated entity file → instantiating file
    for f, entities in file_to_entities_used.items():
        for entity in entities:
            provider = entity_to_file.get(entity)
            if provider and provider != f:
                if f not in adj[provider]:
                    adj[provider].add(f)
                    indeg[f] += 1
                    logger.debug(f"Entity dependency: {os.path.basename(provider)} → {os.path.basename(f)}")

    # Topological sort with priority: packages (0) < regular entities (1) < top entities (2)
    def get_priority(f):
        if _is_vhdl_pkg_file(f):
            return 0
        elif f in top_entity_files:
            return 2
        else:
            return 1
    
    index_map = {f: i for i, f in enumerate(nodes)}
    zero_indeg = sorted(
        [n for n in nodes if indeg[n] == 0],
        key=lambda x: (get_priority(x), index_map[x])
    )
    ordered: List[str] = []

    while zero_indeg:
        n = zero_indeg.pop(0)
        ordered.append(n)
        for m in sorted(adj[n], key=lambda x: index_map[x]):
            indeg[m] -= 1
            if indeg[m] == 0:
                zero_indeg.append(m)
                zero_indeg.sort(key=lambda x: (get_priority(x), index_map[x]))

    if len(ordered) != len(nodes):
        remaining = [n for n in nodes if n not in ordered]
        logger.warning(f"VHDL topological sort incomplete: {len(remaining)} files have circular dependencies")
        ordered.extend(sorted(remaining, key=lambda x: index_map[x]))

    logger.debug(f"VHDL file ordering complete: {len(ordered)} files ordered")
    return ordered
