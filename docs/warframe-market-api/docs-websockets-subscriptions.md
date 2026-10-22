# Subscriptions | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/websockets/subscriptions/ (HTTP 200, copiado el 2026-10-22)

WebSocketsSubscriptionsOn this pageSubscriptions
Commands and events for realtime marketplace subscriptions.
Subscribe To New Orders​
Command@wfm|cmd/subscribe/newOrdersSubscribe to a live feed of newly posted visible orders from online users.💬Command
Client Message​
{  "route": "@wfm|cmd/subscribe/newOrders",  "id": "message-id",  "payload": {    "platform": "pc",    "crossplay": true  }}
Payload Fields​
FieldTypeDescriptionplatformPlatformOptional. One of pc, ps4, xbox, switch, mobile. Omit to subscribe to all platforms.crossplayboolOptional. Defaults to true. If platform is switch, the server forces crossplay to false.
You can have multiple active subscriptions at the same time, such as one for pc and one for xbox.
Success Message​
{  "route": "@wfm|cmd/subscribe/newOrders:ok",  "id": "message-id"}
Error Message​
{  "route": "@wfm|cmd/subscribe/newOrders:error",  "payload": "app.errors.alreadySubscribed",  "id": "message-id"}
Unsubscribe From New Orders​
Command@wfm|cmd/unsubscribe/newOrdersUnsubscribe from a new-order subscription.💬Command
You must send the same payload used for subscription. This is required because a client can have multiple subscriptions active simultaneously.
Client Message​
{  "route": "@wfm|cmd/unsubscribe/newOrders",  "id": "message-id",  "payload": {    "platform": "pc",    "crossplay": true  }}
Payload Fields​
FieldTypeDescriptionplatformPlatformOptional. Must match the subscription payload. Omit only to unsubscribe from an all-platform subscription.crossplayboolOptional. Defaults to true. If platform is switch, the server forces crossplay to false.
Success Message​
{  "route": "@wfm|cmd/unsubscribe/newOrders:ok",  "id": "message-id"}
Error Message​
{  "route": "@wfm|cmd/unsubscribe/newOrders:error",  "payload": "app.errors.notSubscribed",  "id": "message-id"}
New Order Event​
Event@wfm|event/subscriptions/newOrderSend a matching newly created visible order to subscribers.🔔Event
Sent to matching new-order subscriptions when a visible order from a non-offline user is created.
{  route: "@wfm|event/subscriptions/newOrder",  payload: Order,}
Payload is an Order shape.
Not Implemented Yet​
The backend currently contains stubs for item and profile order subscriptions, but those commands are not registered as public WebSocket routes. Do not rely on them until they are documented as active.PreviousStatus And ActivityNextOverviewSubscribe To New OrdersUnsubscribe From New OrdersNew Order EventNot Implemented Yet
