# Authentication | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/authentication/ (HTTP 200, copiado el 2026-10-22)

HTTP APIAuthenticationOn this pageAuthentication
Session endpoints for first-party clients. OAuth 2.0 authorization-code endpoints are documented separately in OAuth 2.0.
Sign In​
POST/auth/signinSign in with a first-party client and create a session.💔First-party only
⚠RestrictionFirst-party applications only. The client must be a registered first-party client and the request must pass Firebase App Check.
Request​
Headers​
NameTypeDescriptionContent-TypestringMust be application/json.X-Firebase-AppCheckstringFirebase App Check verification token.
Body​
{  "email": "[email protected]",  "password": "12345",  "clientId": "wfm-0000",  "deviceId": "random unique id",  "deviceName": "My cool Nokia 3310"}
Body Fields​
FieldTypeDescriptionemailstringUser email. Normalized to lowercase. Max: 128 characters.passwordstringUser password. Min: 1 character for legacy compatibility. Max: 128 characters.clientIdstringRegistered first-party client ID. Min: 6 characters. Max: 64 characters.deviceIdstringUnique device ID used to bind the session to this device. Min: 6 characters. Max: 256 characters.deviceNamestringHuman-readable device name. Defaults to Unknown. Max: 128 characters.
Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "accessToken": "...",    "refreshToken": "...",    "tokenType": "Bearer",    "expiresIn": 12345  },  "error": null}
Data Fields​
FieldTypeDescriptionaccessTokenstringJWT access token for authenticated requests.refreshTokenstringRefresh token for this session.tokenTypeBearerToken type for the Authorization header.expiresInintAccess token lifetime in seconds.
Sign Up​
POST/auth/signupRegister a new user with a first-party client and create a session.💔First-party only
⚠RestrictionFirst-party applications only. The client must be a registered first-party client and the request must pass Firebase App Check.
Request​
Headers​
NameTypeDescriptionContent-TypestringMust be application/json.X-Firebase-AppCheckstringFirebase App Check verification token.
Body​
{  "email": "[email protected]",  "password": "123456",  "passwordConfirmation": "123456",  "clientId": "wfm-0000",  "deviceId": "random unique id",  "deviceName": "My Nokia 3310",  "platform": "pc",  "locale": "ko"}
Body Fields​
FieldTypeDescriptionemailstringUser email. Normalized to lowercase. Max: 128 characters.passwordstringUser password. Min: 6 characters. Max: 128 characters.passwordConfirmationstringMust match password. Min: 6 characters. Max: 128 characters.clientIdstringRegistered first-party client ID. Min: 6 characters. Max: 64 characters.deviceIdstringUnique device ID used to bind the session to this device. Min: 6 characters. Max: 256 characters.deviceNamestringHuman-readable device name. Defaults to Unknown. Max: 128 characters.platformPlatformUser's starting platform. Must be one of the supported platforms.localeLanguagePreferred communication language.
Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "accessToken": "...",    "refreshToken": "...",    "tokenType": "Bearer",    "expiresIn": 12345  },  "error": null}
Refresh Session​
POST/auth/refreshRefresh a session using a refresh token.
This endpoint does not use the Authorization header.
ℹApp CheckFirst-party clients must include X-Firebase-AppCheck. Third-party clients do not use this header.
Request​
Headers​
NameTypeDescriptionContent-TypestringMust be application/json.X-Firebase-AppCheckstringRequired only when clientId belongs to a first-party client.
Body​
{  "grantType": "refresh_token",  "clientId": "wfm-0000",  "deviceId": "BASD001-KSADFDG",  "refreshToken": "JwtRefreshToken"}
Body Fields​
FieldTypeDescriptiongrantTyperefresh_tokenOAuth-style grant type for refresh-token flow.clientIdstringRegistered client ID. Min: 6 characters. Max: 64 characters.deviceIdstringDevice ID bound to the session. Min: 6 characters. Max: 256 characters.refreshTokenstringRefresh token for the existing session. Min: 6 characters. Max: 256 characters.
Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "accessToken": "...",    "refreshToken": "...",    "tokenType": "Bearer",    "expiresIn": 12345  },  "error": null}
Sign Out​
POST/auth/signoutTerminate the current session.🔒Auth required
The current access token and its session refresh tokens become unusable.
🔒Requires
Authentication

Request​
Headers​
NameTypeDescriptionAuthorizationstringJWT access token in the format Bearer YourJWTAccessToken.
Response​
Empty response body with status code 200.PreviousAchievementsNextDashboardSign InSign UpRefresh SessionSign Out
