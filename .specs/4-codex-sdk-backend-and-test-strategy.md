**Status:** Draft
**Created:** 2026-04-14
**Purpose:** Add a runtime-selectable Codex SDK backend while preserving the current CLI workflow, and define a tests-first rollout that hardens the LLM layer before feature work.

---

# Specification 4: Codex SDK Backend and Test Strategy

## 1. Executive Summary

**1.1 Objective**: Extend CV Builder so the same `cv-builder generate|validate|auth` workflow can run against either the existing Bedrock-oriented backend or a new Codex SDK backend.

**1.2 Constraints**:
- The existing CLI flow must remain intact.
- The default backend must remain the current one unless explicitly overridden.
- Test reliability on Windows must be fixed before backend feature work proceeds.
- The specification must remain generic and not depend on a single target job posting.

**1.3 Solution**:
1. Introduce a provider-agnostic LLM layer with runtime backend selection.
2. Preserve the current backend behavior behind a `litellm` backend implementation.
3. Add a `codex-sdk` backend implemented through a small Node bridge using the official TypeScript Codex SDK.
4. Extend validation to check backend prerequisites without making live model calls.
5. Add tests first, then implement the backend changes, then validate with live dry runs.

---

## 2. Backend Architecture

### 2.1 Stable Python Interface

All LLM-backed agents continue to use the same Python interface:

```python
await llm_client.complete(
    messages=[...],
    model=None,
    temperature=0.7,
    max_tokens=4096,
)
```

The interface returns the final assistant text exactly as it does today.

### 2.2 Runtime Backend Selection

Backend selection precedence:

1. CLI flag `--llm-backend`
2. Environment variable `CV_BUILDER_LLM_BACKEND`
3. Default value `litellm`

Supported values:
- `litellm`
- `codex-sdk`

### 2.3 Backend Responsibilities

**`litellm` backend**
- Preserves the current Bedrock-oriented behavior.
- Resolves per-agent model selection using the existing fast/best mapping.
- Avoids eager provider imports during module import and test collection.

**`codex-sdk` backend**
- Uses the actual Codex SDK, not a normal OpenAI text-generation client.
- Converts the existing chat transcript into a deterministic Codex prompt.
- Starts a Codex thread in the requested working directory and returns the final response text.
- Uses `skipGitRepoCheck=true` because local execution may occur outside a Git repository.

---

## 3. Configuration Surface

### 3.1 Existing Configuration Kept

The following remain in use for the `litellm` backend:
- `BEDROCK_MODEL_FAST`
- `BEDROCK_MODEL_BEST`
- existing fast/best per-agent routing

### 3.2 New Codex Configuration

Add the following environment variables:
- `CODEX_MODEL_FAST`
- `CODEX_MODEL_BEST`
- `CODEX_NODE_BIN` with default `node`

Optional authentication remains external to this repo, for example via local Codex authentication state or API-key-based Codex CLI setup.

### 3.3 CLI Changes

Add `--llm-backend {litellm,codex-sdk}` to:
- `cv-builder generate`
- `cv-builder validate`

`auth` remains Google-Drive-specific and unchanged.

---

## 4. Python to Node Bridge

### 4.1 Rationale

The official Codex docs describe the TypeScript SDK as the primary server-side SDK. The Python SDK is experimental and depends on a local checkout of the Codex repository, so it is not the supported integration path for this project.

Reference:
- https://developers.openai.com/codex/sdk

### 4.2 Bridge Layout

Add a small `codex_bridge/` package containing:
- `package.json`
- `runner.mjs`

The Python backend invokes the runner as a subprocess and exchanges JSON over stdin/stdout.

### 4.3 Request Contract

Python sends a JSON request containing:
- `prompt`
- `model`
- `cwd`

Optional fields may include:
- `temperature`
- `max_tokens`

### 4.4 Response Contract

Node returns a JSON response containing:
- `content`
- `thread_id`
- optional usage metadata when available

Errors return a non-zero exit code plus structured stderr text.

---

## 5. Test-First Rollout

### 5.1 First Milestone

Fix the current pytest collection failure on Windows by ensuring:
- `litellm` is not imported at Python module import time
- non-LLM tests can import agents and orchestrator safely
- helper-method tests can instantiate LLM-backed agents without requiring live model configuration

### 5.2 New Tests

Add:
- `tests/test_llm_factory.py`
- `tests/test_llm_config.py`
- `tests/test_litellm_backend.py`
- `tests/test_codex_backend.py`

Update existing tests so they inject fake LLM clients/backends rather than assuming a single concrete provider implementation.

### 5.3 Job Parsing Coverage

Add a recorded fixture derived from a real job posting page shape so HTML extraction is exercised without relying on live network calls.

### 5.4 Markers

Keep:
- `integration`

Add:
- `codex_integration`

---

## 6. Acceptance Criteria

The rollout is complete when all of the following are true:

1. `python -m pytest` passes for the non-integration suite on Windows.
2. `cv-builder validate --llm-backend litellm` performs backend prerequisite checks without live model calls.
3. `cv-builder validate --llm-backend codex-sdk` performs backend prerequisite checks without live model calls.
4. `cv-builder generate ... --dry-run --llm-backend litellm` remains compatible with the current flow.
5. `cv-builder generate ... --dry-run --llm-backend codex-sdk` completes the same flow using the Codex backend.
6. README documentation explains installation, backend selection, and Codex bridge setup.

---

## 7. Operational Constraints and Failure Modes

### 7.1 `litellm` Backend

Failure conditions:
- missing Bedrock model configuration
- provider import failure
- Bedrock/API call failure
- invalid model output that does not parse as JSON

Mitigation:
- lazy imports
- clear validation errors
- backend-isolated tests

### 7.2 `codex-sdk` Backend

Failure conditions:
- Node.js missing or too old
- bridge dependencies not installed
- Codex authentication unavailable
- Codex CLI execution failure
- invalid model output that does not parse as JSON

Mitigation:
- prerequisite validation
- small bridge surface
- subprocess-level error capture
- backend-isolated tests

### 7.3 Live Smoke Testing

Final live verification should use `--dry-run` first.

Live Google Doc creation is only attempted if the local Google Drive configuration and authentication already validate cleanly.
