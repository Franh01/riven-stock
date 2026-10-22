# wfm-localization | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/contributing/wfm-localization/ (HTTP 200, copiado el 2026-10-22)

ContributingRepositorieswfm-localizationOn this pagewfm-localization
GitHub Repository
wfm-localization contains the interface translations used by Warframe.market. If you want to improve the wording users see in menus, buttons, forms, warnings, filters, settings, and other UI text, this is the repository to edit.
This repository is for application text. Item names, item descriptions, Riven attributes, Lich entities, and other game-data translations usually belong in wfm-items instead.
Good Contributions​

Add a missing language by creating translation files from the English source.
Fill missing keys in an existing language.
Fix mistranslations, awkward wording, typos, or inconsistent terminology.
Improve marketplace-specific terminology so it matches how Warframe players actually talk in that language.
Translate miscellaneous UI strings such as rarity labels and generated text templates.
Keep existing translations up to date when English strings change.

Small, focused pull requests are easier to review than very large rewrites. If you are changing many translations at once, group them by language or topic.
Repository Layout​
The exact layout may change, but the important areas are:
AreaPurposelocales/Main UI translation files.misc/Additional translation files for labels, templates, and generated UI text.en.jsonEnglish source text and the best template for new languages.overwolf/Legacy/special integration files. Do not edit unless maintainers ask you to.
Translation Rules​
Only translate values. Do not change keys.
{  "settings.language": "Language"}
In this example, translate Language, but do not change settings.language.
Placeholders in curly braces usually must stay unchanged:
{itemName}{count}{platform}
If a string uses ICU select syntax, keep the variable and option names intact, but translate the user-visible text inside option blocks.
{platform, select, pc {} xbox {| Xbox } other {}}
In that example, translate text such as Xbox only if the language requires it. Do not rename platform, pc, xbox, or other.
How To Contribute With Git​

Fork the repository.
Create a branch for your language or topic.
Edit the relevant files in locales/ or misc/.
Keep JSON valid.
Submit a pull request with a short explanation of what you changed.

Useful pull request descriptions mention:

Language code.
Whether this is a new translation or an update.
Whether you are a native/fluent speaker or using another source.
Any terms that may need maintainer review.

How To Contribute Without Git​
If you are not comfortable with GitHub:

Open the repository on GitHub.
Download the repository as a ZIP file.
Edit or create translation files locally.
Send the changed files to maintainers through the Warframe.market Discord.

This is slower than a pull request, but translation contributions are still welcome.
Review Expectations​
Maintainers mostly check that:

JSON files are valid.
Keys were not renamed or deleted accidentally.
Placeholders were preserved.
The contribution belongs in wfm-localization rather than wfm-items.
The translation does not include jokes, machine-generated nonsense, or unrelated rewrites.

We may not be able to verify every language ourselves. Community review from native or fluent speakers is very helpful.
Avoid​

Do not translate JSON keys.
Do not remove placeholders like {itemName}.
Do not edit overwolf/ files unless requested.
Do not move item or game-data translations into this repository.
Do not submit unreviewed machine translation dumps as final translations.
Do not mix many unrelated languages in one large pull request unless there is a good reason.
PreviousWebSocket Message FormatNextwfm-itemsGood ContributionsRepository LayoutTranslation RulesHow To Contribute With GitHow To Contribute Without GitReview ExpectationsAvoid
