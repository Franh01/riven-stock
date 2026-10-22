# HTTP API Endpoint Format | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/contributing/http-api-endpoint-format/ (HTTP 200, copiado el 2026-10-22)

ContributingHTTP API Endpoint FormatOn this pageHTTP API Endpoint Format
Use this page as the Markdown/MDX reference for HTTP endpoint documentation style. The examples are illustrative format samples, not public API contracts.
Visual Language​
Endpoint pages should stay mostly Markdown, with ApiEndpoint cards for routes and API UI components for badges, callouts, and field types.
🔒Auth required🇬🇧Language aware🌀Platform/crossplay aware⏱Cached◆First-party only✕Deletes data
Conventions​

Use ApiEndpoint for every documented route behavior.
Put the canonical route in path and route variants in aliases.
Do not include the HTTP method in aliases.
Keep badges text-first; icons and emoji are visual aids, not the only meaning.
Split each endpoint into Request and Response sections.
Use #### headings inside those sections for URL parameters, query parameters, headers, body, fields, constraints, errors, and response fields.
Use json for concrete copyable payloads.
Use ts for schematic responses that contain reusable model types, such as data: Order[].
Link reusable models to Data Models instead of duplicating full schemas.
Use ApiCallout for auth requirements, restrictions, response context, and implementation notes.
Do not use raw :::warning blocks unless directive rendering has been verified.

Badge Table​
Render markers directly in tables when explaining endpoint behavior.
MarkerMeaning🔒Auth requiredEndpoint requires authentication or returns auth-only data.🇬🇧Language awareResponse changes with the Language header.🌀Platform/crossplay awareResponse changes with Platform or Crossplay headers.⏱CachedResponse has documented cache or freshness behavior.◆First-party onlyEndpoint is restricted to first-party clients or special access.✕Deletes dataEndpoint deletes data or performs destructive behavior.
JSON Endpoint Example​
PATCH/v2/example/{id}Alternative/v2/exampleSlug/{slug}Update an example resource and return the updated model.🔒Auth required🌀Platform/crossplay aware🇬🇧Language aware⏱60s cache
🔒Requires
Authentication
Scope: examples.update

ℹResponse ContextResponse data depends on the Platform, Crossplay, and Language headers. Responses are cached for 60s.
Request​
URL Parameters​
NameTypeDescriptionidstringid field from the linked model.slugstringAlternative slug field from the linked model.
Query Parameters​
NameTypeDescriptionlimitintOptional. Maximum number of records. Default: 50. Min: 1. Max: 100.cursorstringOptional. Pagination cursor from a previous response.
Headers​
NameTypeDescriptionAuthorizationstringJWT access token in the format Bearer YourJWTAccessToken.LanguageLanguageTranslation language. Default: en.PlatformPlatformPlatform context. Default: pc.CrossplayboolCrossplay context. Default depends on endpoint behavior.
Body​
{  "name": "Example",  "visible": true,  "note": "Optional note"}
Body Fields​
FieldTypeDescriptionnamestringRequired. Display name. Min: 3. Max: 32.visibleboolOptional. Whether the resource should be visible.notestring or nullOptional. Owner-only note. Send null to clear it.
Constraints​

name must be unique for the authenticated user.
limit is ignored when cursor is present.

Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "id": "example-id",    "name": "Example",    "visible": true,    "note": "Optional note"  },  "error": null}
Data Fields​
FieldAccessTypeDescriptionidstringUnique example identifier.namestringDisplay name.visibleboolWhether the resource is visible.note👤ownerstring or nullOwner-only note.
Model Response Example​
Use ts when the response body is schematic and refers to reusable models.
GET/v2/examplesGet a list of example resources.🇬🇧Language aware
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: Example[],  error: null,}
data is an array of linked reusable model shapes.
Multipart Endpoint Example​
POST/v2/example/{id}/imageUpload an image for an example resource.🔒Auth required◆First-party only
⚠RestrictionFirst-party applications only.
Request​
URL Parameters​
NameTypeDescriptionidstringid field from the linked model.
Body​
Content-Type: multipart/form-data
form-data; name="image"; filename="example.png"
Body Fields​
FieldTypeDescriptionimagefileImage file to upload.
Constraints​

Accepts image formats: .png, .jpg, .jpeg, .webp, .gif, .bmp, .avif.
Maximum upload size is 5 MiB.
Image is resized to 256x256 pixels, focusing on the center of the image.

Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "id": "example-id",    "imageUrl": "https://example.com/example.png"  },  "error": null}
Empty Response Example​
DELETE/v2/example/{id}Delete an example resource.🔒Auth required✕Deletes data
Request​
URL Parameters​
NameTypeDescriptionidstringid field from the linked model.
Response​
✓Empty ResponseEmpty response body with status code 200.
Copyable Skeleton​
Use this skeleton for a new endpoint.
## Endpoint Name<ApiEndpoint  method="GET"  path="/v2/example/{id}"  aliases={['/v2/exampleSlug/{slug}']}  summary="Short behavior description."  badges={[{ kind: 'auth', icon: '🔒', label: 'Auth required' }]}/><ApiCallout kind="warning" icon="🔒" title="Requires">- Authentication</ApiCallout>### Request#### URL Parameters| Name | Type                                       | Description            || ---- | ------------------------------------------ | ---------------------- || `id` | <ApiBadge kind="neutral" label="string" /> | Parameter description. |#### Query Parameters| Name    | Type                                    | Description              || ------- | --------------------------------------- | ------------------------ || `limit` | <ApiBadge kind="neutral" label="int" /> | Optional. Default: `50`. |#### Body```json{  "field": "value"}```#### Body Fields| Field   | Type                                       | Description        || ------- | ------------------------------------------ | ------------------ || `field` | <ApiBadge kind="neutral" label="string" /> | Field description. |### Response#### Body```ts{  apiVersion: "x.x.x",  data: Example,  error: null,}```
Do Not​

Do not document routes that are not implemented.
Do not include HTTP methods in aliases.
Do not render loose badge rows before route text; use ApiEndpoint.
Do not use json for reusable model placeholders such as "data": "Order" or "data": ["Order"]; use ts and link the model.
Do not duplicate reusable model schemas on endpoint pages.
Do not create nested custom containers around every subsection.
Do not use old Notion-only color spans.
PreviousDocumentation StyleNextWebSocket Message FormatVisual LanguageBadge TableJSON Endpoint ExampleModel Response ExampleMultipart Endpoint ExampleEmpty Response ExampleCopyable SkeletonDo Not
