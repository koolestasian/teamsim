# 0002. Start from the teamctx simulation prototype; decide the stack after research

- Status: Accepted
- Date: 2026-11-10
- Deciders: maintainer
- Plan reference: none

## Context

The idea for teamsim came from building a simulation to test teamctx: a fictional team chats
through a local Discord emulator while the real product syncs it, and a checker scores the
result against planted ground truth. That prototype works end to end, including a realism mode
based on patterns from a real student team server. It is Python 3.14, standard library only,
and it is specific to teamctx and Discord.

Prior art (see [docs/research](../research/)) shows two things. Persona simulators that predict
opinions are crowded and unreliable. Multi-agent environments that act on software exist, but
they are research benchmarks that are hard to set up. Neither covers easy, checkable team
simulation for testing a product.

## Decision

- Keep the working prototype as `prototypes/teamctx-sim/`, with its tests running in CI. It is
  the reference for what the product must do, not the product's architecture.
- Do not choose the language, runtime or architecture yet. The first milestone is a deeper audit
  of the prototype and a research pass on prior art, emulators and model options. The stack is
  decided in a later ADR based on that work.
- Every decision is judged against the three goals in the README: testing rather than opinion
  prediction, ground truth first, easy to run.

## Alternatives considered

- **Generalise the Python prototype directly:** fastest path to something runnable, but it
  would lock in choices (emulator, process model, teamctx coupling) before they are tested.
- **Start over in a new stack now:** throws away a working, tested reference before knowing
  what the new design needs.

## Consequences

### Good

- The project starts with working, tested code and real findings, not a blank page.
- The stack decision rests on research instead of habit.

### Bad

- The prototype carries teamctx-specific assumptions and some local-environment defaults
  (the emulator runs in a named WSL distro). These must be removed or generalised before the
  project goes public.

### Follow-ups

- Audit and research milestone; its findings go to `docs/research/`.
- A stack ADR after the research.
