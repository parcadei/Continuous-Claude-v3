# Codemap: Path Traversal Security Analysis

**Target:** `scripts/agentica/agent_handoff.py`
**Issue:** CodeRabbit review flagged potential path traversal in artifact names

---

## 1. Module Structure

```
agent_handoff.py (530 lines)
├── Constants (L47-51)
│   ├── SAFE_PATH_COMPONENT = re.compile(r'^[a-zA-Z0-9_\-]+$')
│   └── SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$')
├── Validation Functions (L54-161)
│   ├── _validate_path_component(component, component_type) -> str
│   ├── _validate_filename(name) -> str
│   └── _validate_path_within_base(path, base) -> Path
├── AgentHandoff Class (L163-516)
│   ├── __init__(session_id, base_dir)
│   ├── get_output_dir(phase) -> Path
│   ├── chain_from(upstream_phase) -> Path
│   ├── write_summary(phase, summary, metadata) -> Path
│   ├── read_summary(phase) -> str | None
│   ├── write_artifact(phase, name, content) -> Path  [TARGET]
│   ├── read_artifact(phase, name) -> str | None
│   ├── list_artifacts(phase) -> list[str]
│   ├── build_system_prompt(...) -> str
│   ├── get_memory_context() -> str
│   └── cleanup() -> None
└── Convenience Functions (L518-529)
    ├── create_handoff(session_id) -> AgentHandoff
    └── get_phase_summary(session_id, phase) -> str | None
```

---

## 2. Call Graph

```
External Input Sources
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    AgentHandoff.__init__                       │
│  session_id ──► _validate_path_component() ──► validated      │
│  base_dir   ──► Path.resolve()                                 │
│  session_dir ──► _validate_path_within_base() ──► checked     │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    get_output_dir(phase)                       │
│  phase ──► _validate_path_component() ──► validated           │
│  output_dir ──► _validate_path_within_base() ──► checked      │
│  Creates: session_dir/phase/artifacts/                         │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│              write_artifact(phase, name, content)              │
│  name  ──► _validate_filename() ──► validated                 │
│  phase ──► get_output_dir() ──► already validated             │
│  artifact_path ──► _validate_path_within_base() ──► checked   │
│  artifact_path.write_text(content) ──► FS write               │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow: User Input to File System

```
Input Sources                Validation Layer              File System
─────────────────           ──────────────────           ─────────────
session_id (str)  ─────►  _validate_path_component()
                              │ Checks:
                              │ - Empty check
                              │ - Null byte (\x00)
                              │ - ".." traversal
                              │ - "/" or "\" separators
                              │ - "~" or "/" prefix
                              │ - Allowlist regex
                              ▼
                          SAFE_PATH_COMPONENT.match()
                              │
phase (str)  ─────────►  _validate_path_component()
                              │
                              ▼
name (artifact)  ─────►  _validate_filename()
                              │ Checks:
                              │ - Empty check
                              │ - Null byte
                              │ - ".." traversal
                              │ - "/" or "\" separators
                              │ - "." prefix (hidden)
                              │ - Allowlist regex
                              ▼
                          SAFE_FILENAME.match()
                              │
Final Path  ──────────►  _validate_path_within_base()
                              │ Checks:
                              │ - Resolve symlinks
                              │ - Case-insensitive (macOS)
                              │ - Containment check
                              ▼
                          artifact_path.write_text()  ───►  FS Write
```

---

## 4. Existing Security Measures

### 4.1 Input Validation (Allowlist)

| Validator | Pattern | Blocks |
|-----------|---------|--------|
| `_validate_path_component` | `^[a-zA-Z0-9_\-]+$` | `.`, `/`, `\`, special chars |
| `_validate_filename` | `^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$` | Hidden files, multi-ext |

### 4.2 Path Containment (Defense-in-Depth)

```python
def _validate_path_within_base(path: Path, base: Path) -> Path:
    resolved = path.resolve()
    base_resolved = base.resolve()
    # macOS case-insensitive handling
    if not resolved_str.startswith(base_str + os.sep):
        raise ValueError(...)
