# Orders | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/orders/ (HTTP 200, copiado el 2026-10-22)

HTTP APIOrdersOn this pageOrders
Endpoints for marketplace orders.
Get Recent Orders​
GET/v2/orders/recentGet the most recent visible orders from non-banned users.🌀Platform/crossplay aware⏱1m refresh
Returns up to 500 visible orders created in the last 4h, sorted by createdAt descending. Results include only users currently online.
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order[],  error: null,}
data is an array of Order models.
Get Orders By Item​
GET/v2/orders/item/{slug}Alternative/v2/orders/itemId/{itemId}Get visible orders for an item.🌀Platform/crossplay aware
Returns visible orders from non-banned users whose lastSeen is within the last 48h, or whose lastSeen is missing. Current user status is refreshed in the response, but offline users are not removed by this endpoint.
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Item model.itemIdstringid field from the Item model.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order[],  error: null,}
data is an array of Order models.
Get Top Orders By Item​
GET/v2/orders/item/{slug}/topAlternative/v2/orders/itemId/{itemId}/topGet the top buy and sell orders for an item from online users.🌀Platform/crossplay aware⇅Custom ranking
The response contains up to 5 sell orders and up to 5 buy orders.
Sell orders are ranked from the buyer's point of view: Endo listings first, then better Endo-per-platinum ratio for Endo listings, otherwise lower platinum-per-trade first.
Buy orders are ranked from the seller's point of view: Endo listings first, then lower Endo-per-platinum ratio for Endo listings, otherwise higher platinum-per-trade first.
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Item model.itemIdstringid field from the Item model.
Query Parameters​
NameTypeDescriptionrankintExact item rank. Accepted range: 0 to item max rank. Ignored when the item has no ranks or when rankLt is provided.rankLtintMatch ranks lower than this value. Accepted range: 1 to item max rank. Takes precedence over rank.chargesintExact remaining charges. Accepted range: 0 to item max charges. Ignored when the item has no charges or when chargesLt is provided.chargesLtintMatch remaining charges lower than this value. Accepted range: 1 to item max charges. Takes precedence over charges.amberStarsintExact amber star count. Accepted range: 0 to item max amber stars. Ignored when the item has no amber stars or when amberStarsLt is provided.amberStarsLtintMatch amber star counts lower than this value. Accepted range: 1 to item max amber stars. Takes precedence over amberStars.cyanStarsintExact cyan star count. Accepted range: 0 to item max cyan stars. Ignored when the item has no cyan stars or when cyanStarsLt is provided.cyanStarsLtintMatch cyan star counts lower than this value. Accepted range: 1 to item max cyan stars. Takes precedence over cyanStars.subtypestringExact item subtype. Must be one of the subtypes supported by the item. Ignored when the item has no subtypes.
Response​
Body​
{  apiVersion: "x.x.x",  data: {    sell: Order[],    buy: Order[],  },  error: null,}
Data Fields​
FieldTypeDescriptionsellOrder[]Up to 5 sell orders from online users, sorted from the buyer's point of view.buyOrder[]Up to 5 buy orders from online users, sorted from the seller's point of view.
Get Orders By User​
GET/v2/orders/user/{slug}Alternative/v2/orders/userId/{userId}Get orders from a specific user.
Anonymous users and unrelated users receive only visible orders. The requested user and users with role moderator or higher receive visible and hidden orders.
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the User model.userIdstringid field from the User model.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order[],  error: null,}
data is an array of compact Order models.
Get My Orders​
GET/v2/orders/myGet all orders associated with the authenticated user.🔒Auth required
Returns visible and hidden orders.
🔒Requires
Authentication

Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order[],  error: null,}
data is an array of compact Order models.
Get Order​
GET/v2/order/{id}Get one order by ID.
Request​
URL Parameters​
NameTypeDescriptionidstringid field from the Order model.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order,  error: null,}
data is a compact Order model.
Create Order​
POST/v2/orderCreate a new order.🔒Auth required
🔒Requires
Authentication
Verified account
User must not be banned

