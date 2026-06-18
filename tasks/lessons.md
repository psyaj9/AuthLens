# Lessons

## Case-Scoped Generated State

- When a workspace view switches cases, generated artifacts such as readiness reports, drafts, citation checks, and exports must either be cleared at the selection boundary or rendered only when their `case_id` matches the selected case.
- Do not rely on a new case list row to overwrite component-local generated state; generated state can outlive the selected case unless it is explicitly scoped.

## Prior Auth And Appeal Shared Helpers

- Shared workflow helpers must branch on `case_type` when selecting draft letters or naming exports.
- Do not hardcode `prior_auth` in export, citation, or draft lookup paths that are also used by appeal cases.
