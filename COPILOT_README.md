# Copilot Auxiliary File Handling

This repository treats Copilot instruction and agent files as operational metadata.

## Defaults

- Copilot agent files use one canonical format: `.github/agents/*.agent.md`.
- Keep agent content free of secrets, tokens, internal-only hostnames, and private operational details.
- If sensitive variants are needed, store them outside the repository.

## Restore Sensitive Files

1. Retrieve encrypted files from Forgejo or your secure backup.
2. Unlock with `git-crypt unlock` in a trusted environment.
3. Verify no secrets or operational metadata are exposed before committing.

## Public Mirror Safety

- Do not mirror raw Copilot instruction/agent files to public remotes.
- Mirror only sanitized and non-sensitive workspace metadata.

## Custom Agent Artifacts

- Primary agent file: `.github/agents/hac-general.agent.md`
- Additional stage agents follow the same `.agent.md` naming convention.
- Keep committed agent files sanitized and environment-agnostic.

## Bootstrap Flow

- Use `pwsh -NoProfile -File ./scripts/bootstrap-copilot-agent.ps1` only for migration/normalization scenarios.
- The script can copy or normalize an agent file path and leaves an existing output file untouched.