Request​
Body​
{  "itemId": "54aae292e7798909064f1575",  "type": "sell",  "platinum": 38,  "quantity": 12,  "visible": true,  "perTrade": 6,  "rank": 5,  "charges": 3,  "subtype": "blueprint",  "amberStars": 3,  "cyanStars": 3}
Body Fields​
FieldTypeDescriptionitemIdstringRequired. Item ID. Item must exist and be tradable.typesell or buyRequired. Order type.platinumintRequired. Price in platinum. Min: 1. Max: 900000.quantityintRequired. Order quantity. Min: 1. Max: 9999.visibleboolWhether the order is visible. Defaults to false when omitted.perTradeintRequired for bulk-tradable items, forbidden otherwise. Min: 1. Max: 6. Must divide quantity.rankintRequired when the item supports ranks, forbidden otherwise. Min: 0. Max: item max rank.chargesintRequired when the item supports charges, forbidden otherwise. Min: 0. Max: item max charges.subtypestringRequired when the item has subtypes, forbidden otherwise. Must be one of the item's subtypes.amberStarsintRequired when the item supports amber stars, forbidden otherwise. Min: 0. Max: item max amber stars.cyanStarsintRequired when the item supports cyan stars, forbidden otherwise. Min: 0. Max: item max cyan stars.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order,  error: null,}
data is a compact Order model.
Update Order​
PATCH/v2/order/{id}Patch an existing order.🔒Auth required
🔒Requires
Authentication
Verified account
Order owner or role admin and higher

Request​
URL Parameters​
NameTypeDescriptionidstringid field from the Order model.
Body​
{  "platinum": 10,  "quantity": 12,  "perTrade": 3,  "rank": 1,  "charges": 2,  "amberStars": 2,  "cyanStars": 2,  "subtype": "blueprint",  "visible": false}
Body Fields​
FieldTypeDescriptionplatinumintPrice in platinum. Min: 1. Max: 900000.quantityintOrder quantity. Min: 1. Max: 9999.visibleboolWhether the order is visible.perTradeintAllowed only for bulk-tradable items. Min: 1. Max: 6. Must divide the final quantity.rankintAllowed only when the item supports ranks. Min: 0. Max: item max rank.chargesintAllowed only when the item supports charges. Min: 0. Max: item max charges.subtypestringAllowed only when the item has subtypes. Must be one of the item's subtypes.amberStarsintAllowed only when the item supports amber stars. Min: 0. Max: item max amber stars.cyanStarsintAllowed only when the item supports cyan stars. Min: 0. Max: item max cyan stars.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order,  error: null,}
Delete Order​
DELETE/v2/order/{id}Delete an order.🔒Auth required✕Deletes data
🔒Requires
Authentication
Verified account
Order owner or role admin and higher

Request​
URL Parameters​
NameTypeDescriptionidstringid field from the Order model.
Response​
Body​
{  apiVersion: "x.x.x",  data: Order,  error: null,}
Close Order​
POST/v2/order/{id}/closeClose a portion or all of an existing order.🔒Auth required
If quantity is greater than the remaining order quantity, the service closes the remaining quantity. A full close deletes the order; a partial close updates the remaining quantity.
🔒Requires
Authentication
Verified account
User must not be banned
Order owner or role admin and higher

Request​
URL Parameters​
NameTypeDescriptionidstringid field from the Order model.
Body​
{  "quantity": 12}
Body Fields​
FieldTypeDescriptionquantityintUnits to close. Min: 1. Max: 9999. Must be divisible by the order's perTrade.
Response​
Body​
{  apiVersion: "x.x.x",  data: Transaction,  error: null,}
data is a compact Transaction model.
Update Order Group Visibility​
PATCH/v2/orders/group/{id}Update visibility for a virtual order group.🔒Auth required
🔒Requires
Authentication
Verified account

Request​
URL Parameters​
NameTypeDescriptionidstringGroup ID. Currently supported values: all, ungrouped.
Body​
{  "visible": false,  "type": "sell"}
Body Fields​
FieldTypeDescriptionvisibleboolVisibility state to apply. Defaults to false when omitted.typesell or buyRestrict the update to one order type. Omit to update both types.
Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "updated": 13  },  "error": null}
Data Fields​
FieldTypeDescriptionupdatedintNumber of orders updated.PreviousManifests And CollectionsNextGroupsGet Recent OrdersGet Orders By ItemGet Top Orders By ItemGet Orders By UserGet My OrdersGet OrderCreate OrderUpdate OrderDelete OrderClose OrderUpdate Order Group Visibility
