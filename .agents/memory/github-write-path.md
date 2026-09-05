---
name: GitHub connector write path
description: The GitHub connector's authenticated GraphQL client can create bundled commits when REST Git writes are blocked upstream.
---

Use the authenticated GitHub GraphQL client mutation `createCommitOnBranch` with an expected head SHA and bundled file additions/deletions when the connector's REST blob/tree write endpoints return an upstream Cloudflare 403.

**Why:** Read operations and the connector client worked, but REST blob/tree writes and the shell remote push were blocked; GraphQL successfully created one atomic commit without exposing credentials.

**How to apply:** Compare local and remote trees first, include `expectedHeadOid` to prevent overwriting concurrent changes, and verify `refs/heads/main` after the mutation.