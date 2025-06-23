# Trinetri Quick Start Guide

**Trinetri – zero-touch traces & eval for multi-agent LLMs**

This guide will walk you through setting up Trinetri for comprehensive observability of your multi-agent LLM workflows in under 10 minutes.

## 📋 Prerequisites

- **Python 3.9+** installed
- **Docker & Docker Compose** for the observability stack
- **Git** for cloning the repository

## 🚀 Step 1: Installation

### Option A: Framework-Specific Installation

```bash
# For LangGraph users
pip install trinetri_auto[langgraph]

# For CrewAI users
pip install trinetri_auto[crewai]

# For both frameworks
pip install trinetri_auto[frameworks]
```

### Option B: Complete Installation

```bash
# Install everything (recommended for getting started)
pip install trinetri_auto[all]
```

### Verify Installation

```bash
# Check if Trinetri is properly installed
python -c "import trinetri_auto; print('✅ Trinetri installed successfully')"

# Check CLI availability
trinetri --help
```

## 🐳 Step 2: Start Observability Stack

### Clone Repository

```bash
git clone https://github.com/trinetri/trinetri.git
cd trinetri
```

### Start Services

```bash
# Navigate to deployment directory
cd deploy/

# Start the full observability stack
docker-compose up -d

# Verify services are running
docker-compose ps
```

**Expected Output:**
```
NAME                 SERVICE             STATUS              PORTS
otel-collector       otel-collector      running             0.0.0.0:4317-4318->4317-4318/tcp
grafana              grafana             running             0.0.0.0:3000->3000/tcp
tempo                tempo               running             0.0.0.0:3200->3200/tcp
postgres             postgres            running             0.0.0.0:5432->5432/tcp
```

### Service URLs

Once started, you'll have access to:

- **🎨 Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **📡 OTLP Endpoint**: http://localhost:4318
- **🔍 Tempo Query**: http://localhost:3200
- **🗄️ PostgreSQL**: localhost:5432

![Screenshot: Docker services running](screenshots/docker-compose-services.png)
*Screenshot placeholder: Docker Compose services status*

## ⚙️ Step 3: Environment Configuration

Set up the required environment variables:

```bash
# Required: OpenTelemetry configuration
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=my-agent-app

# Optional: Additional configuration
export OTEL_RESOURCE_ATTRIBUTES="service.version=1.0.0,deployment.environment=development"
export TRINETRI_LOG_LEVEL=INFO
export TRINETRI_EVAL_ENABLED=true
```

### Verify Configuration

```bash
# Check system health
trinetri doctor

# Expected output:
# ✅ OTEL endpoint reachable (http://localhost:4318)
# ✅ Dependencies installed
# ✅ Instrumentation active
# ✅ Evaluation system ready
```

![Screenshot: Health check output](screenshots/trinetri-doctor-success.png)
*Screenshot placeholder: Successful health check*

## 🤖 Step 4: LangGraph Demo (Full Example)

Create a new Python file called `langgraph_demo.py`:

