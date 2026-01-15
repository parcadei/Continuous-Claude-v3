# WORKPLAN: CodeRabbit Review Comparison

## Objective

Compare CodeRabbit (AI code review bot) output with alternative LLM analysis to evaluate:
1. Review quality and depth
2. Actionable vs noise ratio
3. Accuracy of suggestions
4. Coverage of security/architecture issues

## Status

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Data Collection | ✅ Complete | 113 reviews from 37 PRs archived |
| 2. Structure Documentation | ✅ Complete | README with field reference and extraction commands |
| 3. High-Value Review Index | ✅ Complete | Top reviews tagged by category |
| 4. Alternative LLM Analysis | ⏳ Pending | User to run comparison |
| 5. Comparison Report | ⏳ Pending | After phase 4 |

## Data Available

### Archive Contents
- **Location**: `docs/coderabbit-reviews/`
- **Format**: Raw GitHub API JSON responses
- **Total PRs**: 37 (27 origin + 10 fork)
- **Total Reviews**: 113

### Key Fields Per Review
```text
commit_id        - Exact SHA reviewed
submitted_at     - ISO 8601 timestamp
body             - Full markdown review with:
                   - Actionable count
                   - Nitpick count
                   - Files processed list
                   - Line-specific suggestions
                   - Code diff recommendations
html_url         - Direct GitHub link
```

### Extraction Commands
```bash
# Get all commit SHAs reviewed
for f in *.json; do echo "$f:"; jq -r '.[].commit_id' "$f"; done

# Count actionable comments per review
for f in *.json; do
  echo -n "$f: "
  jq -r '.[].body' "$f" | grep -o "Actionable comments posted: [0-9]*" | head -1
done

# List files reviewed per PR
jq -r '.[].body' origin-pr-76.json | grep -A50 "Files selected for processing"
```

## High-Value Test Cases

For LLM comparison, focus on these reviews (most feedback):

| PR | Reviews | Why |
|----|---------|-----|
| origin-pr-76 | 10 | Complex hook refactoring, PEP 723 migration |
| origin-pr-84 | 15 | Installation modes, symlink patterns |
| origin-pr-83 | 7 | Session state management |
| origin-pr-19 | 6+4 | Cross-platform script, deep merge logic |
| fork-pr-11 | 1 | Retry logic, error handling (our PR) |

## Comparison Criteria

### Quantitative
- [ ] Number of actionable issues found
- [ ] False positive rate (suggestions that don't apply)
- [ ] Line-level accuracy of suggestions
- [ ] Coverage (% of files reviewed with feedback)

### Qualitative
- [ ] Architectural insight quality
- [ ] Security issue detection
- [ ] Best practice recommendations
- [ ] Code pattern recognition

## Next Steps

1. **Select comparison LLM**: Claude, GPT-4, Gemini, etc.
2. **Create test prompt**:
   - Provide PR diff
   - Ask for code review
   - Compare output with CodeRabbit
3. **Document findings**: Add comparison results to this directory
4. **Report**: Summarize which reviewer provides better value

## File Structure
```text
docs/coderabbit-reviews/
├── README.md           # Index and documentation
├── WORKPLAN.md         # This file
├── origin-pr-*.json    # Origin repo reviews
├── fork-pr-*.json      # Fork repo reviews
└── comparison/         # (Future) LLM comparison results
```
