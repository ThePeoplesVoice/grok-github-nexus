# Ara as GitHub collaborating partner

Standing notes for any human or agent landing work in this field.

## Home

- GitHub login — `ThePeoplesVoice`
- Partner repo — this repository
- Commercial sibling — `ThePeoplesVoice/naixus-roof-technicians`
- Private core — `ThePeoplesVoice/ara-complete-nexus`

## How Ara works this repo

- Discover work from issues, PRs, and search. Notifications currently 403 on the chat connector.
- Prefer branch `ara/<short-intent>` → commit → PR against `main`.
- Standing squash-merge on repos Shawn owns after he asked to land the change, when CI is green or there is no CI.
- Never auto-merge money, deploy, public-visibility, or token-rotation. Those need the human-approval labels in `config/gates.json`.
- Never commit secrets. Never copy the `GROK_GITHUB_TOKEN` description pattern.

## This change set

`ara/status-sync-2026-09-08` is a public-docs sync. It requires `human-approval:public` before merge.

## What this file is not

It is not the live Grok session skill. Session skills live in the agent host. This page is the public ledger so the partner rule survives a dead tab.
