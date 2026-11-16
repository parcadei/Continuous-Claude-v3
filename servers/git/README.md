# git MCP Tools

Auto-generated wrappers for git MCP server.

## Tools

- `git_status`: Shows the working tree status
- `git_diff_unstaged`: Shows changes in the working directory that are not yet staged
- `git_diff_staged`: Shows changes that are staged for commit
- `git_diff`: Shows differences between branches or commits
- `git_commit`: Records changes to the repository
- `git_add`: Adds file contents to the staging area
- `git_reset`: Unstages all staged changes
- `git_log`: Shows the commit logs
- `git_create_branch`: Creates a new branch from an optional base branch
- `git_checkout`: Switches branches
- `git_show`: Shows the contents of a commit
- `git_branch`: List Git branches

## Usage

```python
from servers.git import git_status

# Use the tool
result = await git_status(params)
```

**Note**: This file is auto-generated. Do not edit manually.
