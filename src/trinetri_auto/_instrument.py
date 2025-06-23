"""
Main instrumentation module for Trinetri auto-patching.

This module is imported by __init__.py to trigger automatic instrumentation
of LLM clients, frameworks, and protocols when trinetri_auto is imported.
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

import warnings

from ._ids import ensure_correlation_id
from .agent import instrument_agent
from .eval import score_with

# Import patchers - these will only patch if libraries are available
from ._llm.openai import patch_openai
from ._llm.anthropic import patch_anthropic
from ._llm.httpx import patch_httpx

from ._framework.langgraph import instrument_langgraph
from ._framework.crewai import instrument_crewai

from ._protocol.mcp import patch_mcp
from ._protocol.a2a import patch_a2a

# Export the main API
__all__ = ["instrument_agent", "score_with", "get_patch_status"]


def get_patch_status() -> dict:
    """
    Get the current patching status for all components.
    
    Returns:
        dict: Status of all patches with bool values
    """
    status = {}
    
    # Check LLM clients
    try:
        from ._llm.openai import patch_openai
        status["OpenAI"] = patch_openai.__wrapped__ is not None if hasattr(patch_openai, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["OpenAI"] = False
    
    try:
        from ._llm.anthropic import patch_anthropic  
        status["Anthropic"] = patch_anthropic.__wrapped__ is not None if hasattr(patch_anthropic, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["Anthropic"] = False
    
    try:
        from ._llm.httpx import patch_httpx
        status["HTTPX"] = patch_httpx.__wrapped__ is not None if hasattr(patch_httpx, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["HTTPX"] = False
        
    # Check frameworks
    try:
        from ._framework.langgraph import instrument_langgraph
        status["LangGraph"] = instrument_langgraph.__wrapped__ is not None if hasattr(instrument_langgraph, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["LangGraph"] = False
        
    try:
        from ._framework.crewai import instrument_crewai
        status["CrewAI"] = instrument_crewai.__wrapped__ is not None if hasattr(instrument_crewai, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["CrewAI"] = False
    
    # Check protocols
    try:
        from ._protocol.mcp import patch_mcp
        status["MCP"] = patch_mcp.__wrapped__ is not None if hasattr(patch_mcp, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["MCP"] = False
        
    try:
        from ._protocol.a2a import patch_a2a
        status["A2A"] = patch_a2a.__wrapped__ is not None if hasattr(patch_a2a, '__wrapped__') else True
    except (ImportError, AttributeError):
        status["A2A"] = False
    
    return status


def _apply_auto_patching() -> None:
    """
    Apply automatic patching to available libraries.
    
    This function is called when trinetri_auto is imported to automatically
    instrument any detected libraries without requiring explicit setup.
    """
    # Ensure a correlation ID exists in the current context
    ensure_correlation_id()
    
    # Patch LLM clients
    patched = []
    failed = []
    
    try:
        if patch_openai():
            patched.append("OpenAI")
    except NotImplementedError:
        failed.append("OpenAI (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch OpenAI: {e}", UserWarning)
    
    try:
        if patch_anthropic():
            patched.append("Anthropic")
    except NotImplementedError:
        failed.append("Anthropic (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch Anthropic: {e}", UserWarning)
    
    try:
        if patch_httpx():
            patched.append("HTTPX")
    except NotImplementedError:
        failed.append("HTTPX (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch HTTPX: {e}", UserWarning)
    
    # Patch frameworks
    try:
        if instrument_langgraph():
            patched.append("LangGraph")
    except NotImplementedError:
        failed.append("LangGraph (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch LangGraph: {e}", UserWarning)
    
    try:
        if instrument_crewai():
            patched.append("CrewAI")
    except NotImplementedError:
        failed.append("CrewAI (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch CrewAI: {e}", UserWarning)
    
    # Patch protocols
    try:
        if patch_mcp():
            patched.append("MCP")
    except NotImplementedError:
        failed.append("MCP (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch MCP: {e}", UserWarning)
    
    try:
        if patch_a2a():
            patched.append("A2A")
    except NotImplementedError:
        failed.append("A2A (stub)")
    except Exception as e:
        warnings.warn(f"Failed to patch A2A: {e}", UserWarning)
    
    # Log results (in production, this might go to a logger)
    if patched:
        print(f"Trinetri: Successfully patched {', '.join(patched)}")
    if failed:
        print(f"Trinetri: Stub implementations for {', '.join(failed)}")


# Automatically apply patching when this module is imported
_apply_auto_patching() 