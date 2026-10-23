# policy-writer — project rules

Project: "Who guards the policy writer?" — audit of Progent's LLM policy writer on AgentDojo (see project.txt).

## Development rules (also in ~/.claude/CLAUDE.md)
1. Reuse by copying: copy referenced upstream code (Progent, AgentDojo) into this repo and edit the copy; don't rewrite from memory.
2. Print informatively, handle caches deliberately, print every exception with traceback. No silent failures.
3. Think through design and failure modes before implementing.
4. Build in small pieces; test each piece before moving on.
5. Be precise about the goal; run independent audits of earlier work; discuss critical design decisions with the user.
6. Generalize; never hardcode or patch for a single case; NEVER use fallbacks unless the user explicitly asks (fail loudly instead).
7. Use standard libraries/SDKs; keep code clean and debuggable.

## Project-specific conduct
- Every reported number must trace to an executed run or trace file. No fabricated numbers.
- Reproduce one published number exactly before changing conditions.
- Sandboxed AgentDojo only. Remove API keys before submission.
