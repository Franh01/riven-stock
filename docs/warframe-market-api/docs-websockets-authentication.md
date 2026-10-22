# Authentication And Account Events | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/websockets/authentication/ (HTTP 200, copiado el 2026-10-22)

WebSocketsAuthentication And Account EventsOn this pageAuthentication And Account Events
Authentication commands and account-level server events.
Sign In​
Command@wfm|cmd/auth/signInAuthorize the WebSocket client.💬Command
This command supports auth tokens from the v1 API. If token is an empty string, the server attempts legacy cookie-based authorization.
Client Message​
{  "route": "@wfm|cmd/auth/signIn",  "id": "message-id",  "payload": {    "token": "jwtToken"  }}
Payload Fields​
FieldTypeDescriptiontokenstringJWT access token. Empty string enables legacy cookie fallback.deviceIdstringOptional. Device identifier accepted by the payload shape.
Success Message​
{  "route": "@wfm|cmd/auth/signIn:ok",  "id": "message-id"}
After successful sign-in, the server sends the current status with @wfm|event/status/set.
Error Message​
{  "route": "@wfm|cmd/auth/signIn:error",  "payload": "app.errors.unauthorized",  "id": "message-id"}
Sign Out​
Command@wfm|cmd/auth/signOutRemove the current actor from this WebSocket client.💬Command
Client Message​
{  "route": "@wfm|cmd/auth/signOut",  "id": "message-id"}
Success Message​
{  "route": "@wfm|cmd/auth/signOut:ok",  "id": "message-id"}
Error Message​
{  "route": "@wfm|cmd/auth/signOut:error",  "payload": "app.errors.wsNotAuthenticated",  "id": "message-id"}
Account Patch​
Event@wfm|event/account/patchNotify connected clients that account data was patched by backend systems.🔔Event
{  route: "@wfm|event/account/patch",  payload: UserPatch,}PreviousReportsNextStatus And ActivitySign InSign OutAccount Patch