```

### 4.3 Checks Per Entry Point

| Method | Input Validated | Containment Checked |
|--------|-----------------|---------------------|
| `__init__` | session_id (L179) | session_dir (L186) |
| `get_output_dir` | phase (L203) | output_dir (L208) |
| `chain_from` | upstream_phase (L227) | path (L232) |
| `write_summary` | via get_output_dir | via get_output_dir |
| `read_summary` | phase (L276) | summary_path (L281) |
| `write_artifact` | name (L302) | artifact_path (L309) |
| `read_artifact` | phase+name (L328-329) | artifact_path (L334) |
| `list_artifacts` | phase (L353) | artifacts_dir (L358) |
| `cleanup` | - | session_dir (L504) |

---

## 5. Attack Surface Analysis

### 5.1 Entry Points

| Entry Point | Risk Level | Protection |
|-------------|------------|------------|
| `AgentHandoff(session_id)` | HIGH | Validated + contained |
| `get_output_dir(phase)` | HIGH | Validated + contained |
| `write_artifact(phase, name)` | HIGH | Both validated + contained |
| `cleanup()` | CRITICAL | Re-validates before rmtree |

### 5.2 Attack Vectors Blocked

| Attack | Vector | Blocked By |
|--------|--------|------------|
| `../../../etc/passwd` | Traversal | Regex + containment |
| `/tmp/evil` | Absolute path | `/` check + containment |
| `session\x00.evil` | Null byte | `\x00` check |
| `.bashrc` | Hidden file | `.` prefix check |
| `..\\..\\win` | Backslash | `\` check |
| `file.tar.gz` | Double ext | Single-dot regex |
| Symlink escape | Race | `resolve()` before write |

### 5.3 Remaining Considerations

1. **Content validation:** `content` param is not validated (intentional - arbitrary content allowed)
2. **Timing attacks:** Path resolution before write prevents TOCTOU
3. **Encoding attacks:** Regex allowlist rejects URL-encoded or unicode variants

---

## 6. Callers of write_artifact()

### Production Code
- None found outside `agent_handoff.py` itself

### Test Files
| File | Context |
|------|---------|
| `tests/unit/test_agent_handoff_security.py` | Security test suite (16 tests) |
| `tests/unit/test_crud_prompt_reliability.py` | CRUD pattern tests |

### Documentation
| File | Context |
|------|---------|
| `docs/agentica-integration/issue-01-path-traversal/` | Previous analysis |
| `docs/agentica-integration-fixes/issue-1-path-traversal/` | Fix documentation |

---

## 7. CodeRabbit Comment vs Current Implementation

### CodeRabbit Suggested Fix (lines 127-141 in comment):
```python
if "/" in name or "\\" in name or name.startswith("."):
    raise ValueError(f"Invalid artifact name: {name}")
```

### Current Implementation (lines 287-312):
```python
def write_artifact(self, phase: str, name: str, content: str) -> Path:
    _validate_filename(name)          # Allowlist regex + blocklist checks
    output_dir = self.get_output_dir(phase)  # Validates phase
    artifact_path = output_dir / "artifacts" / name
    _validate_path_within_base(artifact_path, self.base_dir)  # Containment
    artifact_path.write_text(content)
    return artifact_path
```

### Assessment

| Aspect | CodeRabbit Suggestion | Current Implementation |
|--------|----------------------|------------------------|
| Blocklist | `/ \ .` prefix | `/ \ .. \x00 .` prefix |
| Allowlist | None | `^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)?$` |
| Containment | None | `_validate_path_within_base()` |
| Defense layers | 1 | 3 (validate + allowlist + containment) |

**Conclusion:** Current implementation exceeds CodeRabbit's suggested fix with defense-in-depth.

---

## 8. Test Coverage

| Test Class | Test Count | Coverage |
|------------|------------|----------|
| `TestSessionIdPathTraversal` | 4 | Basic, deep, absolute, null byte |
| `TestPhasePathTraversal` | 6 | All phase-accepting methods |
| `TestArtifactNameTraversal` | 4 | write, hidden, read, null byte |
| `TestCleanupPathTraversal` | 3 | Valid, escaped, symlink |
| `TestDoubleEncodingAttacks` | 4 | Dots, backslash, mixed, URL |
| `TestUnicodeVariants` | 2 | Slash variants, dot variants |
| `TestAttackVectorsFromPlan` | 4 | All plan attack vectors |
| `TestValidInputsStillWork` | 4 | Regression tests |

**Total:** 31 security-focused tests in `test_agent_handoff_security.py`

---

## 9. File Locations

- **Source:** `/Users/cosimo/.../scripts/agentica/agent_handoff.py`
- **Security Tests:** `/Users/cosimo/.../tests/unit/test_agent_handoff_security.py`
- **CRUD Tests:** `/Users/cosimo/.../tests/unit/test_crud_prompt_reliability.py`
- **Previous Analysis:** `/Users/cosimo/.../docs/agentica-integration/issue-01-path-traversal/`
