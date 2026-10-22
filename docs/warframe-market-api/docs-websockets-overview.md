# Overview | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/websockets/overview/ (HTTP 200, copiado el 2026-10-22)

WebSocketsOverviewOn this pageOverview
Realtime public contracts for Warframe.market WebSocket clients.
ℹLegacy Auth ScopeAuthorization tokens obtained from the v1 API currently have scope all. That means v1-authenticated clients can ignore scope requirements for now. OAuth 2.0 will replace the v1 login flow in the future.
Version​
This documentation describes WebSocket API version v0.13.0.
Connection​
EnvironmentURLProductionwss://ws.warframe.market/socket
The server requires the wfm WebSocket subprotocol. Connections without this subprotocol are rejected.
const socket = new WebSocket('wss://ws.warframe.market/socket', 'wfm');
All messages are JSON-encoded.
Message Envelope​
{  route: string,  payload?: unknown,  id?: string,  meta?: {    stream?: string,    revision?: number,  },}
FieldTypeDescriptionroutestringRoute that selects the server or client handler.payloadunknownRoute-specific message body. Omitted when empty.idstringOptional message ID. Command responses reuse the incoming command id for correlation.metaobjectOptional stream metadata for ordered or deduplicated realtime events.meta.streamstringStream name. Status messages use status:{userId}.meta.revisionnumberMonotonic stream revision.
Message Types​
MarkerMeaning💬CommandClient request that expects :ok, :error, or protection error response.🔔EventOne-way server message that does not expect a response.🔁StreamEvent sequence with meta.stream and meta.revision for ordering.🔒Auth requiredMessage requires an authenticated and authorized client.🚧Not implementedRoute or behavior exists only as a planned/stubbed feature.
Generic Errors​
The server may send generic errors before a route handler runs.
RouteWhen it is sent@ws:error/cmd/typeIncoming message is not valid JSON for the WebSocket message envelope.@ws:error/cmd/routeIncoming route is unknown.@ws:error/cmd/handlerRoute handler returned an unhandled error.@wfm|protect/errorProtected route failed authentication or authorization checks.
Example protection error:
{  "route": "@wfm|protect/error",  "payload": "app.errors.userNotVerified",  "id": "message-id"}PreviousDashboardNextReportsVersionConnectionMessage EnvelopeMessage TypesGeneric Errors
