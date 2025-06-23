"""
CrewAI instrumentation for Trinetri.

Patches CrewAI event listeners and callbacks to emit OTEL spans.
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
from typing import Any, Dict, Optional, Union
import json
import time
from .._ids import get_correlation_id, new_agent_id, new_step_id

try:
    import crewai
    from crewai import Agent, Task, Crew
    from crewai.agent import Agent as CrewAgent
    from crewai.task import Task as CrewTask
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


def patch_crewai() -> bool:
    """
    Patch CrewAI to emit OpenTelemetry spans.
    
    Returns:
        bool: True if patching was successful, False if CrewAI not available
        
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    try:
        import crewai  # noqa: F401
        # TODO: Implement actual CrewAI patching
        # - Hook into step_callback and task_callback functions
        # - Wrap Crew.kickoff() method
        # - Add event listeners for ToolResult, AgentAction, TaskOutput
        # - Add universal attributes to spans
        raise NotImplementedError("CrewAI patching not yet implemented in Phase 1")
    except ImportError:
        # CrewAI not available, skip patching
        return False


def unpatch_crewai() -> None:
    """
    Remove CrewAI patches.
    
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    raise NotImplementedError("CrewAI unpatching not yet implemented in Phase 1")


def instrument_crewai() -> bool:
    """Instrument CrewAI with OpenTelemetry spans."""
    if not CREWAI_AVAILABLE:
        return False
    
    try:
        # Monkey patch Agent.__init__ to assign agent_id once
        original_agent_init = CrewAgent.__init__
        
        def patched_agent_init(self, *args, **kwargs):
            """Patched Agent init with agent_id assignment."""
            result = original_agent_init(self, *args, **kwargs)
            
            # Assign agent_id if not already present
            if not hasattr(self, '_trinetri_agent_id'):
                self._trinetri_agent_id = new_agent_id()
                
                # Create span for agent initialization
                correlation_id = get_correlation_id()
                with trace.get_tracer("trinetri.crewai").start_as_current_span(
                    "crewai.agent.init",
                    attributes={
                        "agent.correlation_id": correlation_id,
                        "agent_id": self._trinetri_agent_id,
                        "span_type": "agent",
                        "framework.name": "crewai",
                        "framework.version": _get_crewai_version(),
                        "crewai.agent.role": getattr(self, 'role', 'unknown'),
                        "crewai.agent.goal": getattr(self, 'goal', 'unknown'),
                        "crewai.agent.backstory": getattr(self, 'backstory', 'unknown')[:200],  # Truncate long backstories
                        "crewai.agent.verbose": getattr(self, 'verbose', False),
                        "crewai.agent.allow_delegation": getattr(self, 'allow_delegation', False),
                    }
                ) as span:
                    span.set_status(Status(StatusCode.OK))
            
            return result
        
        # Monkey patch Agent execute methods
        if hasattr(CrewAgent, 'execute_task'):
            original_execute_task = CrewAgent.execute_task
            
            def patched_execute_task(self, task: Any, context: Optional[str] = None, tools: Optional[list] = None):
                """Patched execute_task with instrumentation."""
                correlation_id = get_correlation_id()
                step_id = new_step_id()
                agent_id = getattr(self, '_trinetri_agent_id', new_agent_id())
                
                with trace.get_tracer("trinetri.crewai").start_as_current_span(
                    "crewai.agent.execute_task",
                    attributes={
                        "agent.correlation_id": correlation_id,
                        "agent_id": agent_id,
                        "step_id": step_id,
                        "span_type": "agent",
                        "framework.name": "crewai",
                        "crewai.operation": "execute_task",
                        "crewai.agent.role": getattr(self, 'role', 'unknown'),
                        "crewai.task.description": getattr(task, 'description', str(task))[:500],  # Truncate long descriptions
                        "crewai.context": context[:200] if context else None,
                        "crewai.tools_count": len(tools) if tools else 0,
                    }
                ) as span:
                    try:
                        start_time = time.time()
                        result = original_execute_task(self, task, context, tools)
                        duration_ms = (time.time() - start_time) * 1000
                        
                        span.set_attribute("crewai.duration_ms", duration_ms)
                        span.set_attribute("crewai.result", str(result)[:1000])  # Truncate long results
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            CrewAgent.execute_task = patched_execute_task
        
        # Monkey patch Task execution if available
        if hasattr(CrewTask, 'execute'):
            original_task_execute = CrewTask.execute
            
            def patched_task_execute(self, agent: Any = None, context: Optional[str] = None, tools: Optional[list] = None):
                """Patched Task execute with instrumentation."""
                correlation_id = get_correlation_id()
                step_id = new_step_id()
                agent_id = getattr(agent, '_trinetri_agent_id', new_agent_id()) if agent else new_agent_id()
                
                with trace.get_tracer("trinetri.crewai").start_as_current_span(
                    "crewai.task.execute",
                    attributes={
                        "agent.correlation_id": correlation_id,
                        "agent_id": agent_id,
                        "step_id": step_id,
                        "span_type": "framework",
                        "framework.name": "crewai",
                        "crewai.operation": "task_execute",
                        "crewai.task.description": getattr(self, 'description', 'unknown')[:500],
                        "crewai.task.expected_output": getattr(self, 'expected_output', 'unknown')[:200],
                        "crewai.agent.role": getattr(agent, 'role', 'unknown') if agent else 'no_agent',
                        "crewai.context": context[:200] if context else None,
                        "crewai.tools_count": len(tools) if tools else 0,
                    }
                ) as span:
                    try:
                        start_time = time.time()
                        result = original_task_execute(self, agent, context, tools)
                        duration_ms = (time.time() - start_time) * 1000
                        
                        span.set_attribute("crewai.duration_ms", duration_ms)
                        span.set_attribute("crewai.result", str(result)[:1000])  # Truncate long results
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            CrewTask.execute = patched_task_execute
        
        # Monkey patch Crew kickoff if available
        if hasattr(Crew, 'kickoff'):
            original_crew_kickoff = Crew.kickoff
            
            def patched_crew_kickoff(self, inputs: Optional[Dict[str, Any]] = None):
                """Patched Crew kickoff with instrumentation."""
                correlation_id = get_correlation_id()
                step_id = new_step_id()
                
                with trace.get_tracer("trinetri.crewai").start_as_current_span(
                    "crewai.crew.kickoff",
                    attributes={
                        "agent.correlation_id": correlation_id,
                        "step_id": step_id,
                        "span_type": "root",
                        "framework.name": "crewai",
                        "crewai.operation": "crew_kickoff",
                        "crewai.agents_count": len(getattr(self, 'agents', [])),
                        "crewai.tasks_count": len(getattr(self, 'tasks', [])),
                        "crewai.process": str(getattr(self, 'process', 'unknown')),
                        "crewai.inputs": json.dumps(inputs, default=str) if inputs else None,
                    }
                ) as span:
                    try:
                        start_time = time.time()
                        result = original_crew_kickoff(self, inputs)
                        duration_ms = (time.time() - start_time) * 1000
                        
                        span.set_attribute("crewai.duration_ms", duration_ms)
                        span.set_attribute("crewai.result", str(result)[:1000])  # Truncate long results
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            Crew.kickoff = patched_crew_kickoff
        
        # Apply the agent init patch
        CrewAgent.__init__ = patched_agent_init
        
        return True
    except Exception:
        return False


def _get_crewai_version() -> str:
    """Get CrewAI version safely."""
    try:
        import crewai
        return getattr(crewai, '__version__', 'unknown')
    except:
        return 'unknown'


def instrument_agent(agent_class: type, role: str) -> type:
    """Instrument a specific agent class with role-based observability."""
    if not CREWAI_AVAILABLE:
        return agent_class
    
    # Store original methods
    original_run = getattr(agent_class, 'run', None)
    original_act = getattr(agent_class, 'act', None)
    
    def create_instrumented_method(method_name: str, original_method):
        """Create an instrumented version of an agent method."""
        def instrumented_method(self, *args, **kwargs):
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            agent_id = getattr(self, '_trinetri_agent_id', new_agent_id())
            
            with trace.get_tracer("trinetri.crewai").start_as_current_span(
                f"crewai.agent.{method_name}",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "agent_id": agent_id,
                    "step_id": step_id,
                    "span_type": "agent",
                    "framework.name": "crewai",
                    "agent.role": role,
                    "crewai.operation": method_name,
                    "crewai.args": json.dumps(args, default=str)[:500],
                    "crewai.kwargs": json.dumps(kwargs, default=str)[:500],
                }
            ) as span:
                try:
                    start_time = time.time()
                    result = original_method(self, *args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    
                    span.set_attribute("crewai.duration_ms", duration_ms)
                    span.set_attribute("crewai.result", str(result)[:1000])
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        return instrumented_method
    
    # Apply instrumentation to available methods
    if original_run:
        setattr(agent_class, 'run', create_instrumented_method('run', original_run))
    
    if original_act:
        setattr(agent_class, 'act', create_instrumented_method('act', original_act))
    
    return agent_class 