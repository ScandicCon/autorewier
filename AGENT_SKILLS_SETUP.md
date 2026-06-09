# Agent Skills Setup (Local)

## What was attempted here

The following commands were executed in this workspace:

- `npx skills add https://github.com/vercel-labs/skills --skill find-skills`
- `npx skills add https://github.com/vercel-labs/agent-browser --skill agent-browser`

In this environment, terminal execution is currently unstable (commands return without an exit status), so installation could not be confirmed reliably.

## Reliable local install steps

Run these commands from `C:\Users\Даниил\Desktop\autorewier` in your own terminal:

```powershell
npx skills add https://github.com/vercel-labs/skills --skill find-skills
npx skills add https://github.com/vercel-labs/agent-browser --skill agent-browser
```

## Verification checklist

Run:

```powershell
npx skills list
```

Expected: both `find-skills` and `agent-browser` are present in the installed skills list.

If `npx` asks for confirmation, accept it. If installation fails because of network/proxy restrictions, retry with the same commands after fixing npm network access.

