# Users | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/users/ (HTTP 200, copiado el 2026-10-22)

HTTP APIUsersOn this pageUsers
Endpoints for authenticated user data, public profiles, and profile media uploads.
Get Me​
GET/v2/meGet information about the authenticated user.🔒Auth required
🔒Requires
Authentication

Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: UserPrivate,  error: null,}
data is a UserPrivate model.
Update Me​
PATCH/v2/meUpdate the authenticated user's profile preferences.🔒Auth required
🔒Requires
Authentication

Request​
Body​
{  "about": "something",  "platform": "mobile",  "crossplay": true,  "locale": "pt",  "theme": "light",  "syncLocale": true,  "syncTheme": true}
Body Fields​
FieldTypeDescriptionaboutstringProfile description in Markdown. Max: 300 characters. Returned as about HTML and aboutRaw Markdown.platformPlatformMain platform the user plays on.crossplayboolWhether crossplay is enabled for the user's Warframe account. Cannot be true when the effective platform is switch.localeLanguageUI locale and preferred communication language.themelight, dark, or systemUI theme preference.syncLocaleboolWhether locale should sync across devices.syncThemeboolWhether theme should sync across devices.
Constraints​

Omitted or null fields are ignored.
If platform is set to switch and crossplay is omitted, crossplay is set to false.
If crossplay is true while the effective platform is switch, the request is rejected.

Response​
Body​
{  apiVersion: "x.x.x",  data: UserPrivate,  error: null,}
Upload Avatar​
POST/v2/me/avatarUpdate the authenticated user's avatar.🔒Auth required☁File upload
The uploaded image is center-cropped to the target aspect ratio, resized to 256x256 pixels, encoded as WebP, and stored as the new avatar.
Request​
Body​
Content-Type: multipart/form-data
form-data; name="avatar"; filename="whatever.png"
Body Fields​
FieldTypeDescriptionavatarfileImage file to upload as the new avatar.
Constraints​

Accepts image formats: .png, .jpg, .jpeg, .webp, .gif, .bmp, .avif.
Maximum upload size is 5 MiB.

Response​
Body​
{  apiVersion: "x.x.x",  data: UserPrivate,  error: null,}
Upload Background​
POST/v2/me/backgroundUpdate the authenticated user's profile background.🔒Auth required◆Silver tier+☁File upload
ℹSubscription RequirementRequires the user to have at least a silver subscription tier.
The uploaded image is center-cropped to the target aspect ratio, resized to 1920x820 pixels, encoded as WebP, and stored as the new background.
Request​
Body​
Content-Type: multipart/form-data
form-data; name="background"; filename="whatever.png"
Body Fields​
FieldTypeDescriptionbackgroundfileImage file to upload as the new background.
Constraints​

Accepts image formats: .png, .jpg, .jpeg, .webp, .gif, .bmp, .avif.
Maximum upload size is 8 MiB.

Response​
Body​
{  apiVersion: "x.x.x",  data: UserPrivate,  error: null,}
Get User​
GET/v2/user/{slug}Alternative/v2/userId/{userId}Get public information about a user.
Users with role moderator or higher may receive moderation fields described in the User model.
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the User model.userIdstringid field from the User model.
Response​
Body​
{  apiVersion: "x.x.x",  data: User,  error: null,}
data is a User model.PreviousGroupsNextAchievementsGet MeUpdate MeUpload AvatarUpload BackgroundGet User
