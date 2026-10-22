# Reports | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/websockets/reports/ (HTTP 200, copiado el 2026-10-22)

WebSocketsReportsOn this pageReports
Server-generated reporting events.
Online Count​
Event@wfm|event/reports/onlineReport current WebSocket connection and authorized-user counts.🔔Event
The server sends this event on connect and broadcasts it about once every 30s.
{  "route": "@wfm|event/reports/online",  "payload": {    "connections": 1,    "authorizedUsers": 1  }}
Payload Fields​
FieldTypeDescriptionconnectionsintCurrent WebSocket connection count.authorizedUsersintCurrent count of authorized users.PreviousOverviewNextAuthentication And Account EventsOnline Count
