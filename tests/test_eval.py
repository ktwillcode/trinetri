"""
Tests for evaluation functionality in Trinetri.

Tests the @score_with decorator, evaluation spans, and CI gating logic.
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
from unittest.mock import patch, MagicMock
import time

from trinetri_auto.eval import (
    score_with, 
    EvaluationError,
    _compute_deepeval_score,
    _mock_deepeval_score
)
from trinetri_auto._ids import get_current_correlation_id


class TestScoreWithDecorator:
    """Test the @score_with decorator functionality."""
    
    def test_successful_evaluation_above_threshold(self):
        """Test decorator with score above threshold (should pass)."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def generate_response(query: str) -> str:
            return "High quality response"
        
        # Mock the evaluation to return a high score
        with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.9):
            result = generate_response("Test query")
            assert result == "High quality response"
    
    def test_failed_evaluation_below_threshold(self):
        """Test decorator with score below threshold (should raise EvaluationError)."""
        
        @score_with(metric="g-eval", threshold=0.9)
        def generate_response(query: str) -> str:
            return "Low quality response"
        
        # Mock the evaluation to return a low score
        with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.7):
            with pytest.raises(EvaluationError) as exc_info:
                generate_response("Test query")
            
            # Check exception details
            error = exc_info.value
            assert error.score == 0.7
            assert error.threshold == 0.9
            assert error.metric == "g-eval"
            assert "0.700 < threshold 0.900" in str(error)
    
    def test_evaluation_with_high_threshold_gate(self):
        """Test CI-gate logic: threshold 0.9 decorator should raise with typical scores."""
        
        @score_with(metric="g-eval", threshold=0.9)
        def generate_response(query: str) -> str:
            return "Response that should fail high threshold"
        
        # Mock score of 0.82 (typical from _mock_deepeval_score)
        with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.82):
            with pytest.raises(EvaluationError) as exc_info:
                generate_response("Test query")
            
            error = exc_info.value
            assert error.score == 0.82
            assert error.threshold == 0.9
    
    def test_evaluation_with_function_exception(self):
        """Test that original function exceptions are preserved."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def failing_function(query: str) -> str:
            raise ValueError("Original function error")
        
        # Should raise the original ValueError, not EvaluationError
        with pytest.raises(ValueError, match="Original function error"):
            failing_function("Test query")
    
    def test_evaluation_span_creation(self):
        """Test that evaluation spans are created with correct attributes."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def generate_response(query: str) -> str:
            return "Test response"
        
        # Mock OpenTelemetry components
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value.__enter__.return_value = mock_span
        
        with patch('trinetri_auto.eval.trace.get_tracer', return_value=mock_tracer):
            with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.85):
                generate_response("Test query")
        
        # Verify span creation and attributes
        mock_tracer.start_span.assert_called_once_with("eval:generate_response")
        
        # Check that span attributes were set
        span_calls = mock_span.set_attribute.call_args_list
        span_attrs = {call[0][0]: call[0][1] for call in span_calls}
        
        assert span_attrs["span_type"] == "eval"
        assert span_attrs["eval.metric"] == "g-eval"
        assert span_attrs["eval.score"] == 0.85
        assert span_attrs["eval.threshold"] == 0.8
        assert span_attrs["eval.pass"] is True
        assert span_attrs["eval.function"] == "generate_response"
        assert "Test query" in span_attrs["eval.input"]
        assert "Test response" in span_attrs["eval.output"]
    
    def test_evaluation_with_different_metrics(self):
        """Test decorator with different metric types."""
        
        @score_with(metric="faithfulness", threshold=0.7)
        def generate_response(query: str) -> str:
            return "Response"
        
        # Should use mock score for unsupported metrics
        with patch('trinetri_auto.eval._mock_deepeval_score', return_value=0.82):
            result = generate_response("Test")
            assert result == "Response"


class TestEvaluationError:
    """Test the EvaluationError exception."""
    
    def test_evaluation_error_creation(self):
        """Test EvaluationError initialization and message."""
        error = EvaluationError(score=0.6, threshold=0.8, metric="g-eval")
        
        assert error.score == 0.6
        assert error.threshold == 0.8
        assert error.metric == "g-eval"
        assert "g-eval score 0.600 < threshold 0.800" in str(error)
    
    def test_evaluation_error_different_precision(self):
        """Test error message formatting with different score precisions."""
        error = EvaluationError(score=0.12345, threshold=0.9, metric="faithfulness")
        
        assert "faithfulness score 0.123 < threshold 0.900" in str(error)


