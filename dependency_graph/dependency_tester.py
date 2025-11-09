import os
import sys
import requests
from typing import Optional
from dependency_graph import build_dependency_graph_from_openapi

OPENAPI_DIR = os.path.join(os.getcwd(), "openapi_specs")
os.makedirs(OPENAPI_DIR, exist_ok=True)

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
    except Exception as e:
        print(f"✗ Error running builder: {e}")

def menu():
    """Interactive menu to create dependency graphs."""
    while True:
        print("\nDependency Graph Tester - Menu")
        print("1) Build from local simple_api.yaml")
        print("2) Download & build Petstore (swagger.io)")
        print("3) Download & build GitHub API (large)")
        print("4) Build from custom local spec path")
        print("5) Download from URL and build")
        print("q) Quit")
        choice = input("Select option: ").strip().lower()

        if choice == "1":
            spec = "C:\dependency_graph_project\simple_api.yaml"
            if not os.path.exists(spec):
                print(f"✗ Local file '{spec}' not found in cwd: {os.getcwd()}")
                continue
            dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
            out = "./output_simple"
            run_builder_for_spec(spec, dyn, out)

        elif choice == "2":
            url = "https://petstore3.swagger.io/api/v3/openapi.yaml"
            local = download_openapi_spec(url, "petstore.yaml")
            if local:
                dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
                out = "./output_petstore"
                run_builder_for_spec(local, dyn, out)

        elif choice == "3":
            url = "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json"
            local = download_openapi_spec(url, "github.json")
            if local:
                dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
                out = "./output_github"
                run_builder_for_spec(local, dyn, out)

        elif choice == "4":
            spec = input("Enter path to local OpenAPI spec (yaml/json): ").strip()
            if not spec:
                print("✗ No path provided")
                continue
            dyn = input("Enable dynamic updates? (y/N): ").strip().lower() == "y"
            out = input("Output directory (default ./output_custom): ").strip() or "./output_custom"
            run_builder_for_spec(spec, dyn, out)

        elif choice == "5":
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

        elif choice == "q":
            print("Exiting.")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        sys.exit(0)