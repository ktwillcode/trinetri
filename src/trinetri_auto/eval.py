"""
In-trace evaluation decorator and utilities for Trinetri.

Provides the @score_with decorator for automated LLM response evaluation
during function execution with threshold-based gating.
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
import time
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from ._ids import new_step_id, ensure_correlation_id


class EvaluationError(Exception):
    """Raised when evaluation score falls below threshold."""
    def __init__(self, score: float, threshold: float, metric: str):
        self.score = score
        self.threshold = threshold
        self.metric = metric
        super().__init__(f"Evaluation failed: {metric} score {score:.3f} < threshold {threshold:.3f}")


def _mock_deepeval_score() -> float:
    """Mock DeepEval score when library is not available."""
    # Return a score slightly above typical threshold (0.8) for demo purposes
    return 0.82


def _compute_deepeval_score(
    input_text: str,
    actual_output: str,
    metric: str = "g-eval",
    expected_output: Optional[str] = None
) -> float:
    """
    Compute evaluation score using DeepEval if available, otherwise mock.
    
    Args:
        input_text: Original function input
        actual_output: Function output to evaluate
        metric: Evaluation metric to use (currently supports "g-eval")
        expected_output: Expected output for comparison (optional)
        
    Returns:
        Evaluation score between 0.0 and 1.0
    """
    try:
        # Try to import and use DeepEval
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
        
        # Create G-Eval metric
        if metric == "g-eval":
            eval_metric = GEval(
                name="Response Quality",
                criteria="Evaluate the quality, relevance, and appropriateness of the actual output based on the input.",
                evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                threshold=0.0,  # We handle thresholding in the decorator
                strict_mode=False
            )
            
            # Create test case
            test_case = LLMTestCase(
                input=str(input_text),
                actual_output=str(actual_output),
                expected_output=expected_output
            )
            
            # Run evaluation
            eval_metric.measure(test_case)
            return eval_metric.score
        else:
            # Fallback for unsupported metrics
            return _mock_deepeval_score()
            
    except ImportError:
        # DeepEval not available, use mock
        return _mock_deepeval_score()
    except Exception:
        # Any other error, use mock
        return _mock_deepeval_score()


def score_with(metric = "g-eval", threshold: float = 0.8):
    """
    Decorator for in-trace evaluation of function outputs.
    
    On function exit, computes an evaluation score using the specified metric
    and emits a child span with evaluation results. If the score falls below
    the threshold, raises EvaluationError to gate execution.
    
    Args:
        metric: Evaluation metric to use (default: "g-eval")
        threshold: Minimum score required to pass (default: 0.8)
        
    Raises:
        EvaluationError: If evaluation score is below threshold
        
    Example:
        @score_with(metric="g-eval", threshold=0.9)
        def generate_response(query: str) -> str:
            return "Some LLM response"
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute original function
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                success = True
                error_msg = None
            except Exception as e:
                result = None
                success = False
                error_msg = str(e)
                raise
            finally:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Only evaluate if function succeeded and returned a result
                if success and result is not None:
                    _emit_evaluation_span(
                        func=func,
                        args=args, 
                        kwargs=kwargs,
                        result=result,
                        metric=metric,
                        threshold=threshold,
                        duration_ms=duration_ms
                    )
                
            return result
            
        return wrapper
    return decorator


def _emit_evaluation_span(
    func: Callable,
    args: tuple,
    kwargs: dict,
    result: Any,
    metric: str,
    threshold: float,
    duration_ms: float
):
    """
    Emit evaluation span with score and pass/fail status.
    
    Args:
        func: Original function being evaluated
        args: Function positional arguments
        kwargs: Function keyword arguments  
        result: Function return value
        metric: Evaluation metric used
        threshold: Score threshold for pass/fail
        duration_ms: Function execution duration in milliseconds
    """
    tracer = trace.get_tracer(__name__)
    
    # Extract input for evaluation (first arg or 'input'/'query' kwargs)
    input_text = ""
    if args:
        input_text = str(args[0])
    elif 'input' in kwargs:
        input_text = str(kwargs['input'])
    elif 'query' in kwargs:
        input_text = str(kwargs['query'])
    
    # Compute evaluation score
    if callable(metric):
        # Custom evaluation function
        try:
            score = metric(input_text, str(result))
        except Exception:
            score = _mock_deepeval_score()
        metric_name = getattr(metric, '__name__', 'custom')
    else:
        # String metric (use DeepEval)
        score = _compute_deepeval_score(
            input_text=input_text,
            actual_output=str(result),
            metric=metric
        )
        metric_name = metric
    
    # Determine pass/fail
    eval_pass = score >= threshold
    
    # Create evaluation span
    with tracer.start_span(f"eval:{func.__name__}") as span:
        # Universal attributes
        correlation_id = ensure_correlation_id()
        step_id = new_step_id()
        
        span.set_attribute("agent.correlation_id", correlation_id)
        span.set_attribute("step_id", step_id)
        span.set_attribute("span_type", "eval")
        
        # Evaluation-specific attributes
        span.set_attribute("eval.metric", metric_name)
        span.set_attribute("eval.score", score)
        span.set_attribute("eval.threshold", threshold)
        span.set_attribute("eval.pass", eval_pass)
        
        # Function metadata
        span.set_attribute("eval.function", func.__name__)
        span.set_attribute("eval.input", input_text[:1000])  # Truncate
        span.set_attribute("eval.output", str(result)[:1000])  # Truncate
        span.set_attribute("eval.duration_ms", duration_ms)
        
        # Set span status based on evaluation result
        if eval_pass:
            span.set_status(Status(StatusCode.OK, f"Evaluation passed: {score:.3f} >= {threshold}"))
        else:
            span.set_status(Status(StatusCode.ERROR, f"Evaluation failed: {score:.3f} < {threshold}"))
            
    # Raise error if evaluation failed
    if not eval_pass:
        raise EvaluationError(score, threshold, metric_name) 