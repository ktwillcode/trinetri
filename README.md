# Trinetri

**Trinetri – zero-touch traces & eval for multi-agent LLMs**

[![CI](https://github.com/trinetri/trinetri/actions/workflows/ci.yml/badge.svg)](https://github.com/trinetri/trinetri/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/trinetri-auto.svg)](https://badge.fury.io/py/trinetri-auto)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Comprehensive observability and in-trace evaluation for multi-agent LLM workflows with friction-less auto-instrumentation.

## 🚀 Quick Install

```bash
# Install with framework support
pip install trinetri_auto[frameworks]

# Or install with all optional dependencies
pip install trinetri_auto[all]
```

## ⚡ Quick Start

### 1. Start Observability Stack

```bash
# Clone and start the deployment stack
git clone https://github.com/trinetri/trinetri.git
cd trinetri/deploy
docker-compose up -d

# Set OpenTelemetry endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-agent-app
```

### 2. LangGraph Demo (20 lines)

```python
import trinetri_auto  # Auto-instruments everything
from langgraph.graph import StateGraph
from typing import TypedDict
from trinetri_auto.eval import score_with

class AgentState(TypedDict):
    messages: list[str]
    result: str

@score_with(metric="g-eval", threshold=0.8)
def research_node(state: AgentState) -> AgentState:
    """Research agent with evaluation gating"""
    # Your LLM call here - automatically traced
    result = "Research findings..."
    return {"messages": state["messages"], "result": result}

def summarize_node(state: AgentState) -> AgentState:
    """Summary agent - also auto-traced"""
    summary = f"Summary of: {state['result']}"
    return {"messages": state["messages"] + [summary], "result": summary}

# Build and run graph - fully instrumented
graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("summarize", summarize_node)
graph.add_edge("research", "summarize")
graph.set_entry_point("research")
graph.set_finish_point("summarize")

app = graph.compile()
result = app.invoke({"messages": [], "result": ""})
```

### 3. View Traces

Open Grafana at [http://localhost:3000](http://localhost:3000) to see your traces with full context.

## 📊 Universal ID Schema

Every span in Trinetri includes these universal attributes for complete traceability:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `agent.correlation_id` | string | Unique workflow execution ID | `wf_2024_01_15_abc123def` |
| `agent.agent_id` | string | Unique agent instance ID | `research_agent_xyz789` |
| `agent.parent_agent_id` | string | Parent agent ID (for hierarchies) | `coordinator_agent_456` |
| `agent.step_id` | string | Unique step/task execution ID | `step_20240115_143022_001` |
| `eval.metric` | string | Evaluation metric used | `g-eval`, `custom-score` |
| `eval.score` | float | Evaluation score (0.0-1.0) | `0.85` |
| `eval.pass` | boolean | Whether evaluation passed threshold | `true` |
| `span.type` | string | Type of operation | `agent`, `tool`, `llm`, `eval` |

## 🔧 Features

### ⚡ **Zero-Touch Instrumentation**
- **Auto-discovery**: Detects LangGraph, CrewAI, OpenAI, Anthropic automatically
- **No code changes**: Just `import trinetri_auto` and everything is traced
- **Universal compatibility**: Works with any OpenTelemetry-compatible backend

### 🎯 **In-Trace Evaluation**
- **Real-time gating**: `@score_with()` decorator stops execution on low scores
- **DeepEval integration**: Advanced LLM evaluation metrics
- **Custom metrics**: Bring your own evaluation functions
- **Threshold enforcement**: Configurable quality gates

### 🌐 **Multi-Agent Support**
- **LangGraph**: Complete graph execution tracing with node-level spans
- **CrewAI**: Agent and task instrumentation with role-based tracking
- **Custom agents**: Instrument any Python class with `trinetri instrument`

### 🔍 **Comprehensive LLM Tracking**
- **Token usage**: Input/output tokens, costs, and rate limiting
- **Model metadata**: Provider, model version, temperature settings
- **Content safety**: Automatic content truncation for performance
- **Error handling**: Graceful degradation on instrumentation failures

### 🛠️ **Developer Experience**
- **Health checking**: `trinetri doctor` validates your setup
- **CLI tools**: Dynamic instrumentation and status monitoring
- **Rich logging**: Detailed debug information when needed
- **Type safety**: Full MyPy support with proper type hints

## 📦 Installation Options

### Core Package
```bash
pip install trinetri_auto
```

### With Framework Support
```bash
# LangGraph support
pip install trinetri_auto[langgraph]

# CrewAI support  
pip install trinetri_auto[crewai]

# All frameworks
pip install trinetri_auto[frameworks]
```

### With Evaluation
```bash
# DeepEval integration
pip install trinetri_auto[deepeval]

# Everything included
pip install trinetri_auto[all]
```

## 🐳 Docker Deployment

Use the included deployment stack for instant observability:

```bash
# Start full stack (Collector + Tempo + Grafana + Postgres)
cd deploy/
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f
```

Services available:
- **Grafana**: http://localhost:3000 (admin/admin)
- **OTLP Endpoint**: http://localhost:4318
- **Tempo**: http://localhost:3200

## 🔍 CLI Usage

### Health Check
```bash
trinetri doctor
# ✅ OTEL endpoint reachable
# ✅ Dependencies installed  
# ✅ Instrumentation active
```

### Dynamic Instrumentation
```bash
# Instrument custom agent class
trinetri instrument myapp.agents:CustomAgent --role coordinator

# Check what's instrumented
trinetri doctor --verbose
```

## 📈 Advanced Usage

### Custom Evaluation Metrics
```python
from trinetri_auto.eval import score_with

def custom_evaluator(input_text: str, output_text: str) -> float:
    # Your custom logic here
    return 0.95

@score_with(metric=custom_evaluator, threshold=0.9)
def my_agent_function(prompt: str) -> str:
    # Will only proceed if custom_evaluator returns >= 0.9
    return "Agent response"
```

### Manual Span Creation
```python
from trinetri_auto.agent import create_agent_span

with create_agent_span("custom-operation", agent_role="validator") as span:
    # Your custom logic here
    span.set_attribute("custom.metadata", "value")
    result = do_something()
```

### Environment Configuration
```bash
# Required
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-agent-app

# Optional
export OTEL_RESOURCE_ATTRIBUTES="service.version=1.0.0,deployment.environment=prod"
export TRINETRI_LOG_LEVEL=INFO
export TRINETRI_EVAL_ENABLED=true
```

## 🏗️ Architecture

Trinetri provides observability through three core components:

1. **Auto-Instrumentation**: Automatic detection and patching of supported frameworks
2. **Universal ID System**: Consistent correlation across all agent operations  
3. **In-Trace Evaluation**: Real-time quality gates with configurable thresholds

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your Agents   │    │    Trinetri      │    │  Observability  │
│                 │───▶│ Auto-Instrument  │───▶│     Backend     │
│ LangGraph       │    │                  │    │                 │
│ CrewAI          │    │ • Universal IDs  │    │ • Grafana       │
│ Custom          │    │ • Span Creation  │    │ • Tempo         │
│                 │    │ • Evaluation     │    │ • Jaeger        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🤝 Contributing

We welcome contributions! Please see our [contributing guidelines](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Clone repository
git clone https://github.com/trinetri/trinetri.git
cd trinetri

# Install with development dependencies
pip install -e .[all,dev]

# Run tests
pytest tests/

# Run linting
ruff check .
ruff format .
mypy src/trinetri_auto
```

## 📄 License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## 🔗 Links

- **Documentation**: https://trinetri.readthedocs.io
- **PyPI Package**: https://pypi.org/project/trinetri-auto/
- **GitHub Repository**: https://github.com/trinetri/trinetri
- **Issue Tracker**: https://github.com/trinetri/trinetri/issues
- **Changelog**: https://github.com/trinetri/trinetri/blob/main/CHANGELOG.md

## 🆘 Support

- **Documentation**: Check our [docs](https://trinetri.readthedocs.io) first
- **Issues**: Report bugs on [GitHub Issues](https://github.com/trinetri/trinetri/issues)
- **Discussions**: Join our [GitHub Discussions](https://github.com/trinetri/trinetri/discussions)
- **Email**: support@trinetri.dev

---

**Built with ❤️ for the AI agent community**
