# Workflow Quick Start Guide

Get started with the n8n-inspired workflow system in 5 minutes!

## Installation

The workflow system is included in `msk_modelling_python`. No additional dependencies required.

```python
from msk_modelling_python.workflow import Pipeline, WorkflowNode, create_simple_pipeline
```

## Your First Pipeline in 3 Steps

### Step 1: Define Your Functions

Each function represents a task in your workflow:

```python
def load_data(filepath):
    """Load data from file."""
    # Your loading code here
    data = load_from_file(filepath)
    return {"data": data}  # Always return a dictionary

def process_data(data):
    """Process the loaded data."""
    # Your processing code here
    result = process(data)
    return {"result": result}

def save_results(result, output_path):
    """Save results to file."""
    # Your saving code here
    save_to_file(result, output_path)
    return {"status": "saved"}
```

**Key Rule**: Always return a dictionary. The keys become available to subsequent nodes.

### Step 2: Create the Pipeline

```python
# Create pipeline
pipeline = Pipeline("Data Processing", "Load, process, and save data")

# Create nodes
load_node = WorkflowNode("Load", load_data, {"filepath": "input.csv"})
process_node = WorkflowNode("Process", process_data)
save_node = WorkflowNode("Save", save_results, {"output_path": "output.csv"})

# Add nodes to pipeline
pipeline.add_node(load_node, is_start=True)  # First node
pipeline.add_node(process_node)
pipeline.add_node(save_node)

# Connect nodes (define flow)
pipeline.connect("Load", "Process")
pipeline.connect("Process", "Save")
```

### Step 3: Execute

```python
# Visualize (optional)
print(pipeline.visualize())

# Execute
results = pipeline.execute()

# Check results
print(f"Status: {results['status']}")
print(f"Duration: {results['total_time']:.2f}s")
```

## Even Simpler: Use the Helper

For linear pipelines, use `create_simple_pipeline()`:

```python
from msk_modelling_python.workflow import create_simple_pipeline

# Define tasks as list of tuples: (name, function, inputs, description)
tasks = [
    ("Load", load_data, {"filepath": "input.csv"}, "Load input data"),
    ("Process", process_data, {}, "Process the data"),
    ("Save", save_results, {"output_path": "output.csv"}, "Save results")
]

# Create and execute
pipeline = create_simple_pipeline("My Pipeline", tasks)
results = pipeline.execute()
```

## Real Example: OpenSim Analysis

```python
from msk_modelling_python.workflow import Pipeline, WorkflowNode

def setup_files(subject, trial):
    """Setup file paths."""
    return {
        "model": f"/project/models/{subject}.osim",
        "markers": f"/project/data/{subject}/{trial}/markers.trc",
        "output": f"/project/results/{subject}/{trial}"
    }

def run_ik(model, markers, output):
    """Run Inverse Kinematics."""
    ik_file = f"{output}/IK.mot"
    # Run IK here (using msk_modelling_python.bops or OpenSim)
    return {"ik_output": ik_file}

def run_id(model, ik_output, output):
    """Run Inverse Dynamics."""
    id_file = f"{output}/ID.sto"
    # Run ID here
    return {"id_output": id_file}

# Create pipeline
pipeline = Pipeline("OpenSim Analysis")

# Add nodes
pipeline.add_node(WorkflowNode("Setup", setup_files, 
                               {"subject": "S01", "trial": "walk"}), 
                  is_start=True)
pipeline.add_node(WorkflowNode("IK", run_ik))
pipeline.add_node(WorkflowNode("ID", run_id))

# Connect
pipeline.connect("Setup", "IK")
pipeline.connect("IK", "ID")

# Execute
results = pipeline.execute()
```

## Common Patterns

### Pattern 1: Sequential Processing

```python
tasks = [
    ("Step1", func1, {"param": "value"}, "Description"),
    ("Step2", func2, {}, "Description"),
    ("Step3", func3, {}, "Description")
]
pipeline = create_simple_pipeline("Sequential", tasks)
```

### Pattern 2: Fan-Out (One to Many)

```python
pipeline = Pipeline("Fan Out")
pipeline.add_node(WorkflowNode("Start", start_func), is_start=True)
pipeline.add_node(WorkflowNode("Branch1", branch1_func))
pipeline.add_node(WorkflowNode("Branch2", branch2_func))
pipeline.add_node(WorkflowNode("Branch3", branch3_func))

# One node feeds into multiple
pipeline.connect("Start", "Branch1")
pipeline.connect("Start", "Branch2")
pipeline.connect("Start", "Branch3")
```

### Pattern 3: Conditional Processing

```python
def check_condition(data):
    if condition_met(data):
        return {"process_type": "advanced", "data": data}
    else:
        return {"process_type": "basic", "data": data}

def process_advanced(data):
    # Advanced processing
    return {"result": result}

def process_basic(data):
    # Basic processing
    return {"result": result}

# In your pipeline logic, you'd call the appropriate function
# based on the process_type
```

### Pattern 4: Error Handling

```python
def safe_process(data):
    try:
        result = risky_operation(data)
        return {"result": result, "status": "success"}
    except Exception as e:
        print(f"Error: {e}")
        return {"result": None, "status": "failed", "error": str(e)}

# Continue execution despite errors
results = pipeline.execute(stop_on_error=False)
```

## Tips for Success

1. **Return Dictionaries**: Always return `dict` from your functions
   ```python
   # Good
   return {"output": value, "status": "done"}
   
   # Bad
   return value  # Not a dict
   ```

2. **Clear Naming**: Use descriptive names for nodes and outputs
   ```python
   return {"ik_output": path}  # Clear
   return {"out": path}        # Unclear
   ```

3. **Check Connections**: Use `pipeline.visualize()` before executing

4. **Handle Errors**: Add try-except in your functions

5. **Test Incrementally**: Build your pipeline one node at a time

## Next Steps

- Read [WORKFLOW_README.md](msk_modelling_python/WORKFLOW_README.md) for complete documentation
- Check [workflow_example.py](example_data/workflow_example.py) for more examples
- See [workflow_integration_guide.md](example_data/workflow_integration_guide.md) for integrating with existing code
- Run [workflow_opensim_complete.py](example_data/workflow_opensim_complete.py) for a real-world example

## Getting Help

If you encounter issues:

1. Use `pipeline.visualize()` to check structure
2. Check node status in results: `results['nodes']['NodeName']['status']`
3. Look at error messages: `results['nodes']['NodeName']['error']`
4. Review execution log: `results['execution_log']`

## Common Issues

**Issue**: `TypeError: function() got an unexpected keyword argument`
**Solution**: Function is receiving extra parameters. Either accept them with `**kwargs` or check what the previous node is outputting.

**Issue**: `TypeError: function() missing required positional argument`
**Solution**: Required parameter not provided. Add it to node inputs or ensure previous node outputs it.

**Issue**: Node doesn't execute
**Solution**: Check connections with `pipeline.visualize()`. Node must be connected from start.

## Summary

Three simple steps to create any pipeline:
1. **Define functions** that return dictionaries
2. **Create nodes** and connect them
3. **Execute** and monitor

Happy pipelining! 🚀
