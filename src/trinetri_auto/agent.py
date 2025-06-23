"""
Agent instrumentation utilities for Trinetri.

Provides decorators and utilities to instrument custom agent classes
with OpenTelemetry spans and universal correlation attributes.
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

import functools
import inspect
from typing import Any, Callable, Type, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ._ids import ensure_correlation_id, new_agent_id, new_step_id

T = TypeVar("T")

tracer = trace.get_tracer(__name__)


def instrument_agent(cls: Type[T], role: str) -> Type[T]:
    """
    Instrument an agent class with OpenTelemetry spans.
    
    Monkey-patches the class to wrap method calls in OTEL spans
    with universal attributes like agent.correlation_id, agent.role, etc.
    
    Args:
        cls: The agent class to instrument
        role: The role of this agent (e.g., "researcher", "writer", "critic")
        
    Returns:
        The instrumented class with wrapped methods
    """
    # Detect which method to instrument (run or act)
    method_to_wrap = None
    if hasattr(cls, "run") and callable(getattr(cls, "run")):
        method_to_wrap = "run"
    elif hasattr(cls, "act") and callable(getattr(cls, "act")):
        method_to_wrap = "act"
    else:
        # If neither run nor act exists, wrap the first public method found
        for attr_name in dir(cls):
            attr_value = getattr(cls, attr_name)
            if (
                not attr_name.startswith("_")
                and callable(attr_value)
                and not inspect.isbuiltin(attr_value)
            ):
                method_to_wrap = attr_name
                break
    
    if method_to_wrap is None:
        # No suitable method found, return class unchanged
        return cls
    
    # Get the original method
    original_method = getattr(cls, method_to_wrap)
    
    @functools.wraps(original_method)
    def wrapped_method(self: Any, *args: Any, **kwargs: Any) -> Any:
        """Wrapped method with OpenTelemetry instrumentation."""
        # Ensure correlation ID exists
        correlation_id = ensure_correlation_id()
        agent_id = new_agent_id()
        step_id = new_step_id()
        
        # Create span name
        span_name = f"{cls.__name__}.{method_to_wrap}"
        
        with tracer.start_as_current_span(span_name) as span:
            # Set universal attributes
            span.set_attribute("agent.correlation_id", correlation_id)
            span.set_attribute("agent.role", role)
            span.set_attribute("agent.id", agent_id)
            span.set_attribute("step.id", step_id)
            span.set_attribute("agent.class_name", cls.__name__)
            span.set_attribute("agent.method_name", method_to_wrap)
            span.set_attribute("span.type", "agent")
            
            try:
                # Call the original method
                result = original_method(self, *args, **kwargs)
                
                # Mark span as successful
                span.set_status(Status(StatusCode.OK))
                
                return result
                
            except Exception as e:
                # Record the exception
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    # Replace the original method with the wrapped version
    setattr(cls, method_to_wrap, wrapped_method)
    
    return cls


def create_agent_span(
    name: str,
    role: str,
    correlation_id: str | None = None,
) -> trace.Span:
    """
    Create a new agent span with standard attributes.
    
    Args:
        name: The span name
        role: The agent role
        correlation_id: Optional correlation ID (will be generated if not provided)
        
    Returns:
        The created span
    """
    if correlation_id is None:
        correlation_id = ensure_correlation_id()
    
    agent_id = new_agent_id()
    step_id = new_step_id()
    
    span = tracer.start_span(name)
    span.set_attribute("agent.correlation_id", correlation_id)
    span.set_attribute("agent.role", role)
    span.set_attribute("agent.id", agent_id)
    span.set_attribute("step.id", step_id)
    span.set_attribute("span.type", "agent")
    
    return span 