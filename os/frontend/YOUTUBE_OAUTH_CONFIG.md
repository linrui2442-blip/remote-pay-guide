# YouTube OAuth Configuration

## Local Redirect URI

Add this URI to the authorized redirect URIs of the existing Google OAuth Web Application used for YouTube:

```
http://localhost:5173/oauth/youtube/callback
```

The existing Postiz redirect URI can remain configured alongside the OS callback. The OS does not require a second OAuth client.

## Local Environment

Configure the OS backend process with these environment variables:

```
YOUTUBE_OAUTH_CLIENT_ID
YOUTUBE_OAUTH_CLIENT_SECRET
YOUTUBE_OAUTH_REDIRECT_URI=http://localhost:5173/oauth/youtube/callback
```

Fallback Google variable names are also supported by the backend, but the YouTube-specific names are preferred for clarity.

Do not commit client-secret values to this repository.

## Scope Profiles

The OS keeps publishing backward compatible while allowing explicit analytics authorization:

- `publish`: `youtube.upload`
- `analytics`: `youtube.readonly` + `yt-analytics.readonly`
- `full`: publishing + analytics scopes

The control center uses the `full` profile when the user chooses **Connect YouTube (Publish + Analytics)**. Existing upload-only credentials are not silently upgraded; Google authorization must be completed again before live analytics collection can start.

## Production Redirect URI

For a deployed frontend, configure the actual HTTPS callback instead of the local URI, for example:

```
https://domain.com/oauth/youtube/callback
```

`YOUTUBE_OAUTH_REDIRECT_URI` must exactly match an authorized redirect URI in the Google OAuth Web Application.
