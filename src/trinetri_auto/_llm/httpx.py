"""
HTTPX client instrumentation for Trinetri.

Patches HTTPX requests to emit OTEL spans for HTTP calls made by LLM clients.
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
from urllib.parse import urlparse
from .._ids import get_correlation_id, new_step_id

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Known LLM API hosts that we want to instrument
LLM_HOSTS = {
    'api.openai.com',
    'api.anthropic.com',
    'api.cohere.ai',
    'api.together.xyz',
    'api.groq.com',
    'api.perplexity.ai',
    'api.mistral.ai',
    'generativelanguage.googleapis.com',  # Google
    'bedrock-runtime.us-east-1.amazonaws.com',  # AWS Bedrock
    'inference.ai21.com',  # AI21 Labs
    'api.replicate.com',
    'api.huggingface.co',
}


def patch_httpx() -> bool:
    """
    Patch HTTPX client to emit OpenTelemetry spans.
    
    Returns:
        bool: True if patching was successful, False if HTTPX not available
        
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    if not HTTPX_AVAILABLE:
        return False
    
    try:
        # Patch synchronous client request method
        original_request = httpx.Client.request
        
        def patched_request(self, method: str, url, **kwargs):
            """Patched HTTPX client request with instrumentation."""
            # Parse URL to determine if this might be an LLM API call
            parsed_url = urlparse(str(url))
            host = parsed_url.hostname
            
            # Only instrument requests to known LLM API hosts or unknown hosts
            should_instrument = (
                host in LLM_HOSTS or 
                (host and not any(known in host for known in ['localhost', '127.0.0.1', '::1']))
            )
            
            if not should_instrument:
                return original_request(self, method, url, **kwargs)
            
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            
            with trace.get_tracer("trinetri.httpx").start_as_current_span(
                f"llm.http.{method.lower()}",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "step_id": step_id,
                    "span_type": "tool",
                    "http.method": method,
                    "http.url": str(url)[:500],  # Truncate long URLs
                    "http.host": host,
                    "http.scheme": parsed_url.scheme,
                    "http.path": parsed_url.path,
                    "llm.provider": _infer_provider_from_host(host),
                }
            ) as span:
                try:
                    start_time = time.time()
                    
                    # Extract request body if present and JSON
                    request_body = kwargs.get('json') or kwargs.get('data')
                    if request_body:
                        if isinstance(request_body, dict):
                            # Extract common LLM parameters
                            span.set_attribute("llm.model", request_body.get('model', 'unknown'))
                            span.set_attribute("llm.max_tokens", request_body.get('max_tokens'))
                            span.set_attribute("llm.temperature", request_body.get('temperature'))
                            
                            # Handle different message formats
                            messages = request_body.get('messages', [])
                            if messages:
                                span.set_attribute("llm.messages_count", len(messages))
                                # Extract content for observability (truncated)
                                content_preview = str(messages)[:1000]
                                span.set_attribute("llm.request_preview", content_preview)
                            
                            # Handle prompt field (for some APIs)
                            prompt = request_body.get('prompt')
                            if prompt:
                                span.set_attribute("llm.prompt_chars", len(str(prompt)))
                                span.set_attribute("llm.prompt_preview", str(prompt)[:500])
                        
                        span.set_attribute("http.request_body_size", len(str(request_body)))
                    
                    # Extract headers for observability
                    headers = kwargs.get('headers', {})
                    if headers:
                        # Look for API key headers (but don't log the actual keys)
                        if any(key.lower() in headers for key in ['authorization', 'x-api-key', 'api-key']):
                            span.set_attribute("http.has_auth_header", True)
                        
                        content_type = headers.get('content-type') or headers.get('Content-Type')
                        if content_type:
                            span.set_attribute("http.content_type", content_type)
                    
                    # Make the actual HTTP request
                    response = original_request(self, method, url, **kwargs)
                    
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("http.latency_ms", latency_ms)
                    
                    # Extract response information
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute("http.response_size", len(response.content) if hasattr(response, 'content') else 0)
                    
                    # Try to extract LLM-specific response data
                    if response.headers.get('content-type', '').startswith('application/json'):
                        try:
                            response_data = response.json()
                            if isinstance(response_data, dict):
                                # Extract token usage if present
                                usage = response_data.get('usage', {})
                                if usage:
                                    span.set_attribute("llm.prompt_tokens", usage.get('prompt_tokens') or usage.get('input_tokens', 0))
                                    span.set_attribute("llm.completion_tokens", usage.get('completion_tokens') or usage.get('output_tokens', 0))
                                    span.set_attribute("llm.total_tokens", usage.get('total_tokens', 0))
                                
                                # Extract model from response
                                if 'model' in response_data:
                                    span.set_attribute("llm.response_model", response_data['model'])
                                
                                # Extract choices/content preview
                                choices = response_data.get('choices', [])
                                if choices and len(choices) > 0:
                                    first_choice = choices[0]
                                    if 'message' in first_choice and 'content' in first_choice['message']:
                                        content = first_choice['message']['content']
                                        span.set_attribute("llm.response_content", str(content)[:1000])
                                        span.set_attribute("llm.response_chars", len(str(content)))
                                    
                                    if 'finish_reason' in first_choice:
                                        span.set_attribute("llm.finish_reason", first_choice['finish_reason'])
                                
                                # Handle Anthropic-style responses
                                content_blocks = response_data.get('content', [])
                                if content_blocks:
                                    content_texts = []
                                    for block in content_blocks:
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            content_texts.append(block.get('text', ''))
                                    
                                    if content_texts:
                                        full_content = ' '.join(content_texts)
                                        span.set_attribute("llm.response_content", full_content[:1000])
                                        span.set_attribute("llm.response_chars", len(full_content))
                                
                                if 'stop_reason' in response_data:
                                    span.set_attribute("llm.stop_reason", response_data['stop_reason'])
                        
                        except (json.JSONDecodeError, ValueError):
                            # Couldn't parse as JSON, that's okay
                            pass
                    
                    if response.status_code >= 400:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    else:
                        span.set_status(Status(StatusCode.OK))
                    
                    return response
                    
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Patch async client request method
        original_async_request = httpx.AsyncClient.request
        
        async def patched_async_request(self, method: str, url, **kwargs):
            """Patched async HTTPX client request with instrumentation."""
            # Parse URL to determine if this might be an LLM API call
            parsed_url = urlparse(str(url))
            host = parsed_url.hostname
            
            # Only instrument requests to known LLM API hosts or unknown hosts
            should_instrument = (
                host in LLM_HOSTS or 
                (host and not any(known in host for known in ['localhost', '127.0.0.1', '::1']))
            )
            
            if not should_instrument:
                return await original_async_request(self, method, url, **kwargs)
            
            correlation_id = get_correlation_id()
            step_id = new_step_id()
            
            with trace.get_tracer("trinetri.httpx").start_as_current_span(
                f"llm.http.{method.lower()}",
                attributes={
                    "agent.correlation_id": correlation_id,
                    "step_id": step_id,
                    "span_type": "tool",
                    "http.method": method,
                    "http.url": str(url)[:500],  # Truncate long URLs
                    "http.host": host,
                    "http.scheme": parsed_url.scheme,
                    "http.path": parsed_url.path,
                    "llm.provider": _infer_provider_from_host(host),
                    "http.async": True,
                }
            ) as span:
                try:
                    start_time = time.time()
                    
                    # Extract request body if present and JSON
                    request_body = kwargs.get('json') or kwargs.get('data')
                    if request_body:
                        if isinstance(request_body, dict):
                            # Extract common LLM parameters
                            span.set_attribute("llm.model", request_body.get('model', 'unknown'))
                            span.set_attribute("llm.max_tokens", request_body.get('max_tokens'))
                            span.set_attribute("llm.temperature", request_body.get('temperature'))
                            
                            # Handle different message formats
                            messages = request_body.get('messages', [])
                            if messages:
                                span.set_attribute("llm.messages_count", len(messages))
                                # Extract content for observability (truncated)
                                content_preview = str(messages)[:1000]
                                span.set_attribute("llm.request_preview", content_preview)
                            
                            # Handle prompt field (for some APIs)
                            prompt = request_body.get('prompt')
                            if prompt:
                                span.set_attribute("llm.prompt_chars", len(str(prompt)))
                                span.set_attribute("llm.prompt_preview", str(prompt)[:500])
                        
                        span.set_attribute("http.request_body_size", len(str(request_body)))
                    
                    # Extract headers for observability
                    headers = kwargs.get('headers', {})
                    if headers:
                        # Look for API key headers (but don't log the actual keys)
                        if any(key.lower() in headers for key in ['authorization', 'x-api-key', 'api-key']):
                            span.set_attribute("http.has_auth_header", True)
                        
                        content_type = headers.get('content-type') or headers.get('Content-Type')
                        if content_type:
                            span.set_attribute("http.content_type", content_type)
                    
                    # Make the actual HTTP request
                    response = await original_async_request(self, method, url, **kwargs)
                    
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
                    span.set_attribute("http.latency_ms", latency_ms)
                    
                    # Extract response information
                    span.set_attribute("http.status_code", response.status_code)
                    span.set_attribute("http.response_size", len(response.content) if hasattr(response, 'content') else 0)
                    
                    # Try to extract LLM-specific response data
                    if response.headers.get('content-type', '').startswith('application/json'):
                        try:
                            response_data = response.json()
                            if isinstance(response_data, dict):
                                # Extract token usage if present
                                usage = response_data.get('usage', {})
                                if usage:
                                    span.set_attribute("llm.prompt_tokens", usage.get('prompt_tokens') or usage.get('input_tokens', 0))
                                    span.set_attribute("llm.completion_tokens", usage.get('completion_tokens') or usage.get('output_tokens', 0))
                                    span.set_attribute("llm.total_tokens", usage.get('total_tokens', 0))
                                
                                # Extract model from response
                                if 'model' in response_data:
                                    span.set_attribute("llm.response_model", response_data['model'])
                                
                                # Extract choices/content preview
                                choices = response_data.get('choices', [])
                                if choices and len(choices) > 0:
                                    first_choice = choices[0]
                                    if 'message' in first_choice and 'content' in first_choice['message']:
                                        content = first_choice['message']['content']
                                        span.set_attribute("llm.response_content", str(content)[:1000])
                                        span.set_attribute("llm.response_chars", len(str(content)))
                                    
                                    if 'finish_reason' in first_choice:
                                        span.set_attribute("llm.finish_reason", first_choice['finish_reason'])
                                
                                # Handle Anthropic-style responses
                                content_blocks = response_data.get('content', [])
                                if content_blocks:
                                    content_texts = []
                                    for block in content_blocks:
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            content_texts.append(block.get('text', ''))
                                    
                                    if content_texts:
                                        full_content = ' '.join(content_texts)
                                        span.set_attribute("llm.response_content", full_content[:1000])
                                        span.set_attribute("llm.response_chars", len(full_content))
                                
                                if 'stop_reason' in response_data:
                                    span.set_attribute("llm.stop_reason", response_data['stop_reason'])
                        
                        except (json.JSONDecodeError, ValueError):
                            # Couldn't parse as JSON, that's okay
                            pass
                    
                    if response.status_code >= 400:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                    else:
                        span.set_status(Status(StatusCode.OK))
                    
                    return response
                    
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        # Apply patches
        httpx.Client.request = patched_request
        httpx.AsyncClient.request = patched_async_request
        
        return True
        
    except Exception:
        return False


