"""
OpenAI client instrumentation for Trinetri.

Patches OpenAI client methods to emit OTEL spans with token usage and model info.
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
from .._ids import get_correlation_id, new_step_id

try:
    import openai
    from openai import OpenAI, AsyncOpenAI
    from openai.resources.chat import completions
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def patch_openai() -> bool:
    """Patch OpenAI client to emit spans with token usage and latency."""
    if not OPENAI_AVAILABLE:
        return False
    
    try:
        # Patch synchronous chat completions
        original_create = completions.Completions.create
        
        def patched_create(self, **kwargs):
            """Patched OpenAI chat completions create with instrumentation."""
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            
            with trace.get_tracer("trinetri.openai").start_as_current_span(
                "llm.openai.chat.completions.create",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "step_id": step_id,
                    "span_type": "tool",
                    "llm.provider": "openai",
                    "llm.model": kwargs.get('model', 'unknown'),
                    "llm.temperature": kwargs.get('temperature'),
                    "llm.max_tokens": kwargs.get('max_tokens'),
                    "llm.top_p": kwargs.get('top_p'),
                    "llm.frequency_penalty": kwargs.get('frequency_penalty'),
                    "llm.presence_penalty": kwargs.get('presence_penalty'),
                    "llm.messages_count": len(kwargs.get('messages', [])),
                    "llm.stream": kwargs.get('stream', False),
                }
            ) as span:
                try:
                    start_time = time.time()
                    
                    # Extract prompt info for observability
                    messages = kwargs.get('messages', [])
                    if messages:
                        # Count tokens roughly (actual counting would require tiktoken)
                        total_content_chars = sum(
                            len(str(msg.get('content', ''))) 
                            for msg in messages 
                            if isinstance(msg, dict)
                        )
                        span.set_attribute("llm.prompt_chars", total_content_chars)
                        span.set_attribute("llm.prompt_messages", json.dumps(messages, default=str)[:2000])
                    
                    # Make the actual API call
                    response = original_create(self, **kwargs)
                    
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("llm.latency_ms", latency_ms)
                    
                    # Extract usage information if available
                    if hasattr(response, 'usage') and response.usage:
                        usage = response.usage
                        span.set_attribute("llm.prompt_tokens", getattr(usage, 'prompt_tokens', 0))
                        span.set_attribute("llm.completion_tokens", getattr(usage, 'completion_tokens', 0))
                        span.set_attribute("llm.total_tokens", getattr(usage, 'total_tokens', 0))
                    
                    # Extract response content
                    if hasattr(response, 'choices') and response.choices:
                        first_choice = response.choices[0]
                        if hasattr(first_choice, 'message') and hasattr(first_choice.message, 'content'):
                            content = first_choice.message.content
                            span.set_attribute("llm.response_content", str(content)[:1000])
                            span.set_attribute("llm.response_chars", len(str(content)))
                        
                        span.set_attribute("llm.finish_reason", getattr(first_choice, 'finish_reason', 'unknown'))
                    
                    # Set model from response if available
                    if hasattr(response, 'model'):
                        span.set_attribute("llm.response_model", response.model)
                    
                    span.set_status(Status(StatusCode.OK))
                    return response
                    
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Patch async chat completions
        if hasattr(completions, 'AsyncCompletions'):
            original_async_create = completions.AsyncCompletions.create
            
            async def patched_async_create(self, **kwargs):
                """Patched async OpenAI chat completions create with instrumentation."""
                correlation_id = get_correlation_id()
                step_id = new_step_id()
                
                with trace.get_tracer("trinetri.openai").start_as_current_span(
                    "llm.openai.chat.completions.acreate",
                    attributes={
                        "agent.correlation_id": correlation_id,
                        "step_id": step_id,
                        "span_type": "tool",
                        "llm.provider": "openai",
                        "llm.model": kwargs.get('model', 'unknown'),
                        "llm.temperature": kwargs.get('temperature'),
                        "llm.max_tokens": kwargs.get('max_tokens'),
                        "llm.top_p": kwargs.get('top_p'),
                        "llm.frequency_penalty": kwargs.get('frequency_penalty'),
                        "llm.presence_penalty": kwargs.get('presence_penalty'),
                        "llm.messages_count": len(kwargs.get('messages', [])),
                        "llm.stream": kwargs.get('stream', False),
                        "llm.async": True,
                    }
                ) as span:
                    try:
                        start_time = time.time()
                        
                        # Extract prompt info for observability
                        messages = kwargs.get('messages', [])
                        if messages:
                            total_content_chars = sum(
                                len(str(msg.get('content', ''))) 
                                for msg in messages 
                                if isinstance(msg, dict)
                            )
                            span.set_attribute("llm.prompt_chars", total_content_chars)
                            span.set_attribute("llm.prompt_messages", json.dumps(messages, default=str)[:2000])
                        
                        # Make the actual API call
                        response = await original_async_create(self, **kwargs)
                        
                        # Calculate latency
                        latency_ms = (time.time() - start_time) * 1000
                        span.set_attribute("llm.latency_ms", latency_ms)
                        
                        # Extract usage information if available
                        if hasattr(response, 'usage') and response.usage:
                            usage = response.usage
                            span.set_attribute("llm.prompt_tokens", getattr(usage, 'prompt_tokens', 0))
                            span.set_attribute("llm.completion_tokens", getattr(usage, 'completion_tokens', 0))
                            span.set_attribute("llm.total_tokens", getattr(usage, 'total_tokens', 0))
                        
                        # Extract response content
                        if hasattr(response, 'choices') and response.choices:
                            first_choice = response.choices[0]
                            if hasattr(first_choice, 'message') and hasattr(first_choice.message, 'content'):
                                content = first_choice.message.content
                                span.set_attribute("llm.response_content", str(content)[:1000])
                                span.set_attribute("llm.response_chars", len(str(content)))
                            
                            span.set_attribute("llm.finish_reason", getattr(first_choice, 'finish_reason', 'unknown'))
                        
                        # Set model from response if available
                        if hasattr(response, 'model'):
                            span.set_attribute("llm.response_model", response.model)
                        
                        span.set_status(Status(StatusCode.OK))
                        return response
                        
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            completions.AsyncCompletions.create = patched_async_create
        
        # Apply the sync patch
        completions.Completions.create = patched_create
        
        return True
        
    except Exception:
        return False


def _get_openai_version() -> str:
    """Get OpenAI version safely."""
    try:
        import openai
        return getattr(openai, '__version__', 'unknown')
    except:
        return 'unknown'


def instrument_openai_client(client: Any) -> Any:
    """Instrument a specific OpenAI client instance."""
    if not OPENAI_AVAILABLE:
        return client
    
    # This would be used for per-client instrumentation if needed
    # For now, we use global patching
    return client


def unpatch_openai() -> None:
    """
    Remove OpenAI patches.
    
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    raise NotImplementedError("OpenAI unpatching not yet implemented in Phase 1") 