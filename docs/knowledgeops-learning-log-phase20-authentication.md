# Phase 20: Authentication and Authorization

## Why this change was needed

Earlier screens allowed people to type an `actor` name. The backend filtered records by that name, but a browser could impersonate any user by changing the field or request header. This is acceptable only for a short-lived UI demonstration, not for an enterprise workspace.

## What was implemented

- `users` stores a username, display name, PBKDF2-SHA256 password hash, active state, and server-managed role.
- `auth_sessions` makes browser sessions revocable. Logging out revokes the session server-side before clearing the cookie.
- `/auth/register`, `/auth/login`, `/auth/logout`, and `/auth/me` establish the current user through an HttpOnly cookie. JavaScript cannot read the session token.
- The first registered user becomes `admin`; every later registration begins as `employee`.
- Administrators can assign `employee`, `service_desk`, or `admin` roles through protected account APIs.
- Every existing business API now derives its actor from the authenticated user. `X-Actor` and `X-Role` cannot alter identity or permissions in production.
- The front end opens with a login/register dialog and uses the logged-in user across workspace, Agent, tickets, notifications, search, and personal library. It hides the service-desk queue for users without a suitable role.

## How to explain it in an interview

"I separated identity from UI input. The browser sends only a session cookie, while the API verifies its signature, expiry, database session state, account activity, and role on every protected request. This prevents a user from reading another employee's tickets by changing a front-end actor field. Server-side session records provide revocable logout, unlike a JWT-only design."

## Production configuration

Set `AUTH_JWT_SECRET` to a unique, high-entropy value. Turn on `AUTH_COOKIE_SECURE=true` when the service is behind HTTPS. Registration is useful for local deployment; production should normally replace public registration with company SSO or an administrator invitation workflow.

## Interface follow-up

The authentication UI now uses a focused login/register card, while the signed-in state is represented by an avatar menu in the top bar. The dashboard's redundant heading block was removed so the operational overview appears first. Front-end behavior is separated by workspace under `knowledgeops/frontend`: `core.js`, `agent.js`, `knowledge.js`, `indexing.js`, `dashboard.js`, `tickets.js`, `engagement.js`, `notifications.js`, and `create-ticket.js`.
