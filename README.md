# Brest MCP Server

## Table of Contents
- [Description](#description)
- [Technologies](#technologies)
- [Installation](#installation)
- [Usage](#usage)
- [Tools](#tools)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Description
**Brest MCP Server** is a server implementation of the Model Context Protocol (MCP) for the Brest region. It provides a robust infrastructure for managing MCP-based interactions and includes an MCP inspector for debugging and monitoring.

The goal of this project is to facilitate the deployment and management of MCP services with a focus on simplicity and reliability.

## Technologies
- **Language**: Python 3.12.3 or compatible
- **Dependency Management**: uv
- **Inspector**: MCP Inspector via Node.js (`npx`)
- **Environment**: Virtual environment managed by `uv`
- **Inspector**: MCP Inspector via Node.js (`npx`)
- **Node.js** : Pour l'inspecteur MCP
## Installation
To install and configure Brest MCP Server locally, follow these steps:

1. Install `uv` (if not already installed):
    - On Linux/macOS:
        ```bash
        curl -LsSf https://astral.sh/uv/install.sh | sh
        ```
    - On Windows:
        ```bash
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        ```

2. Clone the repository:
    ```bash
    git clone https://github.com/Nijal-AI/Brest-mcp-server.git
    cd Brest-mcp-server
    ```

3. Create and activate the virtual environment:
    ```bash
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

4. Install the dependencies:
    ```bash
    uv sync
    ```

## Usage
To run the server locally, proceed as follows:

1. Ensure the virtual environment is activated:
    ```bash
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2. Start the server with the MCP Inspector:
    ```bash
    npx @modelcontextprotocol/inspector uv run brest-mcp
    ```

3. Access the MCP Inspector in your browser:
    - Proxy: `http://localhost:3000`
    - Web interface: `http://localhost:5173`

Example output:
```
Starting MCP inspector...
Proxy server listening on port 3000
🔍 MCP Inspector is up and running at http://localhost:5173 🚀
```
## Tools
If you want to discut with an AI agent using the Brest MCP Server, you can use the client provided in the `tools` directory :
```bash
uv run python tools/client.py src/server.py
```

## Agent
You can also chat with an AI agent using Brest MCP Server on A2A protocol.
To setup the agent :
```bash
echo "MCP_TRANSPORT=stdio" > src/.env
```
To run the agent :
```bash
uv run agent
```
You can try to use this agent with the demo ui of a2a-samples repository :
```bash
# Setup
git clone https://github.com/google-a2a/a2a-samples.git
echo "GOOGLE_API_KEY=your_api_key_here" > src/.env

# Run
cd a2a-samples/demo/ui
uv run main.py
```
Then go to `localhost:12000` and go to "Agents" and connect your Brest Expert Agent `localhost:10030`
You can add other agents if you want and go to Home and create a new conversation. You can now discuss with your agent(s).

## Development
For developers wishing to contribute or work on advanced features, follow these additional steps:

1. Ensure the virtual environment is set up and dependencies are installed:
    ``` bash
    uv venv
    uv sync
    ```

2. Use the MCP Inspector to debug and monitor the server:
    ``` bash
    npx @modelcontextprotocol/inspector uv run brest-mcp
    ```

3. Refer to the `pyproject.toml` file for details on dependencies and configurations.

## Contributing
Contributions are welcome! To propose changes, follow the [CONTRIBUTING.md](CONTRIBUTING.md) file.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
