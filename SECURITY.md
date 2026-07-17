# Security Policy

DevOps Copilot connects to real infrastructure over SSH, stores encrypted server
credentials, and can execute commands on remote hosts. We take vulnerabilities
in this project seriously and appreciate responsible disclosure.

## Supported Versions

Only the latest published release on PyPI receives security fixes. We do not
currently maintain long-term-support branches.

| Version        | Supported          |
| -------------- | ------------------- |
| Latest release | :white_check_mark:  |
| Older releases | :x:                 |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report it privately using one of the following:

- [GitHub Security Advisories](https://github.com/irzix/devops-copilot/security/advisories/new) (preferred)
- Email the maintainer (see the GitHub profile linked in the repo) with the subject `[SECURITY] devops-copilot`

Please include:

- A description of the vulnerability and its impact
- Steps to reproduce (a minimal PoC helps a lot)
- The affected version/commit
- Any suggested remediation, if you have one

We aim to acknowledge reports within **72 hours** and to provide a fix or
mitigation plan within **14 days** for confirmed issues, depending on severity.

## Scope & Areas of Particular Concern

Given what this project does, the following areas carry higher risk and get
extra scrutiny:

- **Credential handling** — SSH passwords/keys are encrypted at rest with
  Fernet (AES-256) in `app/core/security.py`. Report any issue that could
  leak plaintext credentials, weak key derivation, or key reuse.
- **Command guardrails** — `app/modules/guardrails/service.py` uses semantic
  similarity search to block dangerous commands before execution. Bypasses of
  this guardrail (crafted commands that should be blocked but aren't) are
  considered security issues, not just bugs.
- **Human-in-the-loop approval** — Write commands require explicit `[y/N]`
  approval via LangGraph's `interrupt`. Any path that executes a write
  command without approval is a critical issue.
- **Auth/JWT** — `app/modules/auth/` issues and validates JWTs. Report
  issues with token forgery, expiry bypass, or privilege escalation.
- **Prompt injection** — Since an LLM agent has tool access to SSH execution,
  report any way that content returned from a remote server (logs, file
  contents, command output) can manipulate the agent into executing
  unintended commands, bypassing guardrails, or exfiltrating credentials.

## Disclosure Policy

We follow coordinated disclosure: once a fix is available, we'll credit
reporters (unless they prefer to stay anonymous) in the release notes and
`CHANGELOG.md`.
