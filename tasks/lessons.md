# Lessons

## Auth Form Controls

- Password visibility should be an inline eye icon inside the password field, not a separate text button below the field.
- Keep the password input's accessible label unique; icon controls can use short contextual labels such as `Show` / `Hide` plus a title so tests and assistive tech do not confuse them with the field label.
- Single secondary actions in auth forms should keep a one-column footer layout at desktop widths; use two-column grids only when two actions are rendered.

## Local Auth Debugging

- When auth appears broken in the Next client, verify `GET /api/health` and the FastAPI backend on `127.0.0.1:8000` before changing form/proxy code; a generic `502` from auth proxy routes means the backend boundary is unreachable.

## Case-Scoped Generated State

- When a workspace view switches cases, generated artifacts such as readiness reports, drafts, citation checks, and exports must either be cleared at the selection boundary or rendered only when their `case_id` matches the selected case.
- Do not rely on a new case list row to overwrite component-local generated state; generated state can outlive the selected case unless it is explicitly scoped.

## Prior Auth And Appeal Shared Helpers

- Shared workflow helpers must branch on `case_type` when selecting draft letters or naming exports.
- Do not hardcode `prior_auth` in export, citation, or draft lookup paths that are also used by appeal cases.
