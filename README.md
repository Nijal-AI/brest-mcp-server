# Brest MCP Server

A robust Model Context Protocol (MCP) server implementation for the Brest region, providing infrastructure for MCP-based interactions with built-in debugging and monitoring capabilities.

## Table of Contents
- [Description](#description)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Technologies](#technologies)
- [Installation](#installation)
- [Usage](#usage)
  - [Running the Server](#running-the-server)
  - [Using the Client](#using-the-client)
  - [AI Agent Integration](#ai-agent-integration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Description

**Brest MCP Server** is a server implementation of the Model Context Protocol (MCP) for the Brest region. It provides a robust infrastructure for managing MCP-based interactions and includes an MCP inspector for debugging and monitoring.

The goal of this project is to facilitate the deployment and management of MCP services with a focus on simplicity and reliability.

## Features

- 🚀 **MCP Protocol Implementation**: Full compliance with Model Context Protocol standards
- 🔍 **Built-in Inspector**: Debug and monitor your MCP server with the integrated web interface
- 🤖 **AI Agent Integration**: Support for A2A protocol and agent-to-agent communication
- 🐍 **Python-based**: Built with Python 3.12+ for modern development practices
- 📦 **UV Package Management**: Fast and reliable dependency management
- 🔧 **Development Tools**: Client tools and debugging utilities included

## Prerequisites

Before installing Brest MCP Server, ensure you have:

- **Python 3.12.3** or higher
- **Node.js** (for MCP Inspector)
- **Git** (for cloning the repository)
- **uv** package manager (installation instructions below)

## Technologies

- **Language**: Python 3.12.3 or compatible
- **Dependency Management**: uv
- **Inspector**: MCP Inspector via Node.js (`npx`)
- **Environment**: Virtual environment managed by `uv`
- **Protocol**: Model Context Protocol (MCP) and A2A (Agent-to-Agent)
## Installation

To install and configure Brest MCP Server locally, follow these steps:

1. **Install `uv`** (if not already installed):
    - On Linux/macOS:
        ```bash
        curl -LsSf https://astral.sh/uv/install.sh | sh
        ```
    - On Windows:
        ```powershell
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        ```

2. **Clone the repository**:
    ```bash
    git clone https://github.com/Nijal-AI/Brest-mcp-server.git
    cd Brest-mcp-server
    ```

3. **Create and activate the virtual environment**:
    ```bash
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

4. **Install the dependencies**:
    ```bash
    uv sync
    ```

## Usage

### Running the Server

To run the server locally, proceed as follows:

1. **Ensure the virtual environment is activated**:
    ```bash
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2. **Start the server with the MCP Inspector**:
    ```bash
    npx @modelcontextprotocol/inspector uv run brest-mcp
    ```

3. **Access the MCP Inspector in your browser**:
    - Proxy: `http://localhost:3000`
    - Web interface: `http://localhost:5173`

Example output:
```
Starting MCP inspector...
Proxy server listening on port 3000
🔍 MCP Inspector is up and running at http://localhost:5173 🚀
```

### Using the Client

If you want to communicate with an AI agent using the Brest MCP Server, you can use the client provided in the `tools` directory:

```bash
uv run python tools/client.py src/server.py
```

### AI Agent Integration

You can also chat with an AI agent using Brest MCP Server on A2A protocol.

1. **Setup the agent**:
    ```bash
    echo "MCP_TRANSPORT=stdio" > src/.env
    ```

2. **Run the agent**:
    ```bash
    uv run agent
    ```

3. **Use with A2A samples demo** (optional):
    ```bash
    # Setup
    git clone https://github.com/google-a2a/a2a-samples.git
    echo "GOOGLE_API_KEY=your_api_key_here" > a2a-samples/demo/ui/.env

    # Run
    cd a2a-samples/demo/ui
    uv run main.py
    ```
    
    Then navigate to `http://localhost:12000`, go to "Agents" and connect your Brest Expert Agent at `localhost:10030`. You can add other agents if you want, then go to Home and create a new conversation to discuss with your agent(s).

## Development

For developers wishing to contribute or work on advanced features, follow these additional steps:

1. **Ensure the virtual environment is set up and dependencies are installed**:
    ```bash
    uv venv
    uv sync
    ```

2. **Use the MCP Inspector to debug and monitor the server**:
    ```bash
    npx @modelcontextprotocol/inspector uv run brest-mcp
    ```

3. **Refer to the `pyproject.toml` file** for details on dependencies and configurations.

## Troubleshooting

### Common Issues

**Virtual environment activation fails**
- Ensure `uv` is properly installed and in your PATH
- Try recreating the virtual environment: `uv venv --force`

**MCP Inspector not starting**
- Ensure Node.js is installed: `node --version`
- Clear npm cache: `npm cache clean --force`
- Try installing the inspector globally: `npm install -g @modelcontextprotocol/inspector`

**Connection errors with A2A samples**
- Verify your Google API key is correctly set in the `.env` file
- Check that the Brest Expert Agent is running on `localhost:10030`
- Ensure all required ports are available and not blocked by firewall

**Dependencies installation fails**
- Update `uv` to the latest version: `uv self update`
- Clear the cache: `uv cache clean`
- Try installing with verbose output: `uv sync -v`

### Getting Help

If you encounter issues not covered here:
1. Check the [Issues](https://github.com/Nijal-AI/Brest-mcp-server/issues) section on GitHub
2. Review the MCP protocol documentation
3. Create a new issue with detailed error messages and your environment details

## Contributing

Contributions are welcome! To propose changes:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes** and ensure tests pass
4. **Follow the coding standards** defined in the project
5. **Submit a pull request** with a clear description of your changes

Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file for detailed guidelines.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
