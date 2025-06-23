"""
ID integrity tests for Trinetri.

Tests to ensure correlation IDs and step IDs are properly maintained across spans.
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

import pytest
from unittest.mock import Mock, patch


def test_correlation_id_consistency():
    """Test that correlation ID remains consistent across multiple operations."""
    from trinetri_auto._ids import new_correlation_id, get_correlation_id, ensure_correlation_id
    
    # Create a new correlation ID
    correlation_id = new_correlation_id()
    
    # Verify it's set in context
    assert get_correlation_id() == correlation_id
    
    # Ensure correlation ID should return the same ID
    same_id = ensure_correlation_id()
    assert same_id == correlation_id
    
    # Get it again to verify persistence
    retrieved_id = get_correlation_id()
    assert retrieved_id == correlation_id


def test_multiple_spans_same_correlation():
    """Test creating multiple spans with the same correlation ID."""
    from trinetri_auto._ids import new_correlation_id, get_correlation_id
    from trinetri_auto.agent import create_agent_span
    
    # Set a correlation ID
    correlation_id = new_correlation_id()
    
    # Create two spans
    span1 = create_agent_span("span1", "role1", correlation_id)
    span2 = create_agent_span("span2", "role2", correlation_id)
    
    # Both spans should have the same correlation ID
    assert span1.attributes["agent.correlation_id"] == correlation_id
    assert span2.attributes["agent.correlation_id"] == correlation_id
    
    # But different agent IDs and step IDs
    assert span1.get_attribute("agent.id") != span2.get_attribute("agent.id")
    assert span1.get_attribute("step.id") != span2.get_attribute("step.id")
    
    # Both should have the correct roles
    assert span1.get_attribute("agent.role") == "role1"
    assert span2.get_attribute("agent.role") == "role2"


@patch('trinetri_auto.agent.tracer')
def test_agent_instrumentation_correlation(mock_tracer):
    """Test that agent instrumentation maintains correlation ID."""
    from trinetri_auto._ids import new_correlation_id
    from trinetri_auto.agent import instrument_agent
    
    # Set up mock span
    mock_span = Mock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
    
    # Create a correlation ID
    correlation_id = new_correlation_id()
    
    # Create and instrument an agent
    class TestAgent:
        def run(self, task: str) -> str:
            return f"Completed: {task}"
    
    InstrumentedAgent = instrument_agent(TestAgent, role="test_role")
    agent = InstrumentedAgent()
    
    # Run the agent
    result = agent.run("test task")
    
    # Verify the span was created with correct attributes
    mock_tracer.start_as_current_span.assert_called_once()
    span_calls = mock_span.set_attribute.call_args_list
    
    # Find the correlation_id attribute call
    correlation_calls = [call for call in span_calls 
                        if call[0][0] == "agent.correlation_id"]
    assert len(correlation_calls) == 1
    assert correlation_calls[0][0][1] == correlation_id
    
    # Verify role is set correctly
    role_calls = [call for call in span_calls if call[0][0] == "agent.role"]
    assert len(role_calls) == 1
    assert role_calls[0][0][1] == "test_role"
    
    assert result == "Completed: test task"


def test_context_isolation():
    """Test that correlation IDs are isolated between different contexts."""
    from trinetri_auto._ids import new_correlation_id, get_correlation_id
    import asyncio
    
    async def task_with_correlation():
        # Each task should get its own correlation ID
        task_correlation_id = new_correlation_id()
        return get_correlation_id()
    
    async def test_isolation():
        # Create multiple tasks
        tasks = [task_with_correlation() for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        # All results should be different (different correlation IDs)
        assert len(set(results)) == 3
        
        # Each should be a valid UUID
        for correlation_id in results:
            assert len(correlation_id) == 36
            assert correlation_id.count("-") == 4
    
    # Run the async test
    asyncio.run(test_isolation())


def test_ensure_correlation_id_creates_if_missing():
    """Test that ensure_correlation_id creates a new ID if none exists."""
    from trinetri_auto._ids import ensure_correlation_id, get_correlation_id, _correlation_id_var
    
    # Clear any existing correlation ID
    _correlation_id_var.set(None)
    
    # Verify no correlation ID exists
    assert get_correlation_id() is None
    
    # Ensure correlation ID should create a new one
    correlation_id = ensure_correlation_id()
    
    # Verify it was created and set
    assert correlation_id is not None
    assert len(correlation_id) == 36
    assert get_correlation_id() == correlation_id


def test_step_and_agent_id_uniqueness():
    """Test that step IDs and agent IDs are unique across calls."""
    from trinetri_auto._ids import new_agent_id, new_step_id
    
    # Generate multiple IDs
    agent_ids = [new_agent_id() for _ in range(10)]
    step_ids = [new_step_id() for _ in range(10)]
    
    # All agent IDs should be unique
    assert len(set(agent_ids)) == 10
    
    # All step IDs should be unique
    assert len(set(step_ids)) == 10
    
    # All should have correct format
    for agent_id in agent_ids:
        assert agent_id.startswith("agt-")
        assert len(agent_id) == 16
    
    for step_id in step_ids:
        assert step_id.startswith("stp-")
        assert len(step_id) == 16


if __name__ == "__main__":
    pytest.main([__file__]) 