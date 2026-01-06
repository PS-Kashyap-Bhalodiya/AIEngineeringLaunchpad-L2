# Weekend Wizard

A friendly CLI agent that plans chill mini-itineraries, tells you the current weather, suggests books, cracks jokes, and shares dog picture links. Built with MCP (Model Context Protocol) and runs locally using Ollama.

## Features

- **Weather** - Current conditions for given coordinates (Open-Meteo)
- **Books** - Simple recommendations by topic (Open Library)
- **Jokes** - Safe, one-liner jokes (JokeAPI)
- **Dog Photos** - Random dog image URLs (Dog CEO)
- **Trivia** - Multiple-choice questions (Open Trivia DB)

## Prerequisites

- Python 3.10+
- Ollama installed (from [ollama.com](https://ollama.com))

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install "mcp>=1.2" requests ollama
```

### 3. Install and pull the Ollama model

```bash
# Install Ollama from https://ollama.com if not already installed
ollama pull mistral:7b
```

## Running the Agent

```bash
python agent_fun.py
```

## Example Prompts

```
Plan a cozy Saturday in New York at (40.7128, -74.0060). Include the current weather, 2 book ideas about mystery, one joke, and a dog pic.
```

```
What's the temperature now at (37.7749, -122.4194)? Keep it brief.
```

```
Give me one trivia question.
```

## Architecture

```
User  <-->  Agent (LLM policy + loop)
                 |
                 v
           MCP Client (stdio)
                 |
                 v
         MCP Tools Server (Python)
         |   |    |     |
         |   |    |     +-- dog photo (Dog CEO)
         |   |    +-------- jokes (JokeAPI)
         |   +------------- books (Open Library)
         +----------------- weather (Open-Meteo)
             (optional) trivia (Open Trivia)
```

## Files

- [`server_fun.py`](server_fun.py) - MCP tools server with all API integrations
- [`agent_fun.py`](agent_fun.py) - Agent client with ReAct loop and tool calling

## Optional: Visual Tool Testing

```bash
npx @modelcontextprotocol/inspector
```

Then add a STDIO connection pointing to `python server_fun.py` to test each tool individually.