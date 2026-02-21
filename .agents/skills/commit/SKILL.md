---
name: commit
description: Creates atomic git commits with conventional commit messages following standard prefixes (feat, fix, docs, refactor, test, chore, etc.). Stages changes, reviews uncommitted files, and generates properly formatted commit messages. Use when committing code, creating git commits, staging files, or when the user mentions conventional commits or commit messages.
license: MIT
metadata:
  author: Yves Tkaczyk
  version: "0.1"
---

# Git Commit Skill

This skill helps you create well-structured, atomic git commits following conventional commit standards.

## What this skill does

- Reviews uncommitted changes in your repository
- Stages the appropriate files for commit
- Generates atomic commit messages with conventional commit prefixes
- Ensures commits follow best practices

## When to use this skill

Use this skill when you:
- Need to commit changes to your git repository
- Want to create properly formatted commit messages
- Need help determining which files to stage
- Want to follow conventional commit standards

## How to use this skill

1. **Review uncommitted changes**
   - Run `git status` to see what files have been modified
   - Run `git diff HEAD` to review the actual changes
   - Run `git status --porcelain` for a machine-readable status

2. **Handle unrelated changes**
   - If the worktree is dirty, stage only the files relevant to this change
   - Prefer partial staging (e.g., `git add -p`) to keep commits atomic
   - If changes are unrelated, split into separate commits

3. **Stage the changes**
   - Add untracked files using `git add`
   - Stage modified files using `git add`
   - Ensure only related changes are staged together for atomic commits

4. **Run repository verification**
   - If the repo defines a verification script, run it before committing
   - In this repo, prefer: `uv run scripts/verify.py` for code changes
   - If verification is not applicable (docs-only), confirm with the user

5. **Create the commit message**
   - Use conventional commit format: `<type>: <description>`
   - Common types include:
     - `feat`: A new feature
     - `fix`: A bug fix
     - `docs`: Documentation changes
     - `style`: Code style changes (formatting, missing semicolons, etc.)
     - `refactor`: Code refactoring
     - `test`: Adding or updating tests
     - `chore`: Maintenance tasks
     - `perf`: Performance improvements
     - `ci`: CI/CD changes
     - `build`: Build system changes

6. **Commit the changes**
   - Create an atomic commit that represents a single logical change
   - Ensure the commit message clearly describes what changed and why
   - If the change is breaking, use `!` in the header and add a footer:
     - `feat!: drop legacy config format`
     - `BREAKING CHANGE: legacy config is no longer supported`

## Example

```bash
# Review changes
git status
git diff HEAD

# Stage changes
git add src/component.ts
git add tests/component.test.ts

# Commit with conventional message
git commit -m "feat: add new component for user profile display"
```