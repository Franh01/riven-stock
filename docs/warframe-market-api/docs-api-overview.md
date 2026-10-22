# Overview | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/overview/ (HTTP 200, copiado el 2026-10-22)

HTTP APIOverviewOn this pageOverview
Warframe.market exposes HTTP APIs for marketplace data, user-facing actions, and integration workflows.
Version​
This documentation describes API version v0.25.0.
Base URLs​
ResourceBase URLProduction APIhttps://api.warframe.market/v2/Static assetshttps://warframe.market/static/assets/
Some response fields are asset paths, such as item icons, user avatars, or profile backgrounds. Resolve those paths relative to the static assets base URL.
Rate Limits​
The current public limit is 3 requests per second.
♿Protection LimitsCloudflare may return 429 when request rate limits are exceeded. Too many concurrent connections from one IP address may return 509.
Global Headers​
These headers apply only to endpoints whose response depends on localization, platform, or crossplay context.
Language​
Use Language: {lang} to request localized i18n data in addition to English.
Supported values: ko, ru, de, fr, pt, zh-hans, zh-hant, es, it, pl, uk, tr, ja, en.
Default: en.
Language: ko
Platform​
Use Platform: {platform} to request platform-specific marketplace data.
Supported values: pc, ps4, xbox, switch, mobile.
Default: pc.
Platform: pc
Crossplay​
Use Crossplay: true to include crossplay-compatible orders from other platforms when the endpoint supports crossplay filtering.
Default: false.
Platform: pcCrossplay: true
Response Envelope​
Most JSON endpoints use this response envelope:
{  "apiVersion": "x.x.x",  "data": {},  "error": null}
FieldTypeDescriptionapiVersionstringSemVer-compatible API server version.dataobject, array, or nullResponse payload for successful requests.errorobject or nullError payload for handled errors.
Errors​
Handled Errors​
Handled errors use the response envelope with data: null.
{  "apiVersion": "x.x.x",  "data": null,  "error": {    "request": ["app.errors.unauthorized"],    "inputs": {      "platinum": "app.field.tooSmall"    }  }}
FieldTypeDescriptionrequest[]stringGeneral request-level errors, such as app.errors.unauthorized or app.errors.forbidden.inputsmap[string]stringField-level errors for request bodies, query parameters, or multipart form fields.
Unhandled Errors​
Unhandled critical errors return a 5xx status without a documented JSON body.
Endpoint Markers​
Endpoint pages use text labels with icons for quick scanning.
🔜In development🚧Unstable♿Rate limited🔒Auth required💔First-party only🌀Platform/crossplay aware🇬🇧Language aware🚫Deprecated
OAuth tokens obtained from the v1 API currently have scope all. That means v1-authenticated clients can ignore endpoint scope requirements for now. OAuth 2.0 will replace the v1 login flow in the future.PreviousIntroductionNextManifests And CollectionsVersionBase URLsRate LimitsGlobal HeadersResponse EnvelopeErrorsEndpoint Markers
