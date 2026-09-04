# Remote Pay Guide Execution Context

## Purpose

This document records the current execution state for the next AI/developer handover.

It is not an architecture document and not a production SOP.

Its purpose is to prevent repeated historical investigation and keep future execution moving.

---

# Current Phase

Current production phase:

```
short06-short10 production
```

short04 and short05 are validated production assets.

---

# Existing Render Batch

Primary render workflow:

```
.github/workflows/render-launch02.yml
```

Purpose:

Generate the short02-short10 batch.

Artifact:

```
remote-pay-guide-short02-short10
```

The artifact should be reused when available.

Do not rerender existing validated assets unless a new production requirement exists.

---

# Source Run ID Rule

Cross-workflow publishing requires:

```
source_run_id
```

The value must come from:

```
Successful render-launch02 workflow run ID
```

Do not use:

- workflow number
- job ID
- shortened ID
- guessed values

Before asking the user for a run ID, check:

1. GitHub Actions history
2. RUN_HISTORY.md
3. Existing workflow records

---

# Operator Behavior When Information Is Missing

If source_run_id or another execution value is unavailable:

The operator must first attempt all available repository and history checks.

Do not immediately ask the user to manually search GitHub Actions.

Only request user input when the required information is genuinely unavailable through available tools.

The requested input should be the minimum possible reference:

Preferred:

```
workflow run URL
```

Not:

```
manual extraction of IDs
```

The purpose is to provide an entry point for verification, not to transfer repository investigation work to the user.

---

# If Workflow History Cannot Be Queried

If the available tools cannot list workflow runs:

Mark the missing information as:

```
UNKNOWN
```

Do not repeatedly request historical information that should be available from GitHub Actions.

Ask only for the minimum missing reference, such as the workflow run URL.

---

# Next Execution Steps

1. Identify successful render-launch02 batch run.
2. Run the matching publish-existing-shortXX workflow.
3. Verify:

```
Artifact
↓
GitHub Pages media URL
↓
Postiz
↓
Facebook / Instagram / YouTube
```

4. Update RUN_HISTORY.md.
5. Update PROJECT_STATUS.md.

---

# Recovery Rules

If one social platform fails:

Do not rerender.

Do not manually upload media.

Fix the platform authentication/API issue and rerun publishing.

The publish bridge is idempotent:

- successful platforms are skipped
- failed platforms are retried

---

# Operational Rule

Continue from the current production state.

Do not restart architecture analysis unless a new failure requires it.
