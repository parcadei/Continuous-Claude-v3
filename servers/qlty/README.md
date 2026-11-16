# qlty MCP Tools

Auto-generated wrappers for qlty MCP server.

## Tools

- `qlty_check`: Run linters on files. Returns issues found. Use --fix to auto-fix.
- `qlty_fmt`: Auto-format files using configured formatters.
- `qlty_metrics`: Calculate code quality metrics (complexity, duplication, etc).
- `qlty_smells`: Find code smells (duplication, complexity hotspots).
- `qlty_init`: Initialize qlty in a repository. Creates .qlty/qlty.toml.
- `qlty_plugins_list`: List available qlty plugins.

## Usage

```python
from servers.qlty import qlty_check

# Use the tool
result = await qlty_check(params)
```

**Note**: This file is auto-generated. Do not edit manually.
