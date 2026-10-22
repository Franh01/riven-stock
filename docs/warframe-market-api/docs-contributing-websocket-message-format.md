# WebSocket Message Format | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/contributing/websocket-message-format/ (HTTP 200, copiado el 2026-10-22)

ContributingWebSocket Message FormatOn this pageWebSocket Message Format
Use this page as the Markdown/MDX reference for WebSocket documentation style. The examples are illustrative format samples, not public API contracts.
Visual Language​
WebSocket pages should stay mostly Markdown, with WsMessage cards for message routes and API UI components for badges, callouts, and field types.
💬Command🔔Event🔁Stream🔒Auth required🚧Not implemented
Conventions​

Use WsMessage for every documented route.
Keep badges text-first; icons and emoji are visual aids, not the only meaning.
Split command docs into Client Message, Payload Fields, Success Message, and Error Message sections.
Split event docs into a message example and Payload Fields when the payload is inline.
Use json for concrete copyable messages.
Use ts for schematic messages that contain reusable model types, such as payload: Order.
Link reusable models to Data Models instead of duplicating full schemas.
Use ApiCallout for auth requirements, restrictions, stream behavior, and implementation notes.
Do not use raw :::warning blocks unless directive rendering has been verified.

Message Type Table​
Render message markers directly in tables when explaining message types.
MarkerMeaning💬CommandClient request that expects :ok, :error, or protection error response.🔔EventOne-way server message that does not expect a response.🔁StreamEvent sequence with meta.stream and meta.revision for ordering.🔒Auth requiredMessage requires an authenticated and authorized client.🚧Not implementedRoute or behavior exists only as a planned/stubbed feature.
Command Example​
Command@wfm|cmd/example/doThingPerform an example action and return a command response.💬Command🔒Auth required
🔒Requires
Authentication
Verified account
Scope: example.scope

Client Message​
{  "route": "@wfm|cmd/example/doThing",  "id": "message-id",  "payload": {    "name": "Example",    "enabled": true  }}
Payload Fields​
FieldTypeDescriptionnamestringRequired. Display name. Max: 32 characters.enabledboolOptional. Whether the example is enabled. Default: false.
Success Message​
{  "route": "@wfm|cmd/example/doThing:ok",  "payload": {    "updated": true  },  "id": "message-id"}
Error Message​
{  "route": "@wfm|cmd/example/doThing:error",  "payload": {    "name": "app.field.tooLong"  },  "id": "message-id"}
Event Example​
Event@wfm|event/example/changedNotify clients that an example resource changed.🔔Event
{  "route": "@wfm|event/example/changed",  "payload": {    "id": "example-id",    "changedAt": "2026-06-19T00:00:00Z"  }}
Payload Fields​
FieldTypeDescriptionidstringChanged resource identifier.changedAtstringChange timestamp.
Stream Example​
Stream@wfm|event/example/stateBroadcast an ordered state update for one stream.🔔Event🔁Stream
Use stream metadata only when the backend sends meta.stream and meta.revision.
{  "route": "@wfm|event/example/state",  "payload": {    "state": "ready"  },  "meta": {    "stream": "example:example-id",    "revision": 7  }}
Meta Fields​
FieldTypeDescriptionstreamstringStream name used for ordering or deduplication.revisionnumberMonotonic revision within the stream.
Model Payload Example​
Use ts when the message body is schematic and refers to a reusable model.
Event@wfm|event/subscriptions/newOrderSend a matching newly created visible order to subscribers.🔔Event
{  route: "@wfm|event/subscriptions/newOrder",  payload: Order,}
Payload is an Order shape.
Not Implemented Example​
Command@wfm|cmd/example/futureReserved example command that is not implemented yet.🚧Not implemented
Use this pattern only when a planned or stubbed backend route needs to be mentioned. Do not document stubbed routes as active behavior.
Copyable Skeleton​
Use this skeleton for a new command route.
## Message Name<WsMessage  type="Command"  route="@wfm|cmd/domain/action"  summary="Short behavior description."  badges={[{ kind: 'neutral', icon: '💬', label: 'Command' }]}/>### Client Message```json{  "route": "@wfm|cmd/domain/action",  "id": "message-id",  "payload": {}}```### Payload Fields| Field   | Type                                       | Description        || ------- | ------------------------------------------ | ------------------ || `field` | <ApiBadge kind="neutral" label="string" /> | Field description. |### Success Message```json{  "route": "@wfm|cmd/domain/action:ok",  "id": "message-id"}```### Error Message```json{  "route": "@wfm|cmd/domain/action:error",  "payload": "app.errors.example",  "id": "message-id"}```
Do Not​

Do not document routes that are constants only; confirm they are registered.
Do not document stubbed handlers as active behavior.
Do not document fields that the backend does not implement, such as refId.
Do not render loose badge rows before route text; use WsMessage.
Do not use json for model placeholders such as payload: "Order"; use ts and link the model.
Do not duplicate reusable model schemas on WebSocket pages.
PreviousHTTP API Endpoint FormatNextwfm-localizationVisual LanguageMessage Type TableCommand ExampleEvent ExampleStream ExampleModel Payload ExampleNot Implemented ExampleCopyable SkeletonDo Not
