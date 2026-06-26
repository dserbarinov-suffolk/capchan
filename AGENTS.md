# AGENTS.md

## Read order

Before beginning work, read:

1. This file.
2. Any referenced document in `docs/` that affects the task.

## Design Documents

Place them in /docs, with a date and meaningful title (`YYYY-MM-DD-<name>.md`).
Before writing ANY design document or TDD, read `docs/writing-tdds.md` in full and follow it exactly — it defines the sizing gate, the required section structure, and the style constraints.

## Your Invariable Rules

- use `uv` for Python

### Hard constraint: NO ROOT / ADMIN ACCESS
- Never suggest `sudo`, system-wide Homebrew, `/usr/local`, or anything requiring admin privileges.
- Everything installs to user space: `~/.local/bin`, `pip3 install --user`, apps in `~/Applications`, npm prefix in `$HOME` if needed.

### Code Implementation

- Act as a discerning engineer: optimize for correctness, clarity, and reliability over speed;
    avoid risky shortcuts, speculative changes, and messy hacks just to get the code to work;
    cover the root cause or core ask, not just a symptom or a narrow slice.
- Practice Domain Driven Design for encapsulation and using consistent terms between the code and the TDDs [see writing-tdds instructions](./docs/writing-tdds.md)
- Choose Hexagonal Architecture/Ports and Adapters to avoid dependencies between layers and centralizing business logic in it's own core.
- Functional, composable, reusable code that minimizes mocks.
- Functions either perform work or arrange work, never both.
- Keep file size down to under 300 lines.
- Monorepo structure to synchronize packages.
- Make application state explicit.
- Do not write universal functions that infer ambiguous application state from loosely shaped input.
- Keep business rules in pure functions or domain services.
- Keep side effects in orchestrators, adapters, route handlers, hooks, or services that exist specifically to coordinate them.
- Every boundary must have a clear input contract and output contract.
- Map explicitly between DTOs, domain models, persistence models, and view models.
- Use linting and static type checking to ensure code correctness


## Project status: greenfield, pre-release

There are no paid users of any API, schema, file format, or database in this repository.
Nothing here is a published contract.
No version of anything has shipped.
This is all under active iterative development.

Because of this, when making changes:

- Prefer breaking changes.
  Change schemas, signatures, and formats freely to reach the right design.
- Delete superseded code.Do not leave the old version beside the new one.
- When old and new conflict, the old is wrong — replace it.
- When data and code disagree, the data is stale — regenerate it, don't adapt the code to it.
- Do not add migration logic, compatibility shims, version flags, fallback branches, deprecation markers, dual-read/dual-write paths, or anything labeled "legacy."
- If you find yourself preserving an old behavior "just in case," stop: there is no case - make the clean change instead.

