"""
Test script to download OpenAPI spec and build dependency graph
"""

import os
import requests

# Import from your dependency_graph.py
from dependency_graph import build_dependency_graph_from_openapi


# ============================================================================
# LOCAL OPENAPI SPEC FILES - Add new specs here
# ============================================================================
LOCAL_SPECS = {
    'simple_api': {
        'path': 'simple_api.yaml',
        'name': 'Simple User API',
        'description': 'Basic user CRUD operations'
    },
    'user': {
        'path': 'user.yaml',
        'name': 'User API',
        'description': 'User management API'
    },
    'market': {
        'path': 'market.yaml',
        'name': 'Market API',
        'description': 'Market/trading operations'
    },
    'person': {
        'path': 'person.yaml',
        'name': 'Person API',
        'description': 'Person management API'
    },
    'project': {
        'path': 'project.yaml',
        'name': 'Project API',
        'description': 'Project management API'
    },
    'features': {
        'path': 'features.yaml',
        'name': 'Features API',
        'description': 'Feature flag/toggle API'
    },
    'spotify': {
        'path': 'spotify.yaml',
        'name': 'Spotify API',
        'description': 'Spotify music API'
    },
    'fdic': {
        'path': 'fdic.yaml',
        'name': 'FDIC API',
        'description': 'Federal Deposit Insurance Corporation API'
    },
    'language_tool': {
        'path': 'language-tool.yaml',
        'name': 'Language Tool API',
        'description': 'Grammar and spell checking API'
    },
    'genome_nexus': {
        'path': 'genome-nexus.yaml',
        'name': 'Genome Nexus API',
        'description': 'Genomic data annotation API'
    },
    'rest_countries': {
        'path': 'rest-countries.yaml',
        'name': 'REST Countries API',
        'description': 'Country information API'
    },
    'ohsome': {
        'path': 'ohsome.yaml',
        'name': 'Ohsome API',
        'description': 'OpenStreetMap history analytics API'
    },
}


def download_openapi_spec(url: str, filename: str) -> str:
    """Download OpenAPI specification"""
    
    # Create directory
    os.makedirs("openapi_specs", exist_ok=True)
    output_path = os.path.join("openapi_specs", filename)
    
    # Check if already exists
    if os.path.exists(output_path):
        print(f"✓ {filename} already exists at {output_path}")
        return output_path
    
    # Download
    print(f"Downloading {filename}...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✓ Downloaded to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"✗ Error downloading: {e}")
        return None


def test_local_spec(spec_key: str):
    """Generic function to test any local OpenAPI spec"""
    if spec_key not in LOCAL_SPECS:
        print(f"✗ Error: Unknown spec key '{spec_key}'")
        return None
    
    spec_info = LOCAL_SPECS[spec_key]
    spec_path = spec_info['path']
    spec_name = spec_info['name']
    
    print("\n" + "="*80)
    print(f"TESTING WITH {spec_name.upper()}")
    print("="*80)
    
    if not os.path.exists(spec_path):
        print(f"✗ Error: '{spec_path}' not found.")
        return None

    # Build dependency graph
    print("\nBuilding dependency graph...\n")
    
    # Create output directory name from spec key
    output_dir = f"./output_{spec_key}"
    
    graph = build_dependency_graph_from_openapi(
        spec_path=spec_path,
        enable_dynamic=False,
        export_results=True,
        output_dir=output_dir
    )
    
    # Print some interesting information
    print("\n" + "="*80)
    print("INTERESTING FINDINGS")
    print("="*80)
    
    # Show some example sequences
    print("\nExample Operation Sequences:")
    interesting_ops = [op for op in graph.operations.values() if op.is_interesting()]
    
    if interesting_ops:
        for i, op in enumerate(interesting_ops[:3], 1):
            sequence = graph.get_operation_sequence(op)
            print(f"\n{i}. To execute: {op.method.value} {op.path}")
            print(f"   Prerequisites:")
            if len(sequence) > 1:
                for j, seq_op in enumerate(sequence[:-1], 1):
                    print(f"      {j}. {seq_op.method.value} {seq_op.path}")
            else:
                print(f"      (No dependencies - can execute directly)")
    else:
        print("  No interesting operations found.")
    
    print("\n" + "="*80)
    print("✓ Test completed!")
    print(f"✓ Check '{output_dir}' folder for results:")
    print(f"   - graph.json (JSON format)")
    print(f"   - graph.html (Interactive visualization)")
    print(f"   - build_stats.txt (Complete build log)")
    print("="*80)
    
    return graph


def test_petstore():
    """Test with Petstore API"""
    print("\n" + "="*80)
    print("TESTING WITH PETSTORE API")
    print("="*80)
    
    # Download Petstore spec
    spec_path = download_openapi_spec(
        url="https://petstore3.swagger.io/api/v3/openapi.yaml",
        filename="petstore.yaml"
    )
    
    if not spec_path:
        print("Failed to download spec")
        return
    
    # Build dependency graph
    print("\nBuilding dependency graph...\n")
    graph = build_dependency_graph_from_openapi(
        spec_path=spec_path,
        enable_dynamic=False,
        export_results=True,
        output_dir="./output_petstore"
    )
    
    # Print some interesting information
    print("\n" + "="*80)
    print("INTERESTING FINDINGS")
    print("="*80)
    
    # Show some example sequences
    print("\nExample Operation Sequences:")
    interesting_ops = [op for op in graph.operations.values() if op.is_interesting()]
    
    for i, op in enumerate(interesting_ops[:3], 1):
        sequence = graph.get_operation_sequence(op)
        print(f"\n{i}. To execute: {op.method.value} {op.path}")
        print(f"   You need to first execute:")
        for j, seq_op in enumerate(sequence[:-1], 1):  # Exclude the target operation itself
            print(f"      {j}. {seq_op.method.value} {seq_op.path}")
        if len(sequence) == 1:
            print(f"      (No dependencies - can execute directly)")
    
    print("\n" + "="*80)
    print("✓ Test completed!")
    print(f"✓ Check './output_petstore' folder for results:")
    print(f"   - graph.json (JSON format)")
    print(f"   - graph.html (Interactive visualization - OPEN THIS IN BROWSER)")
    print(f"   - annotated_spec.yaml (Annotated OpenAPI spec)")
    print("="*80)


def test_github():
    """Test with GitHub API (more complex)"""
    print("\n" + "="*80)
    print("TESTING WITH GITHUB API (This will take longer - 600+ operations)")
    print("="*80)
    
    spec_path = download_openapi_spec(
        url="https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json",
        filename="github.json"
    )
    
    if not spec_path:
        print("Failed to download spec")
        return
    
    print("\nBuilding dependency graph (this may take 1-2 minutes)...\n")
    graph = build_dependency_graph_from_openapi(
        spec_path=spec_path,
        enable_dynamic=False,
        export_results=True,
        output_dir="./output_github"
    )
    
    print("\n✓ GitHub API analysis complete!")
    print(f"✓ Check './output_github' folder for results")


def print_menu():
    """Print the main menu"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   DEPENDENCY GRAPH BUILDER - TEST SUITE                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Available OpenAPI Specs:

  ─── LOCAL SPECS ───────────────────────────────────────────────────────────
""")
    
    # Print local specs with numbers
    menu_items = {}
    idx = 1
    
    for key, info in LOCAL_SPECS.items():
        exists = "✓" if os.path.exists(info['path']) else "✗"
        print(f"  {idx:2}. [{exists}] {info['name']:<25} - {info['description']}")
        menu_items[str(idx)] = ('local', key)
        idx += 1
    
    print("""
  ─── REMOTE SPECS (will download) ──────────────────────────────────────────
""")
    
    print(f"  {idx:2}. [↓] Petstore API             - Classic pet store example")
    menu_items[str(idx)] = ('remote', 'petstore')
    idx += 1
    
    print(f"  {idx:2}. [↓] GitHub API               - Complex API (600+ operations)")
    menu_items[str(idx)] = ('remote', 'github')
    idx += 1
    
    print("""
  ─── BATCH OPTIONS ─────────────────────────────────────────────────────────
""")
    
    print(f"  {idx:2}. Run ALL local specs")
    menu_items[str(idx)] = ('batch', 'all_local')
    idx += 1
    
    print(f"  {idx:2}. Run ALL specs (local + remote)")
    menu_items[str(idx)] = ('batch', 'all')
    idx += 1
    
    print("""
  ─────────────────────────────────────────────────────────────────────────────
   q. Quit
   
Legend: [✓] File exists  [✗] File not found  [↓] Will download
""")
    
    return menu_items


