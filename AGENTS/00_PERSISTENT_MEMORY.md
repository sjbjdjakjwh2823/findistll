# Preciso Agent Persistent Memory (Read First)

This repo uses a "Conductor + 3 Workers" workflow.

Hard rules (must follow):
- Before doing any work, read:
  - `AGENTS/01_CONDUCTOR.md`
  - `PLANS/Preciso_Enterprise_NonDev_Central_RAG_LLM_Master_Plan_v1.md`
- Workstreams use **file ownership**. Do not modify files owned by another workstream.
- Shared contracts are modified in **one branch only** (Conductor branch):
  - `app/services/types.py`
  - `app/core/auth.py`
  - Any other "public contract" file explicitly listed in `AGENTS/01_CONDUCTOR.md`
- Big changes must be wrapped behind a feature flag:
  - Default behavior must remain unchanged after merge.
  - Feature flags are read via `app/services/feature_flags.py`.
- If a Worker needs a shared-contract change:
  - Do NOT edit the file in the Worker branch.
  - Write a proposal section in the Worker MD (or a short note in the PR description) and ask Conductor to apply it.

Worktree rule:
- Use `git worktree` branches to run in parallel without stepping on the same files.
- Each Worker works only inside their assigned worktree directory under `.worktrees/`.

Iteration rule:
- When a plan phase is close to "DoD", Conductor must create a "Next Plan" to improve quality and keep momentum.

