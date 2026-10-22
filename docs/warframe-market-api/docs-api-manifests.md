# Manifests And Collections | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/api/manifests/ (HTTP 200, copiado el 2026-10-22)

HTTP APIManifests And CollectionsOn this pageManifests And Collections
Endpoints for version metadata and public collection manifests.
Get Versions​
GET/v2/versionsGet current server, app, and collection versions.
Clients can poll this endpoint to detect when local cached collections should be refreshed.
Request​
URL Parameters​
None.
Response​
Body​
{  "apiVersion": "x.x.x",  "data": {    "apps": {      "ios": "x.x.x",      "android": "x.x.x",      "minIos": "x.x.x",      "minAndroid": "x.x.x"    },    "collections": {      "items": "base64",      "rivens": "base64",      "liches": "base64",      "sisters": "base64",      "missions": "base64",      "npcs": "base64",      "locations": "base64"    },    "updatedAt": "2021-05-21T14:59:02Z"  },  "error": null}
Data Fields​
FieldTypeDescriptionappsVersionAppsCurrent and minimum supported mobile app versions.collectionsVersionCollectionsCollection version hashes.updatedAtstringLast version update timestamp.
See Versions.
List Items​
GET/v2/itemsGet all tradable items.🇬🇧Language aware
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: Item[],  error: null,}
data is an array of Item models.
Get Item​
GET/v2/item/{slug}Alternative/v2/itemId/{itemId}Get full information about one item.🇬🇧Language aware
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Item model.itemIdstringid field from the Item model.
Response​
Body​
{  apiVersion: "x.x.x",  data: Item,  error: null,}
data is an Item model.
Get Item Set​
GET/v2/item/{slug}/setAlternative/v2/itemId/{itemId}/setGet the requested item and related set items.🇬🇧Language aware
If the requested item is not part of a set, the response contains only that item. If the item is part of a set or is the set root, the response contains all items in that set.
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Item model.itemIdstringid field from the Item model.
Response​
Body​
{  apiVersion: "x.x.x",  data: {    id: "54a73e65e779893a797fff72",    items: Item[],  },  error: null,}
Data Fields​
FieldTypeDescriptionidstringID of the requested item.itemsItem[]Items in the set, or only the requested item when it is not part of a set.
List Riven Weapons​
GET/v2/riven/weaponsGet all tradable riven weapons.🇬🇧Language aware
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: RivenItem[],  error: null,}
data is an array of Riven Item models.
Get Riven Weapon​
GET/v2/riven/weapon/{slug}Get full information about one riven weapon.🇬🇧Language aware
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Riven Item model.
Response​
Body​
{  apiVersion: "x.x.x",  data: RivenItem,  error: null,}
data is a Riven Item model.
List Riven Attributes​
GET/v2/riven/attributesGet all riven weapon attributes.🇬🇧Language aware
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: RivenAttribute[],  error: null,}
data is an array of Riven Attribute models.
List Lich Weapons​
GET/v2/lich/weaponsGet all tradable lich weapons.🇬🇧Language aware
Request​
URL Parameters​
None.
Response​
Body​
{  apiVersion: "x.x.x",  data: LichWeapon[],  error: null,}
data is an array of Lich Weapon models.
Get Lich Weapon​
GET/v2/lich/weapon/{slug}Get full information about one lich weapon.🇬🇧Language aware
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Lich Weapon model.
Response​
Body​
{  apiVersion: "x.x.x",  data: LichWeapon,  error: null,}
data is a Lich Weapon model.
List Lich Ephemeras​
GET/v2/lich/ephemerasGet all tradable lich ephemeras.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: LichEphemera[],  error: null,}
data is an array of Lich Ephemera models.
List Lich Quirks​
GET/v2/lich/quirksGet all tradable lich quirks.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: LichQuirk[],  error: null,}
data is an array of Lich Quirk models.
List Sister Weapons​
GET/v2/sister/weaponsGet all tradable sister weapons.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: SisterWeapon[],  error: null,}
data is an array of Sister Weapon models.
Get Sister Weapon​
GET/v2/sister/weapon/{slug}Get full information about one sister weapon.🇬🇧Language aware
Request​
URL Parameters​
NameTypeDescriptionslugstringslug field from the Sister Weapon model.
Response​
Body​
{  apiVersion: "x.x.x",  data: SisterWeapon,  error: null,}
data is a Sister Weapon model.
List Sister Ephemeras​
GET/v2/sister/ephemerasGet all tradable sister ephemeras.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: SisterEphemera[],  error: null,}
data is an array of Sister Ephemera models.
List Sister Quirks​
GET/v2/sister/quirksGet all tradable sister quirks.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: SisterQuirk[],  error: null,}
data is an array of Sister Quirk models.
List Locations​
GET/v2/locationsGet all known locations.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: Location[],  error: null,}
data is an array of Location models.
List NPCs​
GET/v2/npcsGet all known NPCs.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: Npc[],  error: null,}
data is an array of Npc models.
List Missions​
GET/v2/missionsGet all known missions.🇬🇧Language aware
Response​
Body​
{  apiVersion: "x.x.x",  data: Mission[],  error: null,}
data is an array of Mission models.PreviousOverviewNextOrdersGet VersionsList ItemsGet ItemGet Item SetList Riven WeaponsGet Riven WeaponList Riven AttributesList Lich WeaponsGet Lich WeaponList Lich EphemerasList Lich QuirksList Sister WeaponsGet Sister WeaponList Sister EphemerasList Sister QuirksList LocationsList NPCsList Missions
