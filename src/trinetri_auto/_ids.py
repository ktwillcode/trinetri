"""
Core ID generation and management for Trinetri.

Provides universal correlation IDs and agent-specific identifiers using 
contextvars for thread-safe access across async operations.
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

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variables for thread-safe ID management
_correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    """
    Generate a new correlation ID and set it in the current context.
    
    Returns:
        str: The new correlation ID (UUID4 format)
    """
    correlation_id = str(uuid.uuid4())
    _correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.
    
    Returns:
        Optional[str]: The current correlation ID, or None if not set
    """
    return _correlation_id_var.get()


def new_agent_id() -> str:
    """
    Generate a new agent ID with "agt-" prefix.
    
    Returns:
        str: Agent ID in format "agt-<12hex>"
    """
    # Generate UUID4 and take first 12 hex characters
    hex_part = uuid.uuid4().hex[:12]
    return f"agt-{hex_part}"


def new_step_id() -> str:
    """
    Generate a new step ID with "stp-" prefix.
    
    Returns:
        str: Step ID in format "stp-<12hex>"
    """
    # Generate UUID4 and take first 12 hex characters
    hex_part = uuid.uuid4().hex[:12]
    return f"stp-{hex_part}"


def ensure_correlation_id() -> str:
    """
    Ensure a correlation ID exists in the current context.
    If none exists, create a new one.
    
    Returns:
        str: The current or newly created correlation ID
    """
    correlation_id = get_correlation_id()
    if correlation_id is None:
        correlation_id = new_correlation_id()
    return correlation_id 


# Convenient aliases for common usage patterns
def correlation_id() -> str:
    """
    Get or create a correlation ID for the current context.
    
    Returns:
        str: The current correlation ID
    """
    return ensure_correlation_id()


def agent_id() -> str:
    """
    Generate a new agent ID.
    
    Returns:
        str: A new agent ID
    """
    return new_agent_id()


def step_id() -> str:
    """
    Generate a new step ID.
    
    Returns:
        str: A new step ID
    """
    return new_step_id()


# Alias for test compatibility
def get_current_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.
    
    Returns:
        Optional[str]: The current correlation ID, or None if not set
    """
    return get_correlation_id()