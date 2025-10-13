"""
Test script to download OpenAPI spec and build dependency graph
"""

import os
import requests

# Import from your dependency_graph.py
from dependency_graph import build_dependency_graph_from_openapi

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


def test_simple_api():
    """Test with the simple User API from a local file"""
    print("\n" + "="*80)
    print("TESTING WITH SIMPLE USER API")
    print("="*80)
    
    spec_path = "simple_api.yaml"
    if not os.path.exists(spec_path):
        print(f"✗ Error: '{spec_path}' not found. Please create it first.")
        return

    # Build dependency graph
    print("\nBuilding dependency graph...\n")
    graph = build_dependency_graph_from_openapi(
        spec_path=spec_path,
        enable_dynamic=False,
        export_results=True,
        output_dir="./output_simple"
    )
    
    # Print some interesting information
    print("\n" + "="*80)
    print("INTERESTING FINDINGS")
    print("="*80)
    
    # Show the sequence for getUserById
    if 'getUserById' in graph.operations:
        op = graph.operations['getUserById']
        sequence = graph.get_operation_sequence(op)
        print(f"\nTo execute: {op.method.value} {op.path}")
        print(f"   You need to first execute:")
        for j, seq_op in enumerate(sequence[:-1], 1):
            print(f"      {j}. {seq_op.method.value} {seq_op.path}")
    
    print("\n" + "="*80)
    print("✓ Test completed!")
    print(f"✓ Check './output_simple' folder for results.")
    print("="*80)


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


if __name__ == "__main__":
    import sys
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   DEPENDENCY GRAPH BUILDER - TEST SUITE                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Available tests:
  1. Simple User API (Local file - very fast)
  2. Petstore API (Downloads spec)
  3. GitHub API (Complex - downloads spec)
  4. All

""")
    
    choice = input("Enter your choice (1/2/3/4) or 'q' to quit: ").strip()
    
    if choice == '1':
        test_simple_api()
    elif choice == '2':
        test_petstore()
    elif choice == '3':
        test_github()
    elif choice == '4':
        test_simple_api()
        print("\n\n")
        test_petstore()
        print("\n\n")
        test_github()
    elif choice.lower() == 'q':
        print("Exiting...")
    else:
        print("Invalid choice. Running Simple User API test by default...")
        test_simple_api()