if __name__ == "__main__":
    import sys
    
    menu_items = print_menu()
    
    choice = input("Enter your choice: ").strip()
    
    if choice.lower() == 'q':
        print("Exiting...")
    elif choice in menu_items:
        action_type, action_key = menu_items[choice]
        
        if action_type == 'local':
            # Run a single local spec
            test_local_spec(action_key)
            
        elif action_type == 'remote':
            # Run a remote spec
            if action_key == 'petstore':
                test_petstore()
            elif action_key == 'github':
                test_github()
                
        elif action_type == 'batch':
            if action_key == 'all_local':
                # Run all local specs that exist
                print("\n" + "="*80)
                print("RUNNING ALL LOCAL SPECS")
                print("="*80)
                
                for key, info in LOCAL_SPECS.items():
                    if os.path.exists(info['path']):
                        print(f"\n\n{'─'*80}")
                        print(f"Processing: {info['name']}")
                        print(f"{'─'*80}")
                        test_local_spec(key)
                    else:
                        print(f"\n⏭️  Skipping {info['name']} - file not found: {info['path']}")
                        
            elif action_key == 'all':
                # Run everything
                print("\n" + "="*80)
                print("RUNNING ALL SPECS (Local + Remote)")
                print("="*80)
                
                # Run local specs first
                for key, info in LOCAL_SPECS.items():
                    if os.path.exists(info['path']):
                        print(f"\n\n{'─'*80}")
                        print(f"Processing: {info['name']}")
                        print(f"{'─'*80}")
                        test_local_spec(key)
                    else:
                        print(f"\n⏭️  Skipping {info['name']} - file not found: {info['path']}")
                
                # Then remote specs
                print(f"\n\n{'─'*80}")
                print("Processing: Petstore API")
                print(f"{'─'*80}")
                test_petstore()
                
                print(f"\n\n{'─'*80}")
                print("Processing: GitHub API")
                print(f"{'─'*80}")
                test_github()
    else:
        print(f"Invalid choice: '{choice}'. Please try again.")
        print("Tip: Enter a number from the menu or 'q' to quit.")