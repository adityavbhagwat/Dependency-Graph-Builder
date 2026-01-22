import os
import sys
import requests
from typing import Optional, Dict, List
from dependency_graph import build_dependency_graph_from_openapi
from .stats import GraphStatistics

OPENAPI_DIR = os.path.join(os.getcwd(), "openapi_specs")
os.makedirs(OPENAPI_DIR, exist_ok=True)

# All available local OpenAPI specs with their output directories
LOCAL_SPECS: Dict[str, Dict[str, str]] = {
    "simple_api": {"path": "simple_api.yaml", "output": "./output_simple_api"},
    "user": {"path": "user.yaml", "output": "./output_user"},
    "market": {"path": "market.yaml", "output": "./output_market"},
    "person": {"path": "person.yaml", "output": "./output_person"},
    "project": {"path": "project.yaml", "output": "./output_project"},
    "features": {"path": "features.yaml", "output": "./output_features"},
    "fdic": {"path": "fdic.yaml", "output": "./output_fdic"},
    "ohsome": {"path": "ohsome.yaml", "output": "./output_ohsome"},
    "spotify": {"path": "spotify.yaml", "output": "./output_spotify"},
    "rest_countries": {"path": "rest-countries.yaml", "output": "./output_rest_countries"},
    "language_tool": {"path": "language-tool.yaml", "output": "./output_language_tool"},
    "genome_nexus": {"path": "genome-nexus.yaml", "output": "./output_genome_nexus"},
    "petstore": {"path": "openapi_specs/petstore.yaml", "output": "./output_petstore"},
    "github": {"path": "openapi_specs/github.json", "output": "./output_github"},
}

def download_openapi_spec(url: str, filename: str) -> Optional[str]:
    """Download OpenAPI spec into openapi_specs/ and return local path or None."""
    out_path = os.path.join(OPENAPI_DIR, filename)
    if os.path.exists(out_path):
        print(f"✓ {filename} already downloaded ({out_path})")
        return out_path
    print(f"Downloading {url} -> {out_path} ...")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(f"✓ Downloaded to {out_path}")
        return out_path
    except Exception as e:
        print(f"✗ Download failed: {e}")
        return None

def run_builder_for_spec(spec_path: str, dynamic: bool, output_dir: str):
    """Run the refactored builder wrapper on given spec."""
    if not os.path.isabs(spec_path):
        spec_path = os.path.join(os.getcwd(), spec_path)
    if not os.path.exists(spec_path):
        print(f"✗ Spec not found: {spec_path}")
        return
    print(f"\nRunning builder on: {spec_path}\n  dynamic={dynamic}  output={output_dir}\n")
    try:
        graph = build_dependency_graph_from_openapi(
            spec_path=spec_path,
            enable_dynamic=dynamic,
            export_results=True,
            output_dir=output_dir
        )
        print(f"✓ Build finished. Operations: {len(graph.operations)} Dependencies: {len(graph.dependencies)}")
        # Generate and print detailed statistics / benchmark report
        stats = GraphStatistics()
        stats.generate_report(graph, output_dir=output_dir)
    except Exception as e:
        print(f"✗ Error running builder: {e}")

def get_available_local_specs() -> List[str]:
    """Return list of available local spec names that exist on disk."""
    available = []
    for name, info in LOCAL_SPECS.items():
        if os.path.exists(info["path"]):
            available.append(name)
    return available

def run_all_local_specs(dynamic: bool = False):
    """Run builder for all available local OpenAPI specs."""
    available = get_available_local_specs()
    if not available:
        print("✗ No local specs found!")
        return
    
    print(f"\n{'='*80}")
    print(f"RUNNING ALL {len(available)} LOCAL OPENAPI SPECS")
    print(f"{'='*80}")
    
    results = {"success": [], "failed": []}
    
    for i, name in enumerate(available, 1):
        info = LOCAL_SPECS[name]
        print(f"\n[{i}/{len(available)}] Processing: {name}")
        print("-" * 40)
        try:
            run_builder_for_spec(info["path"], dynamic, info["output"])
            results["success"].append(name)
        except Exception as e:
            print(f"✗ Failed: {e}")
            results["failed"].append(name)
    
    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"  ✓ Successful: {len(results['success'])}/{len(available)}")
    for name in results["success"]:
        print(f"      - {name} -> {LOCAL_SPECS[name]['output']}")
    if results["failed"]:
        print(f"  ✗ Failed: {len(results['failed'])}/{len(available)}")
        for name in results["failed"]:
            print(f"      - {name}")
    print(f"{'='*80}\n")

def menu():
    """Interactive menu to create dependency graphs."""
    while True:
        print("\n" + "="*60)
        print("DEPENDENCY GRAPH TESTER - MENU")
        print("="*60)
        
        # List all available local specs
        available = get_available_local_specs()
        print(f"\n--- Local OpenAPI Specs ({len(available)} available) ---")
        for i, name in enumerate(available, 1):
            info = LOCAL_SPECS[name]
            print(f"  {i:2}) {name:<20} -> {info['output']}")
        
        print(f"\n--- Batch Operations ---")
        print(f"  a) Run ALL local specs (update all output folders)")
        
        print(f"\n--- Download Options ---")
        print(f"  d) Download & build from URL")
        print(f"  p) Download fresh Petstore from swagger.io")
        print(f"  g) Download fresh GitHub API (large)")
        
        print(f"\n--- Other ---")
        print(f"  c) Build from custom local path")
        print(f"  q) Quit")
        print("-"*60)
        
        choice = input("Select option (number or letter): ").strip().lower()

        # Handle numeric choices for local specs
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                name = available[idx]
                info = LOCAL_SPECS[name]
                dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
                run_builder_for_spec(info["path"], dyn, info["output"])
            else:
                print(f"✗ Invalid number. Choose 1-{len(available)}")
            continue

        # Run all local specs
        if choice == "a":
            dyn = input("Enable dynamic updates for all? (y/N): ").strip().lower() == "y"
            confirm = input(f"This will run {len(available)} specs. Continue? (y/N): ").strip().lower()
            if confirm == "y":
                run_all_local_specs(dyn)
            else:
                print("Cancelled.")

        # Download from URL
        elif choice == "d":
            url = input("Enter URL to OpenAPI spec: ").strip()
            if not url:
                print("✗ No URL provided")
                continue
            filename = input("Filename to save as (e.g. spec.yaml): ").strip() or os.path.basename(url)
            local = download_openapi_spec(url, filename)
            if local:
                dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
                out = input("Output directory (default ./output_download): ").strip() or "./output_download"
                run_builder_for_spec(local, dyn, out)

        # Download Petstore
        elif choice == "p":
            url = "https://petstore3.swagger.io/api/v3/openapi.yaml"
            local = download_openapi_spec(url, "petstore.yaml")
            if local:
                dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
                run_builder_for_spec(local, dyn, "./output_petstore")

        # Download GitHub
        elif choice == "g":
            url = "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json"
            local = download_openapi_spec(url, "github.json")
            if local:
                dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
                run_builder_for_spec(local, dyn, "./output_github")

        # Custom path
        elif choice == "c":
            spec = input("Enter path to local OpenAPI spec (yaml/json): ").strip()
            if not spec:
                print("✗ No path provided")
                continue
            dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
            out = input("Output directory (default ./output_custom): ").strip() or "./output_custom"
            run_builder_for_spec(spec, dyn, out)

        elif choice == "q":
            print("Exiting.")
            break
        else:
            print("Invalid choice. Enter a number or letter from the menu.")

if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        sys.exit(0)