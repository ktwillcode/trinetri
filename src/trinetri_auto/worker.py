"""
Async worker for large-scale evaluation offload.

Provides queue consumption capabilities for processing evaluation tasks
at scale in distributed environments.
"""

# Copyright 2024 Trinetri
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

import asyncio
from typing import Any, Dict, Optional


class EvaluationTask:
    """Represents an evaluation task for processing in the queue."""
    
    def __init__(
        self,
        task_id: str,
        function_name: str,
        input_data: str,
        output_data: str,
        metric: str = "g-eval",
        threshold: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.function_name = function_name
        self.input_data = input_data
        self.output_data = output_data
        self.metric = metric
        self.threshold = threshold
        self.metadata = metadata or {}


class EvaluationQueue:
    """
    Async queue for processing evaluation tasks at scale.
    
    This is a placeholder implementation for Phase 3.
    In production, this would integrate with a message queue
    like Redis, RabbitMQ, or cloud-native solutions.
    """
    
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
    
    async def put(self, task: EvaluationTask) -> None:
        """Add an evaluation task to the queue."""
        await self._queue.put(task)
    
    async def get(self) -> EvaluationTask:
        """Get the next evaluation task from the queue."""
        return await self._queue.get()
    
    async def consume(self, worker_id: str = "worker-1") -> None:
        """
        Consume evaluation tasks from the queue.
        
        This is a placeholder for large-scale evaluation offload.
        In a full implementation, this would:
        1. Pull tasks from a distributed queue
        2. Execute evaluations using DeepEval
        3. Store results in a database
        4. Handle retries and error cases
        5. Emit metrics and monitoring data
        
        Args:
            worker_id: Identifier for this worker instance
        """
        self._running = True
        print(f"[{worker_id}] Starting evaluation queue consumer...")
        
        try:
            while self._running:
                try:
                    # Wait for a task with timeout
                    task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                    
                    print(f"[{worker_id}] Processing task {task.task_id}: {task.function_name}")
                    
                    # Placeholder processing
                    await self._process_task(task, worker_id)
                    
                    # Mark task as done
                    self._queue.task_done()
                    
                except asyncio.TimeoutError:
                    # No tasks available, continue polling
                    continue
                except Exception as e:
                    print(f"[{worker_id}] Error processing task: {e}")
                    continue
                    
        except KeyboardInterrupt:
            print(f"[{worker_id}] Received interrupt, shutting down...")
        finally:
            self._running = False
            print(f"[{worker_id}] Worker stopped")
    
    async def _process_task(self, task: EvaluationTask, worker_id: str) -> None:
        """
        Process a single evaluation task.
        
        Args:
            task: The evaluation task to process
            worker_id: Identifier for this worker
        """
        # Simulate evaluation processing time
        await asyncio.sleep(0.1)
        
        # In a real implementation, this would:
        # 1. Run the evaluation using DeepEval
        # 2. Store results in a database
        # 3. Emit telemetry data
        
        print(f"[{worker_id}] Completed evaluation for {task.function_name} "
              f"with {task.metric} metric (threshold: {task.threshold})")
    
    def stop(self) -> None:
        """Stop the queue consumer."""
        self._running = False


# Global queue instance for the application
_evaluation_queue: Optional[EvaluationQueue] = None


def get_evaluation_queue() -> EvaluationQueue:
    """Get the global evaluation queue instance."""
    global _evaluation_queue
    if _evaluation_queue is None:
        _evaluation_queue = EvaluationQueue()
    return _evaluation_queue


async def start_worker(worker_id: str = "worker-1") -> None:
    """
    Start an evaluation worker.
    
    Args:
        worker_id: Identifier for this worker instance
    """
    queue = get_evaluation_queue()
    await queue.consume(worker_id)


# Example usage for testing
if __name__ == "__main__":
    async def main():
        # Create some test tasks
        queue = get_evaluation_queue()
        
        tasks = [
            EvaluationTask(
                task_id=f"task-{i}",
                function_name="generate_response",
                input_data=f"Test input {i}",
                output_data=f"Test output {i}",
                metric="g-eval",
                threshold=0.8
            )
            for i in range(3)
        ]
        
        # Add tasks to queue
        for task in tasks:
            await queue.put(task)
        
        # Start worker (will process all tasks and then wait)
        await start_worker("test-worker")
    
    # Run the example
    asyncio.run(main()) 