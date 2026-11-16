---
name: task-decompose
description: Decompose complex tasks into atomic subtasks with dependencies
---

# Task Decomposer

Decompose complex multi-step tasks into a Directed Acyclic Graph (DAG) of atomic subtasks with explicit dependencies.

## When to Use

Use this skill when:
- A task has 3+ distinct steps
- Steps have dependencies (some must complete before others)
- You need to track progress through a complex workflow
- Parallel execution opportunities exist (independent subtasks)
- The task involves research, implementation, or multi-phase work

## Decomposition Prompt Template

When decomposing a complex task, use this structure:

```
Analyze this task and decompose it into atomic subtasks:

TASK: [description of complex task]

For each subtask, provide:
1. id: Unique identifier (kebab-case, e.g., "fetch-user-data")
2. description: What this subtask accomplishes
3. formal: Optional formal notation (e.g., "fetch(id) -> UserData")
4. inputs: What data this subtask needs
5. output: What data this subtask produces
6. deps: Which subtask IDs must complete first (empty if root task)

Output as JSON in this format:
{
    "nodes": {
        "<task-id>": {
            "id": "<task-id>",
            "description": "<what this does>",
            "formal": "<optional formal notation>",
            "inputs": {"<param>": "<source>"},
            "output": {"<name>": "<type>"},
            "deps": ["<dependency-id>", ...]
        }
    }
}

Ensure:
- No circular dependencies
- All dependency IDs reference existing tasks
- Root tasks have empty deps arrays
- Outputs flow into dependent task inputs
```

## Validation Script

After creating a DAG, validate it:

```bash
# Save DAG to file
cat > task_dag.json << 'EOF'
<your JSON here>
EOF

# Validate structure (checks for cycles, missing deps, etc.)
uv run python scripts/agentica_patterns/task_decomposer.py validate task_dag.json

# See which tasks are ready to start
uv run python scripts/agentica_patterns/task_decomposer.py ready task_dag.json

# After completing some tasks, see what's next
uv run python scripts/agentica_patterns/task_decomposer.py ready task_dag.json --completed task-1,task-2
```

## Example Decomposition

Task: "Implement a user authentication system"

```json
{
    "nodes": {
        "design-schema": {
            "id": "design-schema",
            "description": "Design database schema for users and sessions",
            "formal": "design() -> Schema",
            "inputs": {},
            "output": {"schema": "Schema"},
            "deps": []
        },
        "create-tables": {
            "id": "create-tables",
            "description": "Create database tables from schema",
            "formal": "create(Schema) -> Tables",
            "inputs": {"schema": "design-schema.output.schema"},
            "output": {"tables": "Tables"},
            "deps": ["design-schema"]
        },
        "implement-register": {
            "id": "implement-register",
            "description": "Implement user registration endpoint",
            "formal": "register(UserData) -> User",
            "inputs": {"tables": "create-tables.output.tables"},
            "output": {"endpoint": "/auth/register"},
            "deps": ["create-tables"]
        },
        "implement-login": {
            "id": "implement-login",
            "description": "Implement login endpoint with JWT",
            "formal": "login(credentials) -> JWT",
            "inputs": {"tables": "create-tables.output.tables"},
            "output": {"endpoint": "/auth/login"},
            "deps": ["create-tables"]
        },
        "write-tests": {
            "id": "write-tests",
            "description": "Write integration tests for auth endpoints",
            "formal": "test(endpoints) -> Results",
            "inputs": {
                "register": "implement-register.output.endpoint",
                "login": "implement-login.output.endpoint"
            },
            "output": {"tests": "TestSuite"},
            "deps": ["implement-register", "implement-login"]
        }
    }
}
```

This DAG shows:
- `design-schema` is a root task (no deps)
- `implement-register` and `implement-login` can run in parallel (both only need `create-tables`)
- `write-tests` waits for both endpoints to be implemented

## Execution Pattern

1. **Decompose**: Use the prompt template to create the DAG
2. **Validate**: Run the validation script
3. **Execute**: Get ready tasks, complete them, mark completed
4. **Iterate**: Get next ready tasks until `is_complete`

```bash
# Example workflow
COMPLETED=""

# Get first batch of ready tasks
uv run python scripts/agentica_patterns/task_decomposer.py ready dag.json

# After completing design-schema
COMPLETED="design-schema"
uv run python scripts/agentica_patterns/task_decomposer.py ready dag.json -c $COMPLETED

# Continue until all complete
COMPLETED="design-schema,create-tables,implement-register,implement-login,write-tests"
uv run python scripts/agentica_patterns/task_decomposer.py ready dag.json -c $COMPLETED
# Output: "All tasks completed!"
```

## Data Structures

The script provides two main data structures:

### TaskNode
```python
@dataclass
class TaskNode:
    id: str                          # Unique identifier
    description: str                 # Human-readable description
    formal: str | None = None        # Optional formal notation
    inputs: dict[str, Any] = {}      # Input parameters
    output: dict[str, Any] = {}      # Output values
    deps: list[str] = []             # Dependency task IDs
```

### TaskDAG
```python
@dataclass
class TaskDAG:
    nodes: dict[str, TaskNode]       # All nodes by ID

    # Methods:
    # add_node(node) -> None
    # add_edge(from_id, to_id) -> None
    # validate() -> list[str]        # Returns errors
    # ready_tasks(completed) -> list[TaskNode]
    # is_complete(completed) -> bool
    # to_dict() / from_dict()        # Serialization
```

## Integration with Agent Patterns

This skill complements multi-agent patterns:

- **Hierarchical**: Coordinator decomposes, delegates subtasks to specialists
- **Swarm**: Each agent picks from ready_tasks pool
- **Pipeline**: Linear deps become pipeline stages
- **Map/Reduce**: Independent subtasks fan out, aggregation task collects
