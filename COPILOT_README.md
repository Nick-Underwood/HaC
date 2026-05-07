# Copilot Auxiliary File Handling

This repository treats Copilot instruction and agent files as sensitive operational metadata.

## Defaults
- Sensitive Copilot files are excluded in `.gitignore`.
- If a sensitive file must be committed, protect it with `git-crypt` using rules in `.gitattributes`.
- Keep only sanitized templates in git (for example: `.example` files).

## Restore Sensitive Files
1. Retrieve encrypted files from Forgejo or your secure backup.
2. Unlock with `git-crypt unlock` in a trusted environment.
3. Verify no secrets or operational metadata are exposed before committing.

## Public Mirror Safety
- Do not mirror raw Copilot instruction/agent files to public remotes.
- Mirror only sanitized templates and non-sensitive workspace metadata.