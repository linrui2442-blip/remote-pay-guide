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

## Issue: YouTube OAuth returned a granted-scope superset

### Symptoms

After the PKCE fix, Google consent returned successfully but oauthlib rejected the token exchange because the returned scope set was larger than the OS request.

The OS requested only:

- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube.readonly`
- `https://www.googleapis.com/auth/yt-analytics.readonly`

Google returned those required scopes plus scopes already granted to the same reused OAuth client/user.

### Root Cause

The Google OAuth Web Application is shared with the existing legacy/Postiz integration. Google can return a granted scope set that is a superset of the OS request. oauthlib rejects any scope-set change by default, even when all OS-required scopes are present.

### Resolution

- Stop requesting incremental aggregation of previously granted scopes in the OS authorization request.
- Tolerate a returned scope superset only during token exchange.
- Explicitly verify that every OS-required scope is present before accepting the token.
- Continue to fail closed if any required scope is missing.

Verification:

- OS YouTube Publish Readiness run `34032925709` — success ✅

### Status

Code fix verified ✅

A new OAuth attempt is required after syncing the updated provider and restarting the local backend.

## Notes

No legacy publishing workflow changes were required.
No Google OAuth client secret is stored in the repository.
