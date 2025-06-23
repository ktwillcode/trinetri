"""
Anthropic client instrumentation for Trinetri.

Patches Anthropic client methods to emit OTEL spans with token usage and MCP context.
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
from typing import Any, Dict, Optional, Union, List
import json
import time
from .._ids import get_correlation_id, new_step_id

try:
    import anthropic
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.resources import messages
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def patch_anthropic() -> bool:
    """Patch Anthropic client to emit spans with token usage and latency."""
    if not ANTHROPIC_AVAILABLE:
        return False
    
    try:
        # Patch synchronous messages create
        original_create = messages.Messages.create
        
        def patched_create(self, **kwargs):
            """Patched Anthropic messages create with instrumentation."""
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            
            with trace.get_tracer("trinetri.anthropic").start_as_current_span(
                "llm.anthropic.messages.create",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "step_id": step_id,
                    "span_type": "tool",
                    "llm.provider": "anthropic",
                    "llm.model": kwargs.get('model', 'unknown'),
                    "llm.max_tokens": kwargs.get('max_tokens'),
                    "llm.temperature": kwargs.get('temperature'),
                    "llm.top_p": kwargs.get('top_p'),
                    "llm.top_k": kwargs.get('top_k'),
                    "llm.messages_count": len(kwargs.get('messages', [])),
                    "llm.stream": kwargs.get('stream', False),
                    "llm.system": kwargs.get('system', '')[:200] if kwargs.get('system') else None,
                }
            ) as span:
                try:
                    start_time = time.time()
                    
                    # Extract prompt info for observability
                    messages_list = kwargs.get('messages', [])
                    if messages_list:
                        total_content_chars = 0
                        for msg in messages_list:
                            if isinstance(msg, dict):
                                content = msg.get('content', '')
                                if isinstance(content, list):
                                    # Handle multi-modal content
                                    total_content_chars += sum(
                                        len(str(item.get('text', ''))) 
                                        for item in content 
                                        if isinstance(item, dict) and item.get('type') == 'text'
                                    )
                                else:
                                    total_content_chars += len(str(content))
                        
                        span.set_attribute("llm.prompt_chars", total_content_chars)
                        span.set_attribute("llm.prompt_messages", json.dumps(messages_list, default=str)[:2000])
                    
                    # Add system message length if present
                    system_msg = kwargs.get('system', '')
                    if system_msg:
                        span.set_attribute("llm.system_chars", len(str(system_msg)))
                    
                    # Make the actual API call
                    response = original_create(self, **kwargs)
                    
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", latency_ms)
                    
                    # Extract usage information if available
                    if hasattr(response, 'usage') and response.usage:
                        usage = response.usage
                        span.set_attribute("llm.input_tokens", getattr(usage, 'input_tokens', 0))
                        span.set_attribute("llm.output_tokens", getattr(usage, 'output_tokens', 0))
                        
                        # Anthropic uses input/output instead of prompt/completion
                        span.set_attribute("llm.prompt_tokens", getattr(usage, 'input_tokens', 0))
                        span.set_attribute("llm.completion_tokens", getattr(usage, 'output_tokens', 0))
                        span.set_attribute("llm.total_tokens", 
                                         getattr(usage, 'input_tokens', 0) + getattr(usage, 'output_tokens', 0))
                    
                    # Extract response content
                    if hasattr(response, 'content') and response.content:
                        # Anthropic returns content as a list
                        content_texts = []
                        for content_block in response.content:
                            if hasattr(content_block, 'text'):
                                content_texts.append(content_block.text)
                        
                        full_content = ' '.join(content_texts)
                        span.set_attribute("llm.response_content", full_content[:1000])
                        span.set_attribute("llm.response_chars", len(full_content))
                    
                    # Extract other response metadata
                    if hasattr(response, 'model'):
                        span.set_attribute("llm.response_model", response.model)
                    
                    if hasattr(response, 'stop_reason'):
                        span.set_attribute("llm.stop_reason", response.stop_reason)
                    
                    if hasattr(response, 'stop_sequence'):
                        span.set_attribute("llm.stop_sequence", response.stop_sequence)
                    
                    span.set_status(Status(StatusCode.OK))
                    return response
                    
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Patch async messages create
        if hasattr(messages, 'AsyncMessages'):
            original_async_create = messages.AsyncMessages.create
            
            async def patched_async_create(self, **kwargs):
                """Patched async Anthropic messages create with instrumentation."""
                correlation_id = get_correlation_id()
                step_id = new_step_id()
                
                with trace.get_tracer("trinetri.anthropic").start_as_current_span(
                    "llm.anthropic.messages.acreate",
                    attributes={
                        "agent.correlation_id": correlation_id,
                        "step_id": step_id,
                        "span_type": "tool",
                        "llm.provider": "anthropic",
                        "llm.model": kwargs.get('model', 'unknown'),
                        "llm.max_tokens": kwargs.get('max_tokens'),
                        "llm.temperature": kwargs.get('temperature'),
                        "llm.top_p": kwargs.get('top_p'),
                        "llm.top_k": kwargs.get('top_k'),
                        "llm.messages_count": len(kwargs.get('messages', [])),
                        "llm.stream": kwargs.get('stream', False),
                        "llm.system": kwargs.get('system', '')[:200] if kwargs.get('system') else None,
                        "llm.async": True,
                    }
                ) as span:
                    try:
                        start_time = time.time()
                        
                        # Extract prompt info for observability
                        messages_list = kwargs.get('messages', [])
                        if messages_list:
                            total_content_chars = 0
                            for msg in messages_list:
                                if isinstance(msg, dict):
                                    content = msg.get('content', '')
                                    if isinstance(content, list):
                                        # Handle multi-modal content
                                        total_content_chars += sum(
                                            len(str(item.get('text', ''))) 
                                            for item in content 
                                            if isinstance(item, dict) and item.get('type') == 'text'
                                        )
                                    else:
                                        total_content_chars += len(str(content))
                        
                            span.set_attribute("llm.prompt_chars", total_content_chars)
                            span.set_attribute("llm.prompt_messages", json.dumps(messages_list, default=str)[:2000])
                        
                        # Add system message length if present
                        system_msg = kwargs.get('system', '')
                        if system_msg:
                            span.set_attribute("llm.system_chars", len(str(system_msg)))
                        
                        # Make the actual API call
                        response = await original_async_create(self, **kwargs)
                        
                        # Calculate latency
                        latency_ms = (time.time() - start_time) * 1000
                        span.set_attribute("llm.latency_ms", latency_ms)
                        
                        # Extract usage information if available
                        if hasattr(response, 'usage') and response.usage:
                            usage = response.usage
                            span.set_attribute("llm.input_tokens", getattr(usage, 'input_tokens', 0))
                            span.set_attribute("llm.output_tokens", getattr(usage, 'output_tokens', 0))
                            
                            # Anthropic uses input/output instead of prompt/completion
                            span.set_attribute("llm.prompt_tokens", getattr(usage, 'input_tokens', 0))
                            span.set_attribute("llm.completion_tokens", getattr(usage, 'output_tokens', 0))
                            span.set_attribute("llm.total_tokens", 
                                             getattr(usage, 'input_tokens', 0) + getattr(usage, 'output_tokens', 0))
                        
                        # Extract response content
                        if hasattr(response, 'content') and response.content:
                            # Anthropic returns content as a list
                            content_texts = []
                            for content_block in response.content:
                                if hasattr(content_block, 'text'):
                                    content_texts.append(content_block.text)
                        
                            full_content = ' '.join(content_texts)
                            span.set_attribute("llm.response_content", full_content[:1000])
                            span.set_attribute("llm.response_chars", len(full_content))
                        
                        # Extract other response metadata
                        if hasattr(response, 'model'):
                            span.set_attribute("llm.response_model", response.model)
                        
                        if hasattr(response, 'stop_reason'):
                            span.set_attribute("llm.stop_reason", response.stop_reason)
                        
                        if hasattr(response, 'stop_sequence'):
                            span.set_attribute("llm.stop_sequence", response.stop_sequence)
                        
                        span.set_status(Status(StatusCode.OK))
                        return response
                        
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            messages.AsyncMessages.create = patched_async_create
        
        # Apply the sync patch
        messages.Messages.create = patched_create
        
        return True
        
    except Exception:
        return False


def _get_anthropic_version() -> str:
    """Get Anthropic version safely."""
    try:
        import anthropic
        return getattr(anthropic, '__version__', 'unknown')
    except:
        return 'unknown'


def instrument_anthropic_client(client: Any) -> Any:
    """Instrument a specific Anthropic client instance."""
    if not ANTHROPIC_AVAILABLE:
        return client
    
    # This would be used for per-client instrumentation if needed
    # For now, we use global patching
    return client


def unpatch_anthropic() -> None:
    """
    Remove Anthropic patches.
    
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    raise NotImplementedError("Anthropic unpatching not yet implemented in Phase 1") 