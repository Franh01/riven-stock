# Status And Activity | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/websockets/status-and-activity/ (HTTP 200, copiado el 2026-10-22)

WebSocketsStatus And ActivityOn this pageStatus And Activity
Commands and events for user online status and rich activity.
Set Status And Activity​
Command@wfm|cmd/status/setUpdate the authenticated user's status and activity.💬Command🔒Auth required
🔒Requires
Authentication
Verified account
User must not be banned

The server is the source of truth for status. A client should wait for the current @wfm|event/status/set event after sign-in before deciding whether to send status updates.
Client Message​
{  "route": "@wfm|cmd/status/set",  "id": "message-id",  "payload": {    "status": "ingame",    "duration": 1800,    "activity": {      "type": "ON_MISSION",      "details": "Plains of Eidolon - Bounty Tier 3",      "startedAt": 1745424871    }  }}
Payload Fields​
FieldTypeDescriptionstatusstringRequired. One of online, ingame, invisible.durationint or nullOptional. Duration in seconds. Min: 60. Max: 21600 (6h). Send null to remove an existing duration.activityobject or nullOptional. Full activity object. Send null to clear existing activity. See Activity Fields below.
Activity Fields​
When activity is an object, it replaces the whole current activity. Send all fields needed for the new activity state.
{  "type": "ON_MISSION",  "details": "Plains of Eidolon - Bounty Tier 3",  "startedAt": 1745424871}
FieldTypeDescriptiontypestringRequired. One of UNKNOWN, IDLE, ON_MISSION, IN_DOJO, IN_ORBITER, IN_RELAY.detailsstringOptional. Free-form activity details. Max: 64 characters.startedAtintRequired. Unix timestamp in seconds. Must be between one day ago and now.
Success Message​
{  "route": "@wfm|cmd/status/set:ok",  "payload": {    "status": "ingame",    "statusSetAt": "2017-01-16T23:00:00Z",    "statusUntil": "2017-01-17T00:00:00Z",    "activity": {      "type": "ON_MISSION",      "details": "Plains of Eidolon - Bounty Tier 3",      "startedAt": "2017-01-16T23:00:00Z"    }  },  "id": "message-id",  "meta": {    "stream": "status:user-id",    "revision": 1  }}
Payload is a RichStatus shape.
Error Message​
{  "route": "@wfm|cmd/status/set:error",  "payload": {    "activity.startedAt": "app.field.tooSmall"  },  "id": "message-id"}
Duration Behavior​

Without an existing status and without duration, the status remains active while the user stays connected.
With duration, the status remains active for that duration.
If the user disconnects before the duration expires, the status can be restored briefly on reconnect.
If a duration expires while the user is still connected, the server sets status to invisible and broadcasts an update.
Sending duration: null removes an existing duration.

Activity Behavior​
activity is replaced as a whole. To update one activity field, send the complete activity object. Send activity: null to clear the current activity.
Status And Activity Update​
Stream@wfm|event/status/setBroadcast the current committed status and activity state.🔔Event🔁Stream
The server sends this event after sign-in, after one of the user's connected clients changes status or activity, and when a timed status expires.
{  "route": "@wfm|event/status/set",  "payload": {    "status": "ingame",    "statusSetAt": "2017-01-16T23:00:00Z",    "statusUntil": "2017-01-17T00:00:00Z",    "activity": {      "type": "ON_MISSION",      "details": "Plains of Eidolon - Bounty Tier 3",      "startedAt": "2017-01-16T23:00:00Z"    }  },  "meta": {    "stream": "status:user-id",    "revision": 1  }}
Payload is a RichStatus shape.PreviousAuthentication And Account EventsNextSubscriptionsSet Status And ActivityStatus And Activity Update
