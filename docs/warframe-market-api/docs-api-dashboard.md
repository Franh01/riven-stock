# Dashboard | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/dashboard/ (HTTP 200, copiado el 2026-10-22)

HTTP APIDashboardOn this pageDashboard
Endpoints for dashboard content used by Warframe.market clients.
Get Dashboard Showcase​
GET/v2/dashboard/showcaseGet mobile app main screen dashboard content with featured items.🇬🇧Language aware
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: DashboardShowcase,  error: null,}
data is a DashboardShowcase model.PreviousAuthenticationNextOverviewGet Dashboard Showcase
