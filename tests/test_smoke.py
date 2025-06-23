"""
Smoke tests for Trinetri auto-instrumentation.

Basic tests to ensure import and basic functionality works without crashes.
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


def test_import_trinetri_auto():
    """Test that trinetri_auto can be imported without errors."""
    # This should trigger auto-patching
    import trinetri_auto  # noqa: F401
    
    # If we get here, import was successful
    assert True


def test_instrument_agent():
    """Test that instrument_agent function is available and works."""
    import trinetri_auto
    
    # Create a dummy agent class
    class DummyAgent:
        def run(self, task: str) -> str:
            return f"Completed: {task}"
    
    # Instrument the agent
    InstrumentedAgent = trinetri_auto.instrument_agent(DummyAgent, role="test")
    
    # Create an instance and run it
    agent = InstrumentedAgent()
    result = agent.run("test task")
    
    assert result == "Completed: test task"
    assert InstrumentedAgent is not None


def test_score_with_decorator():
    """Test that score_with decorator is available and works."""
    import trinetri_auto
    
    @trinetri_auto.score_with(metric="g-eval", threshold=0.8)
    def sample_function(text: str) -> str:
        return f"Processed: {text}"
    
    # Call the decorated function
    result = sample_function("test input")
    
    assert result == "Processed: test input"


@patch('trinetri_auto._framework.langgraph.patch_langgraph')
def test_mock_langgraph_workflow(mock_patch_langgraph):
    """Test creating a trivial LangGraph-like workflow (mocked if LG not installed)."""
    # Mock LangGraph if not available
    mock_patch_langgraph.return_value = False
    
    # Create a mock workflow
    class MockWorkflow:
        def __init__(self):
            self.steps = []
        
        def add_step(self, name: str, func):
            self.steps.append((name, func))
        
        def run(self, input_data):
            result = input_data
            for name, func in self.steps:
                result = func(result)
            return result
    
    # Create a simple workflow
    workflow = MockWorkflow()
    workflow.add_step("step1", lambda x: x + " -> step1")
    workflow.add_step("step2", lambda x: x + " -> step2")
    
    result = workflow.run("start")
    
    assert result == "start -> step1 -> step2"


def test_id_generation():
    """Test that ID generation functions work correctly."""
    from trinetri_auto._ids import new_agent_id, new_step_id, new_correlation_id
    
    # Test agent ID format
    agent_id = new_agent_id()
    assert agent_id.startswith("agt-")
    assert len(agent_id) == 16  # "agt-" + 12 hex chars
    
    # Test step ID format
    step_id = new_step_id()
    assert step_id.startswith("stp-")
    assert len(step_id) == 16  # "stp-" + 12 hex chars
    
    # Test correlation ID format (UUID4)
    correlation_id = new_correlation_id()
    assert len(correlation_id) == 36  # UUID4 format: 8-4-4-4-12
    assert correlation_id.count("-") == 4
    
    # Test uniqueness
    assert new_agent_id() != new_agent_id()
    assert new_step_id() != new_step_id()
    assert new_correlation_id() != new_correlation_id()


if __name__ == "__main__":
    pytest.main([__file__]) 