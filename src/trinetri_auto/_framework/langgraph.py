"""
LangGraph instrumentation for Trinetri.

Patches LangGraph callbacks and graph execution to emit OTEL spans.
"""

# Copyright 2025 Trinetri Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from typing import Any, Dict, Optional
import json
import time
from .._ids import get_correlation_id, new_step_id

try:
    from langgraph.graph.graph import CompiledGraph
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.pregel import Pregel
    from langgraph.pregel.executor import PregelExecutor
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class TrinetriLGCallback:
    """LangGraph callback for OpenTelemetry span emission with universal attributes."""
    
    def __init__(self, tracer_name: str = "trinetri.langgraph"):
        self.tracer = trace.get_tracer(tracer_name)
        self._active_spans: Dict[str, Any] = {}
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Called when a chain starts running."""
        correlation_id = get_correlation_id()
        step_id = new_step_id()
        
        span = self.tracer.start_span(
            name=f"lg.chain.{serialized.get('name', 'unknown')}",
            attributes={
                "agent.correlation_id": correlation_id,
                "step_id": step_id,
                "span_type": "framework",
                "framework.name": "langgraph",
                "framework.version": self._get_langgraph_version(),
                "lg.chain.name": serialized.get('name', 'unknown'),
                "lg.chain.type": serialized.get('_type', 'unknown'),
                "lg.inputs": json.dumps(inputs, default=str),
            }
        )
        
        run_id = kwargs.get('run_id', str(id(inputs)))
        self._active_spans[run_id] = span
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """Called when a chain finishes running."""
        run_id = kwargs.get('run_id')
        if run_id and run_id in self._active_spans:
            span = self._active_spans.pop(run_id)
            span.set_attribute("lg.outputs", json.dumps(outputs, default=str))
            span.set_status(Status(StatusCode.OK))
            span.end()
    
    def on_chain_error(self, error: Exception, **kwargs) -> None:
        """Called when a chain errors."""
        run_id = kwargs.get('run_id')
        if run_id and run_id in self._active_spans:
            span = self._active_spans.pop(run_id)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.set_attribute("error.type", type(error).__name__)
            span.set_attribute("error.message", str(error))
            span.end()
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Called when a tool starts running."""
        correlation_id = get_correlation_id()
        step_id = new_step_id()
        
        span = self.tracer.start_span(
            name=f"lg.tool.{serialized.get('name', 'unknown')}",
            attributes={
                "agent.correlation_id": correlation_id,
                "step_id": step_id,
                "span_type": "tool",
                "framework.name": "langgraph",
                "lg.tool.name": serialized.get('name', 'unknown'),
                "lg.tool.input": input_str,
            }
        )
        
        run_id = kwargs.get('run_id', str(id(input_str)))
        self._active_spans[run_id] = span
    
    def on_tool_end(self, output: str, **kwargs) -> None:
        """Called when a tool finishes running."""
        run_id = kwargs.get('run_id')
        if run_id and run_id in self._active_spans:
            span = self._active_spans.pop(run_id)
            span.set_attribute("lg.tool.output", output)
            span.set_status(Status(StatusCode.OK))
            span.end()
    
    def on_tool_error(self, error: Exception, **kwargs) -> None:
        """Called when a tool errors."""
        run_id = kwargs.get('run_id')
        if run_id and run_id in self._active_spans:
            span = self._active_spans.pop(run_id)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.set_attribute("error.type", type(error).__name__)
            span.set_attribute("error.message", str(error))
            span.end()
    
    def _get_langgraph_version(self) -> str:
        """Get LangGraph version safely."""
        try:
            import langgraph
            return getattr(langgraph, '__version__', 'unknown')
        except:
            return 'unknown'


def instrument_langgraph() -> bool:
    """Instrument LangGraph with OpenTelemetry spans."""
    if not LANGGRAPH_AVAILABLE:
        return False
    
    try:
        # Monkey patch the CompiledGraph to include our callback
        original_invoke = CompiledGraph.invoke
        original_ainvoke = CompiledGraph.ainvoke
        
        callback = TrinetriLGCallback()
        
        def patched_invoke(self, input: Any, config: Optional[Dict] = None, **kwargs):
            """Patched invoke with instrumentation."""
            if config is None:
                config = {}
            
            # Add our callback to the config
            callbacks = config.get('callbacks', [])
            callbacks.append(callback)
            config['callbacks'] = callbacks
            
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            
            with trace.get_tracer("trinetri.langgraph").start_as_current_span(
                "lg.graph.invoke",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "step_id": step_id,
                    "span_type": "root",
                    "framework.name": "langgraph",
                    "lg.operation": "invoke",
                    "lg.input": json.dumps(input, default=str),
                }
            ) as span:
                try:
                    result = original_invoke(self, input, config, **kwargs)
                    span.set_attribute("lg.output", json.dumps(result, default=str))
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        async def patched_ainvoke(self, input: Any, config: Optional[Dict] = None, **kwargs):
            """Patched async invoke with instrumentation."""
            if config is None:
                config = {}
            
            # Add our callback to the config
            callbacks = config.get('callbacks', [])
            callbacks.append(callback)
            config['callbacks'] = callbacks
            
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            
            with trace.get_tracer("trinetri.langgraph").start_as_current_span(
                "lg.graph.ainvoke",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "step_id": step_id,
                    "span_type": "root",
                    "framework.name": "langgraph",
                    "lg.operation": "ainvoke",
                    "lg.input": json.dumps(input, default=str),
                }
            ) as span:
                try:
                    result = await original_ainvoke(self, input, config, **kwargs)
                    span.set_attribute("lg.output", json.dumps(result, default=str))
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Apply patches
        CompiledGraph.invoke = patched_invoke
        CompiledGraph.ainvoke = patched_ainvoke
        
        return True
    except Exception:
        return False


def get_callback() -> Optional[TrinetriLGCallback]:
    """Get a configured LangGraph callback for manual use."""
    if not LANGGRAPH_AVAILABLE:
        return None
    return TrinetriLGCallback()


def patch_langgraph() -> bool:
    """
    Patch LangGraph to emit OpenTelemetry spans.
    
    Returns:
        bool: True if patching was successful, False if LangGraph not available
        
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    try:
        import langgraph  # noqa: F401
        # TODO: Implement actual LangGraph patching
        # - Hook into graph execution callbacks
        # - Wrap StateGraph.invoke() and stream() methods
        # - Add universal attributes to spans
        raise NotImplementedError("LangGraph patching not yet implemented in Phase 1")
    except ImportError:
        # LangGraph not available, skip patching
        return False


def unpatch_langgraph() -> None:
    """
    Remove LangGraph patches.
    
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    raise NotImplementedError("LangGraph unpatching not yet implemented in Phase 1") 