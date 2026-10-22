# Data Models | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/data-models/ (HTTP 200, copiado el 2026-10-22)

Data ModelsOn this pageData Models
Reusable public JSON shapes and enum values used by the Warframe.market API.
optional/contextual👤owner/self🛡️moderator+◆first-party🔒auth required🚧unstable
ℹField FlagsEmpty Flags means the field is public and normally present for that model. optional/contextual means the field is returned only for specific item kinds, user context, endpoint shape, language/platform context, or when data exists.
Item​
Full item model with all possible fields.
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.tags[]stringItem tags.setRootoptional/contextualbooleanWhether this item is the root of a set.setPartsoptional/contextual[]stringSet member item IDs.quantityInSetoptional/contextualintNumber of items in the set.rarityoptional/contextualstringItem rarity.bulkTradableoptional/contextualbooleanWhether the item can be traded in bulk.subtypesoptional/contextual[]stringItem subtypes.maxRankoptional/contextualintMaximum rank.maxChargesoptional/contextualintMaximum charges.maxAmberStarsoptional/contextualintMaximum amber stars.maxCyanStarsoptional/contextualintMaximum cyan stars.baseEndooptional/contextualintBase endo value.endoMultiplieroptional/contextualnumberEndo multiplier.ducatsoptional/contextualintDucat value.vosforoptional/contextualintVosfor value.reqMasteryRankoptional/contextualintRequired mastery rank.vaultedoptional/contextualbooleanWhether the item is vaulted.tradingTaxoptional/contextualintTrading tax.i18noptional/contextualmap[string]ItemI18NJsonLocalized item data, keyed by language code.tradableoptional/contextualbooleanWhether the item is tradable.
ItemI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.descriptionoptional/contextualstringItem description.wikiLinkoptional/contextualstringLink to the wiki page.iconstringIcon image path.thumbstringThumbnail image path.subIconoptional/contextualstringSub-icon image path.
Riven Item​
Full riven weapon model with all possible fields. rivenType currently includes kitgun, melee, pistol, rifle, shotgun, and zaw, but new values may be added. group is used by the frontend for display grouping.
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.groupoptional/contextualstringGroup category.rivenTypeoptional/contextualstringWeapon type.dispositionnumberDisposition value.reqMasteryRankintRequired mastery rank.
RivenItemI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.wikiLinkoptional/contextualstringLink to the wiki page.iconstringIcon image path.thumbstringThumbnail image path.subIconstringSub-icon image path.
Riven Attribute​
Full riven attribute model with all possible fields.
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.groupoptional/contextualstringGroup category.prefixstringPrefix name.suffixstringSuffix name.exclusiveTooptional/contextual[]stringRiven types this attribute is exclusive to.positiveIsNegativeoptional/contextualbooleanWhether positive values are treated as negative.unitoptional/contextualstringUnit of measurement.positiveOnlyoptional/contextualbooleanWhether this attribute can only have positive values.negativeOnlyoptional/contextualbooleanWhether this attribute can only have negative values.i18noptional/contextualmap[string]RivenAttributeI18NJsonLocalized text map by language code.
RivenAttributeI18NJson​
FieldFlagsTypeDescriptionnameoptional/contextualstringAttribute effect name.iconoptional/contextualstringIcon image path.thumboptional/contextualstringThumbnail image path.
Lich Weapon​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.reqMasteryRankintRequired mastery rank.i18noptional/contextualmap[string]LichWeaponI18NJsonLocalized text map by language code.
LichWeaponI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.wikiLinkstringLink to the wiki page.iconstringIcon image path.thumbstringThumbnail image path.
Lich Ephemera​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.animationstringAnimation path.elementstringElemental type.i18noptional/contextualmap[string]LichEphemeraI18NJsonLocalized text map by language code.
LichEphemeraI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.iconstringIcon image path.thumbstringThumbnail image path.
Lich Quirk​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.groupoptional/contextualstringGroup category.i18noptional/contextualmap[string]LichQuirkI18NJsonLocalized text map by language code.
LichQuirkI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.descriptionstringQuirk description.iconstringIcon image path.thumbstringThumbnail image path.
Sister Weapon​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.reqMasteryRankintRequired mastery rank.i18noptional/contextualmap[string]SisterWeaponI18NJsonLocalized text map by language code.
SisterWeaponI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.wikiLinkstringLink to the wiki page.iconstringIcon image path.thumbstringThumbnail image path.
Sister Ephemera​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.animationstringAnimation path.elementstringElemental type.i18noptional/contextualmap[string]SisterEphemeraI18NJsonLocalized text map by language code.
SisterEphemeraI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.iconstringIcon image path.thumbstringThumbnail image path.
Sister Quirk​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.groupoptional/contextualstringGroup category.i18noptional/contextualmap[string]SisterQuirkI18NJsonLocalized text map by language code.
SisterQuirkI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.descriptionstringQuirk description.iconstringIcon image path.thumbstringThumbnail image path.
Npc​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.i18noptional/contextualmap[string]NpcI18NJsonLocalized text map by language code.
NpcI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.iconstringIcon image path.thumbstringThumbnail image path.
Location​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.factionoptional/contextualstringFaction name.minLeveloptional/contextualintMinimum level for missions.maxLeveloptional/contextualintMaximum level for missions.i18noptional/contextualmap[string]LocationI18NJsonLocalized text map by language code.
LocationI18NJson​
FieldFlagsTypeDescriptionnodeNamestringNode display name.systemNamestringSystem name.iconstringIcon image path.thumbstringThumbnail image path.
Mission​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.gameRefstringInternal Warframe game reference path.i18noptional/contextualmap[string]MissionI18NJsonLocalized text map by language code.
MissionI18NJson​
FieldFlagsTypeDescriptionnamestringDisplay name.iconstringIcon image path.thumbstringThumbnail image path.
Order​
Order without specifying the owner. Used where the owner is already known, such as a user profile or your own profile.
FieldFlagsTypeDescriptionidstringUnique identifier.typestringbuy or sell.platinumintTotal platinum currency.quantityintNumber of items.perTradeoptional/contextualintItems quantity per transaction.subtypeoptional/contextualstringSpecific subtype or category.rankoptional/contextualintRank or level of the item.chargesoptional/contextualintNumber of charges left.amberStarsoptional/contextualintCount of amber stars in a sculpture.cyanStarsoptional/contextualintCount of cyan stars in a sculpture.visiblebooleanWhether the order is publicly visible.createdAtstringCreation timestamp.updatedAtstringLast modification timestamp.itemIdoptional/contextualstringItem identifier.groupIdoptional/contextualstringUser-defined group. Default group is named all.useroptional/contextualUserShortUser who created the order.
Transaction​
Represents an order that has been fully or partially closed.
FieldFlagsTypeDescriptionidstringUnique identifier.typestringTrade type.originIdstringOriginal order identifier.platinumnumberPlatinum amount.quantityintNumber of items.createdAtstringCreation timestamp.updatedAtstringLast modification timestamp.itemoptional/contextualTxItemItem details involved in the transaction.useroptional/contextualUserShortUser involved in the transaction.
TxItem​
FieldFlagsTypeDescriptionidoptional/contextualstringItem identifier.rankoptional/contextualintRank of the item.chargesoptional/contextualintNumber of charges.subtypeoptional/contextualstringItem subtype.amberStarsoptional/contextualintCount of amber stars.cyanStarsoptional/contextualintCount of cyan stars.
UserShort​
Shortened user model returned inside orders, transactions, and other embedded user references.
FieldFlagsTypeDescriptionidstringUnique identifier.ingameNamestringIn-game name.slugstringURL-safe slug.reputationintReputation score.platformstringGaming platform.crossplaybooleanWhether the user supports cross-platform trading.localestringPreferred communication language.statusstringCurrent online status. invisible is exposed as offline.avataroptional/contextualstringAvatar image path.activityActivity or nullCurrent activity, or null when no activity is set.lastSeenstringLast seen timestamp.
User​
Public user profile.
FieldFlagsTypeDescriptionidstringUnique user identifier.roleRoleUser role.tierTierSubscription/support tier.ingameNamestringUser's in-game name.slugstringURL-safe user slug.avataroptional/contextualstringAvatar image path.backgroundoptional/contextualstringProfile background image path.aboutstringSanitized HTML profile text.reputationintUser reputation score.masteryRankintWarframe mastery rank; 0 when unset.statusStatusCurrent online status. invisible is exposed as offline for public viewers.activityActivity or nullCurrent rich activity, or null when no activity is set.lastSeenstringLast seen timestamp.platformPlatformUser's platform.crossplaybooleanWhether the user supports cross-platform trading.localeLanguageUser's locale.bannedoptional/contextualbooleanPublic ban flag.banUntiloptional/contextualstringPublic ban expiration timestamp.banMessageoptional/contextual 👤owner/self 🛡️moderator+stringBan reason, returned to the affected user or moderators+.createdAtoptional/contextual 🛡️moderator+stringAccount creation timestamp, returned to moderators+.warnedoptional/contextual 👤owner/self 🛡️moderator+booleanWarning flag, returned to affected user or moderators+.warnMessageoptional/contextual 👤owner/self 🛡️moderator+stringWarning message, returned to affected user or moderators+.warnedByoptional/contextual 👤owner/self 🛡️moderator+stringModerator/admin user ID that issued the warning.warnedAtoptional/contextual 👤owner/self 🛡️moderator+stringWarning timestamp.bannedByoptional/contextual 👤owner/self 🛡️moderator+stringModerator/admin user ID that issued the ban.bannedAtoptional/contextual 👤owner/self 🛡️moderator+stringBan timestamp.nameHistoryoptional/contextual 🛡️moderator+[]NameHistoryPrevious names, returned to moderators+ when present.uidoptional/contextual 🛡️moderator+stringPlatform-specific unique user identifier, returned to moderators+ when available.
UserPrivate​
Private self profile returned for the authenticated user.
FieldFlagsTypeDescriptionidstringUnique identifier.rolestringUser role.tierstringSubscription tier.subscriptionbooleanSubscription status.ingameNamestringIn-game name.slugstringURL-safe slug.avataroptional/contextualstringAvatar image path.backgroundoptional/contextualstringProfile background image path.aboutstringSanitized HTML profile text.aboutRawstringAbout text in raw markdown.reputationintReputation score.masteryRankintWarframe mastery rank.creditsintIn-game currency balance.lastSeenstringLast seen timestamp.platformstringGaming platform.crossplaybooleanWhether the user supports cross-platform trading.localestringPreferred communication language.themestringPreferred color scheme for UI.syncLocalebooleanSync locale across devices.syncThemebooleanSync theme across devices.verificationbooleanVerification status.checkCodestringUnique check code for the user.createdAt🛡️moderator+stringAccount creation timestamp.warnedoptional/contextual 👤owner/self 🛡️moderator+booleanWarning flag.warnMessageoptional/contextual 👤owner/self 🛡️moderator+stringWarning message.warnedByoptional/contextual 👤owner/self 🛡️moderator+stringModerator who issued the warning.bannedoptional/contextual 👤owner/self 🛡️moderator+booleanBan status.banUntiloptional/contextual 👤owner/self 🛡️moderator+stringBan expiration timestamp.banMessageoptional/contextual 👤owner/self 🛡️moderator+stringReason for the ban.bannedByoptional/contextual 👤owner/self 🛡️moderator+stringModerator who issued the ban.unreadNotificationsintCount of unread notifications.deleteInProgressoptional/contextualbooleanFlag for pending account deletion.deleteAtoptional/contextualstringScheduled deletion date.linkedAccountsobjectAccounts linked with the user's profile.hasEmailoptional/contextualbooleanWhether the user has an email address.emailoptional/contextual ◆first-partystringEmail address.
Activity​
FieldFlagsTypeDescriptiontypestringActivity type.detailsoptional/contextualstringOptional specifics about the activity.startedAtoptional/contextualstringTimestamp of the activity start.
Activity type values currently include on_mission, dojo, unknown, and an empty string.
Achievement​
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.typestringType of the achievement.secretoptional/contextualbooleanIf true, hidden from the public.reputationBonusoptional/contextualintReputation bonus for the achievement.goaloptional/contextualintGoal to achieve.i18nobjectLocalized text map by language code.stateoptional/contextualAchievementState or nullCurrent state, only present for user-specific achievements.
AchievementState​
FieldFlagsTypeDescriptionfeaturedoptional/contextualbooleanIf true, the achievement is featured.hiddenoptional/contextualbooleanIf true, hidden from the public.progressoptional/contextualint or nullCurrent progress towards the goal.completedAtoptional/contextualstringTimestamp when achieved.
DashboardShowcase​
Mobile app main screen dashboard with featured items.
FieldFlagsTypeDescriptioni18noptional/contextualobject or nullLocalized text map by language code.itemsDashboardShowcaseItem[]Featured items.
DashboardShowcaseItem​
FieldFlagsTypeDescriptionitemstringItem slug/key.backgroundstringBackground image path.bigCardbooleanWhether to render as a big card.labeloptional/contextualstringLabel text.labelPositionoptional/contextualstringLabel position.
Client​
OAuth client model.
FieldFlagsTypeDescriptionidstringUnique identifier.slugstringURL-safe slug.activeoptional/contextualbool or nullWhether the client is active.firstPartyoptional/contextualbool or nullWhether this is a first-party client.logooptional/contextualstringClient logo path.redirectUrioptional/contextualstring[]Allowed redirect URIs.scopesoptional/contextualstring[]Granted scopes.secretoptional/contextualstringClient secret.i18noptional/contextualobject or nullLocalized client info.
ClientI18N​
FieldFlagsTypeDescriptionnameoptional/contextualstringLocalized client name.descriptionoptional/contextualstringLocalized description.
Group​
User-defined order or contract group.
FieldFlagsTypeDescriptionidstringUnique identifier.userIdstringOwner user ID.kindstringorders or contracts.namestringDisplay name.
RichStatus​
Rich user status for status endpoints.
FieldFlagsTypeDescriptionstatusstringStatus string.statusUntiloptional/contextualstringStatus expiration timestamp.statusSetAtstringWhen the status was set.activityoptional/contextualActivity or nullCurrent activity.
Versions​
Version information for apps and collections.
FieldFlagsTypeDescriptionidstringUnique identifier.appsobjectApp version info.collectionsobjectCollection version hashes.updatedAtstringLast update timestamp.
VersionApps​
FieldFlagsTypeDescriptioniosstringLatest iOS version.androidstringLatest Android version.minIosstringMinimum supported iOS version.minAndroidstringMinimum supported Android version.
VersionCollections​
FieldFlagsTypeDescriptionitemsstringItems collection version hash.rivensstringRivens collection version hash.lichesstringLiches collection version hash.sistersstringSisters collection version hash.missionsstringMissions collection version hash.npcsstringNPCs collection version hash.locationsstringLocations collection version hash.
Enums And Constants​
NameValuesStatusinvisible, offline, online, ingameActivityTypeUNKNOWN, IDLE, ON_MISSION, IN_DOJO, IN_ORBITER, IN_RELAYRolenone, user, moderator, adminTiernone, bronze, silver, gold, platinum, diamondLanguageko, ru, de, fr, pt, zh-hans, zh-hant, es, it, pl, uk, tr, ja, enPlatformpc, ps4, xbox, switch, mobileScopeall, orders, contracts, chats, inventory, advanceSubPreviousOverviewNextRulesItemRiven ItemRiven AttributeLich WeaponLich EphemeraLich QuirkSister WeaponSister EphemeraSister QuirkNpcLocationMissionOrderTransactionUserShortUserUserPrivateActivityAchievementDashboardShowcaseClientGroupRichStatusVersionsEnums And Constants
