"""
Workflow Pipeline System for msk_modelling_python
Inspired by n8n workflow automation

This module provides a pipeline/workflow system to chain together
musculoskeletal modeling tasks in a structured, reproducible way.

Author: Basilio Goncalves
"""

import os
import json
import time
from typing import Any, Dict, List, Callable, Optional
from datetime import datetime
import traceback


class WorkflowNode:
    """
    A single node in a workflow pipeline.
    Represents one task/operation that can be executed.
    """
    
    def __init__(self, name: str, function: Callable, inputs: Optional[Dict] = None, 
                 description: str = ""):
        """
        Initialize a workflow node.
        
        Args:
            name: Unique identifier for this node
            function: The function to execute
            inputs: Input parameters for the function
            description: Human-readable description of what this node does
        """
        self.name = name
        self.function = function
        self.inputs = inputs or {}
        self.description = description
        self.outputs = {}
        self.status = "pending"  # pending, running, completed, failed
        self.error = None
        self.start_time = None
        self.end_time = None
        self.next_nodes = []
        
    def connect_to(self, node: 'WorkflowNode'):
        """Connect this node to another node (creates a directed edge)."""
        if node not in self.next_nodes:
            self.next_nodes.append(node)
            
    def execute(self, context: Dict[str, Any] = None) -> Any:
        """
        Execute the node's function.
        
        Args:
            context: Shared context/data from previous nodes
            
        Returns:
            The output of the function
        """
        context = context or {}
        self.status = "running"
        self.start_time = datetime.now()
        
        try:
            # Merge context with node inputs, but only pass parameters the function expects
            import inspect
            execution_inputs = {**context, **self.inputs}
            
            # Get function signature to know which parameters to pass
            sig = inspect.signature(self.function)
            params = sig.parameters
            
            # Filter inputs to only include parameters the function accepts
            filtered_inputs = {}
            for param_name in params:
                if param_name in execution_inputs:
                    filtered_inputs[param_name] = execution_inputs[param_name]
                elif params[param_name].default != inspect.Parameter.empty:
                    # Parameter has default, no need to pass it
                    continue
                # If parameter is required but not in inputs, let it fail naturally
            
            # Execute the function with filtered inputs
            result = self.function(**filtered_inputs)
            
            self.outputs = result if isinstance(result, dict) else {"result": result}
            self.status = "completed"
            self.end_time = datetime.now()
            
            return self.outputs
            
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            self.end_time = datetime.now()
            raise Exception(f"Node '{self.name}' failed: {e}\n{traceback.format_exc()}")
    
    def get_execution_time(self) -> Optional[float]:
        """Get the execution time in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> Dict:
        """Convert node to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "execution_time": self.get_execution_time(),
            "error": self.error,
            "outputs": self.outputs
        }


