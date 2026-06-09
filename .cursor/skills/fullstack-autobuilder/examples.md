# Examples

## Example Triggers

- "Add a paid subscription badge to dashboard and return plan info from API."
- "Implement vehicle status filter in listing endpoint and show it in the UI."
- "Wire parser confidence score into inspection detail page."

## Expected Delivery Shape

For each task:
1. Identify touched layers (service/API/UI/data).
2. Implement coherent changes in each layer.
3. Run available quick checks.
4. Return a short risk-aware summary.

## Example Response Style

```markdown
Implemented subscription visibility end-to-end.

- Backend: extended subscription service to expose `is_active` and `plan_name`.
- API: updated route response schema and handler mapping.
- UI: rendered plan badge and expiry text in dashboard template.
- Verification: ran targeted tests for subscription logic; lint not configured.
- Risk: no migration required; edge case is expired plans without renewal date.
```
