# ADR-0001: Agent Span Schema

**Status:** Accepted  
**Date:** 2025-01-01  
**Authors:** Trinetri Team  

## Context

Trinetri requires a universal correlation model to track multi-agent LLM workflows across different frameworks (LangGraph, CrewAI, custom agents) and protocols (Anthropic MCP, AWS A2A). The span schema must support both sparse APM-style observability and dense local analytics while maintaining correlation across complex agent interactions.

## Decision

We adopt a universal span attribute schema based on OpenTelemetry with the following required attributes for all Trinetri-instrumented spans:

### Universal Attributes

```yaml
# Correlation and Identity
agent.correlation_id: string     # UUID4 - groups related spans across agents
agent.role: string              # Human-readable role (e.g., "researcher", "writer")
agent.id: string                # Unique agent instance ID ("agt-<12hex>")
step.id: string                 # Unique step ID ("stp-<12hex>")

# Span Classification
span.type: string               # Values: "root", "tool", "eval", "agent", "framework"

# Framework Context (optional)
agent.class_name: string        # For custom agents
agent.method_name: string       # Method being instrumented
framework.name: string          # "langgraph", "crewai", etc.
framework.version: string       # Framework version

# Protocol Context (optional)
mcp.context_id: string          # Anthropic MCP context identifier
a2a.thread_id: string           # AWS A2A thread identifier

# Tool/LLM Context (for span.type="tool")
llm.model: string               # Model name (e.g., "gpt-4", "claude-3")
llm.provider: string            # "openai", "anthropic", etc.
llm.tokens.input: int           # Input token count
llm.tokens.output: int          # Output token count
llm.tokens.total: int           # Total token count

# Evaluation Context (for span.type="eval")
eval.metric: string             # Metric name (e.g., "g-eval", "faithfulness")
eval.score: float               # Numeric score (0.0 to 1.0)
eval.threshold: float           # Pass/fail threshold
eval.passed: bool               # Whether evaluation passed
```

### Span Type Taxonomy

1. **"root"** - Top-level workflow spans (sent to APM)
   - LangGraph graph execution
   - CrewAI crew kickoff
   - Custom workflow entry points

2. **"tool"** - External tool/service calls (sent to APM)
   - LLM API calls (OpenAI, Anthropic)
   - HTTP requests
   - Database queries
   - MCP tool invocations

3. **"eval"** - Evaluation spans (sent to APM)
   - DeepEval metric calculations
   - Custom evaluation functions
   - Score summaries

4. **"agent"** - Individual agent operations (dense only)
   - Agent method calls
   - State transitions
   - Internal reasoning steps

5. **"framework"** - Framework-specific operations (dense only)
   - LangGraph node execution
   - CrewAI task processing
   - Internal orchestration

### Dual-Path Strategy

**Sparse Path (APM)**:
- `span.type` in ["root", "tool", "eval"]
- Tail-sampling retains these for Grafana Tempo/Datadog
- Optimized for high-level workflow visibility

**Dense Path (Local Analytics)**:
- All spans regardless of type
- Stored locally in Postgres → Parquet
- Detailed analysis and debugging

## Rationale

### Universal Correlation Model
- `agent.correlation_id` enables tracking across framework boundaries
- `agent.role` provides human-readable context
- `step.id` enables fine-grained tracing within workflows

### Span Type Classification
- Balances APM signal-to-noise ratio with comprehensive local data
- "root" spans provide workflow-level visibility
- "tool" spans capture external dependencies and costs
- "eval" spans enable evaluation-driven development

### OpenTelemetry Compliance
- Leverages existing tooling and standards
- Spans are standard OTEL with additional semantic attributes
- Compatible with existing APM platforms

### Framework Agnostic
- Same schema works for LangGraph, CrewAI, custom agents
- Protocol-specific attributes (MCP, A2A) are optional extensions
- Easy to add new frameworks without schema changes

## Consequences

### Positive
- **Unified observability** across all agent frameworks
- **APM integration** with existing monitoring infrastructure
- **Correlation tracking** for complex multi-agent workflows
- **Cost visibility** through token usage tracking
- **Evaluation integration** for continuous improvement

### Negative
- **Additional overhead** from span attribute population
- **Storage requirements** for dense local data
- **Schema evolution** complexity for breaking changes

### Mitigation
- Lazy attribute computation where possible
- Configurable sampling rates for dense data
- Versioned schema with backward compatibility

## Alternatives Considered

### 1. Framework-Specific Schemas
**Rejected**: Would require separate integrations for each framework and prevent correlation across boundaries.

### 2. Single-Path Storage (APM Only)
**Rejected**: Insufficient detail for debugging and analysis of agent behavior.

### 3. Custom Trace Format
**Rejected**: Would lose OpenTelemetry ecosystem benefits and existing tooling.

## Implementation Notes

### Phase 1 (Current)
- Implement core schema with stub patchers
- Focus on `agent.correlation_id` and basic span types
- Manual instrumentation via `instrument_agent()`

### Phase 2 (Future)
- Automatic framework detection and patching
- Token usage tracking for cost analysis
- DeepEval integration for evaluation spans

### Phase 3 (Future)
- MCP and A2A protocol support
- Advanced correlation analysis
- Real-time evaluation dashboards

## References

- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [DeepEval Documentation](https://docs.confident-ai.com/) 