class Pipeline:
    """
    A workflow pipeline that manages and executes a sequence of nodes.
    Similar to n8n workflows but in Python.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize a pipeline.
        
        Args:
            name: Name of the pipeline
            description: Description of what this pipeline does
        """
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}
        self.start_node = None
        self.context = {}
        self.execution_log = []
        self.status = "ready"  # ready, running, completed, failed
        
    def add_node(self, node: WorkflowNode, is_start: bool = False) -> 'Pipeline':
        """
        Add a node to the pipeline.
        
        Args:
            node: The node to add
            is_start: Whether this is the starting node
            
        Returns:
            Self for chaining
        """
        self.nodes[node.name] = node
        if is_start or self.start_node is None:
            self.start_node = node
        return self
    
    def connect(self, from_node: str, to_node: str) -> 'Pipeline':
        """
        Connect two nodes in the pipeline.
        
        Args:
            from_node: Name of the source node
            to_node: Name of the destination node
            
        Returns:
            Self for chaining
        """
        if from_node not in self.nodes:
            raise ValueError(f"Node '{from_node}' not found in pipeline")
        if to_node not in self.nodes:
            raise ValueError(f"Node '{to_node}' not found in pipeline")
            
        self.nodes[from_node].connect_to(self.nodes[to_node])
        return self
    
    def execute(self, initial_context: Optional[Dict] = None, 
                stop_on_error: bool = True) -> Dict[str, Any]:
        """
        Execute the pipeline starting from the start node.
        
        Args:
            initial_context: Initial context/data to pass to the first node
            stop_on_error: Whether to stop execution on first error
            
        Returns:
            Dictionary with execution results and logs
        """
        if not self.start_node:
            raise ValueError("No start node defined for pipeline")
        
        self.status = "running"
        self.context = initial_context or {}
        self.execution_log = []
        
        start_time = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"Starting Pipeline: {self.name}")
        if self.description:
            print(f"Description: {self.description}")
        print(f"{'='*60}\n")
        
        try:
            self._execute_node(self.start_node, stop_on_error=stop_on_error)
            self.status = "completed"
            
        except Exception as e:
            self.status = "failed"
            print(f"\n❌ Pipeline failed: {e}")
            
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # Print summary
        self._print_summary(total_time)
        
        return {
            "status": self.status,
            "total_time": total_time,
            "nodes": {name: node.to_dict() for name, node in self.nodes.items()},
            "execution_log": self.execution_log,
            "final_context": self.context
        }
    
    def _execute_node(self, node: WorkflowNode, stop_on_error: bool = True):
        """Recursively execute a node and its connected nodes."""
        if node.status == "completed":
            return
        
        print(f"▶ Executing: {node.name}")
        if node.description:
            print(f"  Description: {node.description}")
        
        try:
            # Execute the node
            outputs = node.execute(self.context)
            
            # Update context with outputs
            self.context.update(outputs)
            
            # Log execution
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "node": node.name,
                "status": "completed",
                "execution_time": node.get_execution_time()
            }
            self.execution_log.append(log_entry)
            
            print(f"  ✓ Completed in {node.get_execution_time():.2f}s\n")
            
            # Execute next nodes
            for next_node in node.next_nodes:
                self._execute_node(next_node, stop_on_error=stop_on_error)
                
        except Exception as e:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "node": node.name,
                "status": "failed",
                "error": str(e)
            }
            self.execution_log.append(log_entry)
            
            print(f"  ✗ Failed: {e}\n")
            
            if stop_on_error:
                raise
    
    def _print_summary(self, total_time: float):
        """Print execution summary."""
        print(f"\n{'='*60}")
        print(f"Pipeline Execution Summary")
        print(f"{'='*60}")
        print(f"Pipeline: {self.name}")
        print(f"Status: {self.status}")
        print(f"Total Time: {total_time:.2f}s")
        print(f"\nNode Results:")
        
        for name, node in self.nodes.items():
            status_symbol = "✓" if node.status == "completed" else "✗" if node.status == "failed" else "○"
            exec_time = node.get_execution_time()
            time_str = f"{exec_time:.2f}s" if exec_time else "N/A"
            print(f"  {status_symbol} {name}: {node.status} ({time_str})")
            if node.error:
                print(f"    Error: {node.error}")
        
        print(f"{'='*60}\n")
    
    def save_to_json(self, filepath: str):
        """Save pipeline definition to JSON file."""
        pipeline_def = {
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "name": node.name,
                    "description": node.description,
                    "next_nodes": [n.name for n in node.next_nodes]
                }
                for node in self.nodes.values()
            ],
            "start_node": self.start_node.name if self.start_node else None
        }
        
        with open(filepath, 'w') as f:
            json.dump(pipeline_def, indent=2, fp=f)
        
        print(f"Pipeline definition saved to: {filepath}")
    
    def visualize(self) -> str:
        """
        Generate a text-based visualization of the pipeline.
        
        Returns:
            String representation of the pipeline structure
        """
        if not self.start_node:
            return "Empty pipeline"
        
        lines = [f"\nPipeline: {self.name}"]
        if self.description:
            lines.append(f"Description: {self.description}")
        lines.append("\nFlow:")
        
        visited = set()
        self._visualize_node(self.start_node, lines, visited, indent=0)
        
        return "\n".join(lines)
    
    def _visualize_node(self, node: WorkflowNode, lines: List[str], 
                       visited: set, indent: int = 0):
        """Helper method to recursively visualize nodes."""
        if node.name in visited:
            return
        
        visited.add(node.name)
        
        prefix = "  " * indent + "└─ " if indent > 0 else ""
        status = ""
        if node.status != "pending":
            status = f" [{node.status}]"
        
        lines.append(f"{prefix}{node.name}{status}")
        if node.description and indent == 0:
            lines.append(f"{'  ' * (indent + 1)}({node.description})")
        
        for next_node in node.next_nodes:
            self._visualize_node(next_node, lines, visited, indent + 1)


def create_simple_pipeline(name: str, tasks: List[tuple], 
                          description: str = "") -> Pipeline:
    """
    Helper function to create a simple linear pipeline.
    
    Args:
        name: Name of the pipeline
        tasks: List of tuples (node_name, function, inputs, description)
        description: Description of the pipeline
        
    Returns:
        Configured Pipeline object
    """
    pipeline = Pipeline(name, description)
    
    previous_node = None
    for i, task in enumerate(tasks):
        node_name = task[0]
        function = task[1]
        inputs = task[2] if len(task) > 2 else {}
        desc = task[3] if len(task) > 3 else ""
        
        node = WorkflowNode(node_name, function, inputs, desc)
        pipeline.add_node(node, is_start=(i == 0))
        
        if previous_node:
            pipeline.connect(previous_node, node_name)
        
        previous_node = node_name
    
    return pipeline


# Example usage functions
def example_basic_pipeline():
    """Example of a basic pipeline."""
    
    def load_data(filepath):
        print(f"  Loading data from {filepath}")
        time.sleep(0.5)
        return {"data": "loaded_data", "rows": 100}
    
    def process_data(data):
        print(f"  Processing data: {data}")
        time.sleep(0.5)
        return {"processed_data": f"{data}_processed"}
    
    def save_results(processed_data, output_path):
        print(f"  Saving to {output_path}")
        time.sleep(0.5)
        return {"saved": True, "path": output_path}
    
    # Create pipeline
    pipeline = Pipeline("Example Data Pipeline", "A simple data processing pipeline")
    
    # Add nodes
    load_node = WorkflowNode("Load Data", load_data, 
                            {"filepath": "/path/to/data.csv"},
                            "Load input data from file")
    process_node = WorkflowNode("Process Data", process_data,
                               description="Process the loaded data")
    save_node = WorkflowNode("Save Results", save_results,
                            {"output_path": "/path/to/output.csv"},
                            "Save processed results")
    
    pipeline.add_node(load_node, is_start=True)
    pipeline.add_node(process_node)
    pipeline.add_node(save_node)
    
    # Connect nodes
    pipeline.connect("Load Data", "Process Data")
    pipeline.connect("Process Data", "Save Results")
    
    # Visualize
    print(pipeline.visualize())
    
    # Execute
    results = pipeline.execute()
    
    return pipeline, results


if __name__ == "__main__":
    # Run example
    print("Running example pipeline...")
    example_basic_pipeline()