```python
"""
Trinetri LangGraph Demo - Complete Multi-Agent Workflow
This demo shows a research and summarization workflow with evaluation.
"""

import trinetri_auto  # 🎯 Auto-instruments everything - no other setup needed!

from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from trinetri_auto.eval import score_with
import json

# Define the state that flows between agents
class AgentState(TypedDict):
    topic: str
    messages: List[str]
    research_data: str
    summary: str
    final_report: str

# 🔬 Research Agent with Evaluation
@score_with(metric="g-eval", threshold=0.8)
def research_agent(state: AgentState) -> AgentState:
    """
    Research agent that gathers information on a topic.
    Will be gated by evaluation - only proceeds if score >= 0.8
    """
    topic = state["topic"]
    
    # Simulate research work (replace with your LLM call)
    research_data = f"""
    Research findings for '{topic}':
    - Key insight 1: Important discovery about {topic}
    - Key insight 2: Statistical analysis shows 85% improvement
    - Key insight 3: Industry experts recommend this approach
    - Sources: [academic_paper_1.pdf, industry_report_2024.pdf]
    """
    
    messages = state["messages"] + [f"🔬 Research completed for: {topic}"]
    
    return {
        "topic": topic,
        "messages": messages,
        "research_data": research_data,
        "summary": state.get("summary", ""),
        "final_report": state.get("final_report", "")
    }

# 📝 Summary Agent (also auto-traced)
def summary_agent(state: AgentState) -> AgentState:
    """
    Summary agent that creates a concise summary of research findings.
    """
    research_data = state["research_data"]
    
    # Simulate summarization (replace with your LLM call)
    summary = f"""
    EXECUTIVE SUMMARY:
    
    Topic: {state['topic']}
    
    Key Findings:
    • Significant insights discovered through comprehensive research
    • 85% improvement metric identified as critical success factor
    • Expert consensus supports recommended approach
    
    Confidence Level: High
    Data Quality: Verified from multiple sources
    """
    
    messages = state["messages"] + ["📝 Summary generated"]
    
    return {
        "topic": state["topic"],
        "messages": messages,
        "research_data": research_data,
        "summary": summary,
        "final_report": state.get("final_report", "")
    }

# 📊 Report Agent with Custom Evaluation
def custom_quality_evaluator(input_data: str, output_data: str) -> float:
    """Custom evaluator that checks report quality"""
    # Simple quality metrics (replace with your logic)
    quality_score = 0.0
    
    if len(output_data) > 100:  # Minimum length
        quality_score += 0.3
    if "Key Findings" in output_data:  # Structure check
        quality_score += 0.3
    if "Confidence Level" in output_data:  # Confidence reporting
        quality_score += 0.4
    
    return min(quality_score, 1.0)

@score_with(metric=custom_quality_evaluator, threshold=0.9)
def report_agent(state: AgentState) -> AgentState:
    """
    Report agent that creates the final deliverable.
    Uses custom evaluation with high threshold (0.9)
    """
    summary = state["summary"]
    research_data = state["research_data"]
    
    # Simulate report generation
    final_report = f"""
    🎯 FINAL ANALYSIS REPORT
    
    {summary}
    
    DETAILED FINDINGS:
    {research_data}
    
    RECOMMENDATIONS:
    1. Implement the recommended approach immediately
    2. Monitor the 85% improvement metric closely
    3. Continue research in adjacent areas
    
    STATUS: ✅ COMPLETE
    QUALITY SCORE: Evaluated and approved
    """
    
    messages = state["messages"] + ["📊 Final report completed"]
    
    return {
        "topic": state["topic"],
        "messages": messages,
        "research_data": research_data,
        "summary": summary,
        "final_report": final_report
    }

# Decision function to route workflow
def should_continue(state: AgentState) -> str:
    """Determine next step in the workflow"""
    if not state.get("research_data"):
        return "research"
    elif not state.get("summary"):
        return "summary"
    elif not state.get("final_report"):
        return "report"
    else:
        return END

def main():
    """Run the complete multi-agent workflow"""
    
    # Build the agent graph
    workflow = StateGraph(AgentState)
    
    # Add agents as nodes
    workflow.add_node("research", research_agent)
    workflow.add_node("summary", summary_agent)
    workflow.add_node("report", report_agent)
    
    # Define the workflow structure
    workflow.set_entry_point("research")
    workflow.add_edge("research", "summary")
    workflow.add_edge("summary", "report")
    workflow.add_edge("report", END)
    
    # Compile the graph
    app = workflow.compile()
    
    # 🚀 Execute the workflow (fully instrumented!)
    print("🚀 Starting multi-agent workflow...")
    print("📡 Traces will appear in Grafana at http://localhost:3000")
    print()
    
    initial_state = {
        "topic": "AI Agent Optimization Strategies",
        "messages": ["🎬 Workflow started"],
        "research_data": "",
        "summary": "",
        "final_report": ""
    }
    
    try:
        # Execute with automatic tracing and evaluation
        result = app.invoke(initial_state)
        
        print("✅ Workflow completed successfully!")
        print("\n📋 Final Messages:")
        for message in result["messages"]:
            print(f"  {message}")
            
        print(f"\n📊 Final Report Preview:")
        print(result["final_report"][:200] + "...")
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        print("💡 Check Grafana for detailed error traces")

if __name__ == "__main__":
    main()
```

### Run the Demo

```bash
# Execute the demo
python langgraph_demo.py
```

**Expected Output:**
```
🚀 Starting multi-agent workflow...
📡 Traces will appear in Grafana at http://localhost:3000

✅ Workflow completed successfully!

📋 Final Messages:
  🎬 Workflow started
  🔬 Research completed for: AI Agent Optimization Strategies
  📝 Summary generated
  📊 Final report completed

📊 Final Report Preview:
🎯 FINAL ANALYSIS REPORT

EXECUTIVE SUMMARY:

Topic: AI Agent Optimization Strategies...
```

![Screenshot: Demo execution output](screenshots/demo-execution.png)
*Screenshot placeholder: Demo running in terminal*

## 📊 Step 5: View Your Traces

### Access Grafana

1. Open your browser and go to http://localhost:3000
2. Login with:
   - **Username**: `admin`
   - **Password**: `admin`
3. Navigate to the pre-configured Trinetri dashboard

![Screenshot: Grafana login](screenshots/grafana-login.png)
*Screenshot placeholder: Grafana login screen*

### Explore Your Traces

You'll see comprehensive traces showing:

- **🔗 Trace Waterfall**: Complete workflow execution timeline
- **📊 Evaluation Metrics**: Real-time quality scores and pass/fail status
- **💰 Cost Analysis**: Token usage and cost tracking per agent
- **⚡ Performance**: Latency and throughput metrics
- **🔍 Error Tracking**: Detailed error traces when issues occur

![Screenshot: Grafana dashboard overview](screenshots/grafana-dashboard-overview.png)
*Screenshot placeholder: Main Grafana dashboard with traces*

### Universal ID Schema in Action

Every span includes the universal attributes for complete traceability:

| Attribute | Example Value | Description |
|-----------|---------------|-------------|
| `agent.correlation_id` | `wf_2024_01_15_abc123def` | Links all operations in this workflow |
| `agent.agent_id` | `research_agent_xyz789` | Identifies the specific agent instance |
| `agent.parent_agent_id` | `coordinator_agent_456` | Shows agent hierarchy |
| `agent.step_id` | `step_20240115_143022_001` | Unique identifier for this execution step |
| `eval.metric` | `g-eval` | Which evaluation method was used |
| `eval.score` | `0.85` | Actual evaluation score (0.0-1.0) |
| `eval.pass` | `true` | Whether it passed the threshold |
| `span.type` | `agent` | Type of operation (agent/tool/llm/eval) |

![Screenshot: Span attributes detail](screenshots/span-attributes-detail.png)
*Screenshot placeholder: Detailed view of span attributes*

## 🎯 Step 6: Advanced Features

### Custom Agent Instrumentation

Instrument your own agent classes:

```bash
# Instrument any Python class as an agent
trinetri instrument myapp.agents:CustomAgent --role coordinator

# Verify instrumentation
trinetri doctor --verbose
```

### CrewAI Integration

If you're using CrewAI, it's automatically detected:

```python
import trinetri_auto  # Auto-instruments CrewAI
from crewai import Agent, Task, Crew

# Your existing CrewAI code works unchanged
researcher = Agent(
    role='Research Specialist',
    goal='Find comprehensive information',
    backstory='Expert researcher with access to various sources'
)

# Tasks and crews are automatically traced
```

### Custom Evaluation Metrics

Create your own evaluation functions:

```python
from trinetri_auto.eval import score_with

def domain_specific_evaluator(input_text: str, output_text: str) -> float:
    """Custom evaluator for your specific domain"""
    score = 0.0
    
    # Your custom evaluation logic
    if "technical_accuracy" in output_text.lower():
        score += 0.4
    if len(output_text.split()) > 50:  # Sufficient detail
        score += 0.3
    if "conclusion" in output_text.lower():  # Has conclusion
        score += 0.3
    
    return min(score, 1.0)

@score_with(metric=domain_specific_evaluator, threshold=0.8)
def my_agent_function(prompt: str) -> str:
    # Your agent logic here
    return "Agent response with technical_accuracy and conclusion"
```

## 🔧 Step 7: Troubleshooting

### Common Issues

#### 1. "OTEL endpoint not reachable"

```bash
# Check if Docker services are running
docker-compose ps

# Restart services if needed
cd deploy/
docker-compose down
docker-compose up -d

# Verify endpoint
curl -f http://localhost:4318/v1/traces || echo "Endpoint not ready"
```

#### 2. "Dependencies not found"

```bash
# Reinstall with all dependencies
pip install --upgrade trinetri_auto[all]

# Check specific framework support
python -c "import langgraph; print('LangGraph available')"
python -c "import crewai; print('CrewAI available')"
```

#### 3. "No traces appearing"

```bash
# Verify environment variables
echo $OTEL_EXPORTER_OTLP_ENDPOINT
echo $OTEL_SERVICE_NAME

# Check instrumentation status
trinetri doctor --verbose

# Enable debug logging
export TRINETRI_LOG_LEVEL=DEBUG
python your_script.py
```

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
import trinetri_auto

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('trinetri_auto')
logger.setLevel(logging.DEBUG)

# Your code here - will show detailed trace information
```

## 🎓 Next Steps

### 1. Explore Advanced Features

- **📊 Custom Dashboards**: Create specialized Grafana dashboards
- **🔍 TraceQL Queries**: Write advanced trace queries
- **📈 Alerting**: Set up alerts for quality degradation
- **💾 Data Export**: Export trace data for analysis

### 2. Production Deployment

- **🔒 Security**: Configure authentication and HTTPS
- **📈 Scaling**: Deploy collector clusters for high throughput
- **💾 Storage**: Configure long-term storage backends
- **🔄 CI/CD**: Integrate with your deployment pipeline

### 3. Integration Examples

- **🤖 OpenAI/Anthropic**: Automatic LLM call instrumentation
- **🔌 Custom Tools**: Instrument external API calls
- **📱 Web Apps**: Integrate with FastAPI/Flask applications
- **☁️ Cloud**: Deploy on AWS/GCP/Azure

### 4. Community & Support

- **📖 Documentation**: https://trinetri.readthedocs.io
- **💬 Discussions**: Join our GitHub Discussions
- **🐛 Issues**: Report bugs and request features
- **📧 Email**: support@trinetri.dev

## 📝 Summary

You've successfully set up Trinetri and seen:

✅ **Zero-touch instrumentation** - Just import and go  
✅ **Universal ID tracking** - Complete trace correlation  
✅ **In-trace evaluation** - Real-time quality gates  
✅ **Multi-agent workflows** - LangGraph and CrewAI support  
✅ **Comprehensive observability** - Grafana dashboards and metrics  

Your multi-agent LLM workflows now have enterprise-grade observability with minimal setup effort.

---

**🎉 Welcome to the Trinetri community! Your agents are now fully observable.**

![Screenshot: Success celebration](screenshots/success-celebration.png)
*Screenshot placeholder: Successful setup completion* 