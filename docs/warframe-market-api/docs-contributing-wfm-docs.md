# wfm-docs | Warframe.market Docs

Fuente: https://docs.warframe.market/docs/contributing/wfm-docs/ (HTTP 200, copiado el 2026-10-22)

ContributingRepositorieswfm-docsOn this pagewfm-docs
GitHub Repository
wfm-docs is the public documentation site for Warframe.market. It documents the HTTP API, WebSocket API, OAuth 2.0 plans, shared data models, marketplace rules, and contributor guidance. Built with Docusaurus, React, TypeScript, and Yarn 4.
This is the repository you are reading right now.
Good Contributions​

Fix grammar, typos, or awkward wording in existing documentation.
Improve formatting, broken links, or outdated examples.
Add missing documentation for new API endpoints, WebSocket events, or data model fields.
Add new documentation pages and register them in sidebars.ts.
Improve the contributor guides or documentation style rules.
Translate docs into new languages via Docusaurus i18n.

Small, focused pull requests are easier to review than large rewrites.
Before You Start​
You should be comfortable with at least some of:

Markdown
Docusaurus
TypeScript
Yarn

Read the Documentation Style guide before making changes.
Requirements​

Node.js 20 or newer.
Yarn 4.14 or newer.
Corepack, recommended for using the Yarn version declared in package.json.

If Yarn 4 is not already available, enable Corepack first:
corepack enable
Running Locally​
Install dependencies:
yarn install
Start the local docs site:
yarn start
This starts Docusaurus on localhost:3000 and opens it in your browser.
Internal Warframe.market developers who run the full local Docker stack with Nginx proxying should use:
yarn start:wfm
This starts Docusaurus on 0.0.0.0:3001 and opens http://docs.warframe.test/docs/intro when the server is ready.
Build the static production site:
yarn build
Repository Layout​
AreaPurposedocs/Main documentation pages. Most content changes happen here.docs/api/HTTP API documentation.docs/websockets/WebSocket command, event, and payload documentation.docs/oauth/OAuth 2.0 documentation.docs/contributing/Contributor guides and documentation style rules.src/Docusaurus pages, React components, and custom CSS.static/Static assets copied into the final site.sidebars.tsSidebar navigation order. Update this when adding docs pages.docusaurus.config.tsDocusaurus site configuration.
How To Contribute With Git​

Fork the repository.
Create a branch for your topic.
Edit the relevant files in docs/.
If you add a new page, register it in sidebars.ts.
Run yarn build for docs, sidebar, link, or MDX changes.
Run yarn typecheck for TypeScript, React, or Docusaurus config changes.
Submit a pull request with a short explanation of what you changed.

Public Contributor Rules​
Most public contributors do not have access to the private API backend repository. Without backend source evidence, only make wording-only improvements such as grammar, clarity, formatting, or typo fixes.
Do not change documented public behavior. This includes request or response shapes, fields, auth requirements, scopes, status codes, enum values, validation rules, WebSocket routes, OAuth behavior, and examples that imply contract changes.
Avoid​

Do not invent routes, fields, OAuth behavior, WebSocket events, scopes, rate limits, or rules.
Do not rewrite broad sections when a targeted edit solves the task.
Do not change documented public behavior without backend source evidence.
Do not commit secrets, tokens, or local environment files.
Do not mix formatting-only rewrites with behavior changes.
Previouswfm-themesGood ContributionsBefore You StartRequirementsRunning LocallyRepository LayoutHow To Contribute With GitPublic Contributor RulesAvoid
