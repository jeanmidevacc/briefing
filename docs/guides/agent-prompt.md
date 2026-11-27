# A prompt for coding agents

The prompt below sets up a coding agent (Claude Code, Codex, Cursor, Copilot, Aider…) to
write reports with briefing. Copy it, tick what you want, fill in the reader, and paste it
where your agent reads its instructions. A person can follow it too: it is the way we
recommend to build a report.

## How to use it

1. **Tick** with `[x]` the outputs you want (a report, a deck, an email digest, an embed:
   any of them, all from the same `report.py`) and the freedom you give the agent:
   - **Strict** (the default): briefing's blocks only. Every report looks like the others
     and stays easy to review.
   - **Open**: the agent may add `bf.HTML` and custom CSS where no block fits.
2. **Fill in** the reader: who reads the report and the question it answers. The agent
   designs everything around that question.
3. **Paste** it where your agent reads its instructions:

   | Agent | Where |
   | --- | --- |
   | Claude Code | `CLAUDE.md` at the project's root |
   | Codex, Copilot, Aider, Zed and others | `AGENTS.md` at the project's root |
   | Cursor | a rule in `.cursor/rules/`, or `AGENTS.md` |
   | A chat, or an agent you build | its system prompt |

The prompt keeps data and design apart: `extract.py` holds all the code that reads your
sources, and `report.py` only shapes what it saved and builds the outputs. You can change
the design again and again without touching the sources.

The same prompt is in the repository, as
[prompts/briefing-agent.md](https://github.com/jeanmidevacc/briefing/blob/main/prompts/briefing-agent.md).
Its `report.py` runs in briefing's tests, so it stays true to the installed version.

## The prompt

```{literalinclude} ../../prompts/briefing-agent.md
:language: markdown
```