def _infer_provider_from_host(host: str) -> str:
    """Infer LLM provider from hostname."""
    if not host:
        return 'unknown'
    
    host = host.lower()
    
    if 'openai.com' in host:
        return 'openai'
    elif 'anthropic.com' in host:
        return 'anthropic'
    elif 'cohere.ai' in host:
        return 'cohere'
    elif 'together.xyz' in host:
        return 'together'
    elif 'groq.com' in host:
        return 'groq'
    elif 'perplexity.ai' in host:
        return 'perplexity'
    elif 'mistral.ai' in host:
        return 'mistral'
    elif 'googleapis.com' in host:
        return 'google'
    elif 'amazonaws.com' in host:
        return 'aws'
    elif 'ai21.com' in host:
        return 'ai21'
    elif 'replicate.com' in host:
        return 'replicate'
    elif 'huggingface.co' in host:
        return 'huggingface'
    else:
        return 'unknown'


def _get_httpx_version() -> str:
    """Get HTTPX version safely."""
    try:
        import httpx
        return getattr(httpx, '__version__', 'unknown')
    except:
        return 'unknown'


def instrument_httpx_client(client: Any) -> Any:
    """Instrument a specific HTTPX client instance."""
    if not HTTPX_AVAILABLE:
        return client
    
    # This would be used for per-client instrumentation if needed
    # For now, we use global patching
    return client


def unpatch_httpx() -> None:
    """
    Remove HTTPX patches.
    
    Raises:
        NotImplementedError: This is a Phase 1 stub
    """
    raise NotImplementedError("HTTPX unpatching not yet implemented in Phase 1") 