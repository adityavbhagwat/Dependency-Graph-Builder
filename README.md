# API Dependency Graph Generator

This project analyzes an OpenAPI specification to build a dependency graph between API operations.

## How to Run

### 1. Setup a Python Virtual Environment

First, open a terminal or PowerShell in this directory and create a virtual environment. This keeps the project's dependencies isolated.

```sh
python -m venv .venv
```

### 2. Activate the Environment

**On Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```sh
source .venv/bin/activate
```

### 3. Install Dependencies

Install all the required libraries using the `requirements.txt` file.

```sh
pip install -r requirements.txt
```

### 4. Run the Tester

Run the main script. It will present a menu allowing you to choose an OpenAPI specification to process from the `openapi_specs` folder.

```sh
python -m dependency_graph.dependency_tester
```

### 5. Check the Output

After the script runs, it will create new `output` folders containing the generated dependency graph, statistics, and visualizations. To see visual representation of the graph.html , ``` cd ``` to the output folder which contains the graph.html file, run a server using command 
```
python -m http.server 8000
```
and then visit ``` localhost:8000/graph.html ```
