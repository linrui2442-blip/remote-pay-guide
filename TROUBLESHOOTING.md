# Troubleshooting

## Issue: Meta Developer Verification Triggered

### Symptoms

- Facebook publish failed
- Postiz returned Facebook publish error
- Meta requested developer verification

### Root Cause

Meta security verification triggered during OAuth/developer activity.

### Resolution

Completed Meta verification.
Publishing recovered.

### Status

Resolved ✅

## Issue: YouTube OAuth `invalid_grant` / Missing code verifier

### Symptoms

Google consent completed and redirected back to the local OS callback, but token exchange failed with:

`YouTube OAuth exchange failed: (invalid_grant) Missing code verifier.`

### Root Cause

Current `google-auth-oauthlib` generates a PKCE `code_verifier` when the authorization URL is created. The OS created a new `Flow` instance during the callback but did not persist the original verifier, so Google received a token request without the verifier that matched the earlier `code_challenge`.

### Resolution

- Persist the transient PKCE verifier together with the server-side OAuth state.
- Never expose the verifier to the frontend.
- Recreate the callback `Flow` with the original verifier and disable generation of a replacement verifier.
- Keep state and verifier single-use and time-limited.
- Add a regression smoke test confirming the verifier survives the redirect boundary.

Verification:

- OS YouTube Publish Readiness run `34032445867` — success ✅

### Status

Code fix verified ✅

A fresh OAuth attempt is required after the fixed backend is running because the failed authorization state was already consumed.

## Notes

No legacy publishing workflow changes were required.
No Google OAuth client secret is stored in the repository.
