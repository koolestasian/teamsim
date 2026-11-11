# 0001. Dual licence: MIT OR Apache-2.0

- Status: Accepted
- Date: 2026-11-10
- Deciders: maintainer
- Plan reference: none

## Context

teamsim is meant to be open source and easy for students and small teams to adopt. Its first
prototype comes from teamctx, which is licensed `MIT OR Apache-2.0`, and fixtures are shared
between the two projects.

## Decision

License the project under `MIT OR Apache-2.0`, at the user's option, with both `LICENSE-MIT`
and `LICENSE-APACHE` in the repository. Fixtures and code copied from teamctx keep the same
terms.

## Alternatives considered

- **MIT only:** shortest and most familiar, but no express patent grant.
- **Apache-2.0 only:** has the patent grant; some projects prefer to combine with MIT-only code.
- **AGPL:** would keep hosted forks open, but deters companies and schools from using or
  contributing, which works against the accessibility goal.

## Consequences

### Good

- Same terms as teamctx, so code and fixtures move between the projects without friction.
- A familiar licence pair for contributors and packagers.

### Bad

- Two licence files to keep in step. A third party could run a closed hosted fork.

### Follow-ups

- Revisit only if the project adds dependencies whose licences conflict with either option.
