# Achievements | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/achievements/ (HTTP 200, copiado el 2026-10-22)

HTTP APIAchievementsOn this pageAchievements
Endpoints for public achievements and user achievement progress.
List Achievements​
GET/v2/achievementsGet all available achievements.🇬🇧Language aware
Secret achievements are omitted unless the requester has role admin.
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: Achievement[],  error: null,}
data is an array of Achievement models.
Get User Achievements​
GET/v2/achievements/user/{slug}Alternative/v2/achievements/userId/{userId}Get a user's achievements.🇬🇧Language aware
Anonymous users and unrelated users do not receive hidden achievements. The requested user and users with role moderator or higher can receive hidden achievements.
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the User model.userIdstringid field from the User model.
Query Parameters​
NameTypeDescriptionfeaturedpresence flagWhen present, return only achievements where state.featured is true. The value is ignored, so ?featured=false still enables the filter.
Response​
Body​
{  apiVersion: "x.x.x",  data: Achievement[],  error: null,}
data is an array of Achievement models.PreviousUsersNextAuthenticationList AchievementsGet User Achievements