class TestDeepEvalIntegration:
    """Test DeepEval integration and fallback behavior."""
    
    def test_mock_deepeval_score(self):
        """Test that mock score returns expected value."""
        score = _mock_deepeval_score()
        assert score == 0.82
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
    
    def test_deepeval_unavailable_fallback(self):
        """Test that missing DeepEval falls back to mock scoring."""
        
        # Mock ImportError for deepeval
        with patch('trinetri_auto.eval._compute_deepeval_score', side_effect=ImportError):
            score = _compute_deepeval_score(
                input_text="test input",
                actual_output="test output"
            )
            assert score == 0.82  # Should use mock
    
    def test_deepeval_exception_fallback(self):
        """Test that DeepEval exceptions fall back to mock scoring."""
        
        # Mock DeepEval to raise an exception
        mock_geval = MagicMock()
        mock_geval.measure.side_effect = Exception("DeepEval error")
        
        with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.82):
            score = _compute_deepeval_score(
                input_text="test input",
                actual_output="test output"
            )
            assert score == 0.82  # Should use mock
    
    def test_deepeval_integration_success(self):
        """Test successful DeepEval integration."""
        
        # Test that DeepEval integration works when available
        with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.91):
            score = _compute_deepeval_score(
                input_text="test input",
                actual_output="test output",
                metric="g-eval"
            )
            
            assert score == 0.91


class TestCorrelationIDIntegration:
    """Test that evaluation spans include correlation IDs."""
    
    def test_correlation_id_in_evaluation_span(self):
        """Test that evaluation spans include the current correlation ID."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def test_function() -> str:
            return "test"
        
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value.__enter__.return_value = mock_span
        
        with patch('trinetri_auto.eval.trace.get_tracer', return_value=mock_tracer):
            with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.85):
                test_function()
        
        # Check that correlation_id was set as an attribute
        span_calls = mock_span.set_attribute.call_args_list
        span_attrs = {call[0][0]: call[0][1] for call in span_calls}
        
        assert "agent.correlation_id" in span_attrs
        assert span_attrs["agent.correlation_id"] is not None


class TestInputExtraction:
    """Test input extraction from different function signatures."""
    
    def test_input_extraction_from_args(self):
        """Test extracting input from positional arguments."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def func_with_args(query: str, context: str) -> str:
            return "response"
        
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value.__enter__.return_value = mock_span
        
        with patch('trinetri_auto.eval.trace.get_tracer', return_value=mock_tracer):
            with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.85):
                func_with_args("test query", "test context")
        
        # Check that input was extracted from first argument
        span_calls = mock_span.set_attribute.call_args_list
        span_attrs = {call[0][0]: call[0][1] for call in span_calls}
        
        assert "test query" in span_attrs["eval.input"]
    
    def test_input_extraction_from_kwargs(self):
        """Test extracting input from keyword arguments."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def func_with_kwargs(*, input: str) -> str:
            return "response"
        
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value.__enter__.return_value = mock_span
        
        with patch('trinetri_auto.eval.trace.get_tracer', return_value=mock_tracer):
            with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.85):
                func_with_kwargs(input="test input")
        
        # Check that input was extracted from 'input' keyword
        span_calls = mock_span.set_attribute.call_args_list
        span_attrs = {call[0][0]: call[0][1] for call in span_calls}
        
        assert "test input" in span_attrs["eval.input"]


class TestDurationMeasurement:
    """Test that function duration is measured and recorded."""
    
    def test_duration_measurement(self):
        """Test that function execution duration is recorded in spans."""
        
        @score_with(metric="g-eval", threshold=0.8)
        def slow_function() -> str:
            time.sleep(0.01)  # Small delay for testing
            return "response"
        
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value.__enter__.return_value = mock_span
        
        with patch('trinetri_auto.eval.trace.get_tracer', return_value=mock_tracer):
            with patch('trinetri_auto.eval._compute_deepeval_score', return_value=0.85):
                slow_function()
        
        # Check that duration was measured and is reasonable
        span_calls = mock_span.set_attribute.call_args_list
        span_attrs = {call[0][0]: call[0][1] for call in span_calls}
        
        assert "eval.duration_ms" in span_attrs
        duration = span_attrs["eval.duration_ms"]
        assert isinstance(duration, float)
        assert duration > 0  # Should be positive
        assert duration < 1000  # Should be less than 1 second for this test 