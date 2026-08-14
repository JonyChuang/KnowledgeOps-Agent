# Phase 21: Personal Center And Frontend Structure

## Objective

Provide a usable account self-service page, reachable from the signed-in avatar menu, and reduce the size and coupling of the frontend entry page.

## Design Decisions

1. The account menu now offers **Personal Center** before logout. The page is not a mock: it reads the signed-in account, updates the display name, and supports password changes.
2. Account changes are scoped to the authenticated session. The browser never sends a user ID for the update, so it cannot select another employee's account.
3. A password change verifies the current password, rejects reusing it, and revokes the user's other sessions. The session used to change the password remains available.
4. `index.html` is now only the page shell. Shared elements live in `frontend/components`, while feature pages live in `frontend/views`. `components-loader.js` loads the fragments and scripts in order before invoking the existing application bootstrap.

## API Contract

| Endpoint | Purpose | Permission |
| --- | --- | --- |
| `PATCH /api/v1/auth/me` | Update the current user's display name | Signed-in user |
| `POST /api/v1/auth/me/password` | Verify and replace the current user's password | Signed-in user |

The server derives the target account from the signed session cookie. It does not trust a browser-provided username or actor value.

## Frontend Flow

1. The user clicks their avatar in the top bar.
2. They select **Personal Center**.
3. The profile view renders account, role, registration time, and editable display name.
4. A successful name update refreshes the avatar and all current-user labels.
5. Password changes use a focused dialog with current password, new password, and confirmation fields.

## Follow-up Fix: Navigation And Logout State

The first fragment split exposed an HTML boundary error in the sidebar: the personal-library button was not closed before the administrator button. Browsers then treated both controls as one nested interactive area. The sidebar is now an explicit, standalone fragment with one complete button per navigation target.

Logout is also a page-level state transition, not just a cookie request. After the session is cleared, the workspace is hidden, the account menu closes, the dashboard selection resets, and the login dialog opens in login mode. This makes the unauthenticated state deterministic even when an API request fails during logout.

## Follow-up Fix: Static Asset Delivery

The initial frontend service mounted the Windows source directory directly into Nginx. The running container could serve `index.html` but intermittently failed to see sibling CSS, JavaScript, and HTML fragment files, causing Nginx to fall back to the entry page for every asset request.

The frontend is now a small dedicated image. Its Dockerfile copies the static files into Nginx at build time; the Nginx route configuration remains mounted independently. This makes static file delivery predictable and keeps the frontend deployment independent from the Python API image.

## Interview Notes

- Splitting a monolithic frontend page is not only about shorter files. It makes ownership explicit: shared layout, each business view, and its interaction script can change independently.
- Dynamic fragment loading must preserve initialization order. Here, the loader mounts all HTML first, loads all scripts in dependency order, then calls the bootstrap function once.
- Self-service account APIs should use the server session as the identity boundary. Accepting an arbitrary `user_id` from the frontend would introduce an insecure direct object reference risk.
