# Arrow Circuits build of BIPES

This is the `arrowcircuits` branch of the LCKidsLabs fork of BIPES (https://github.com/LCKidsLabs/BIPES). It is based on the upstream `offline` branch at commit `06a31030c08be22e6ad9d1d3493d4d54d63bb68c`.

It is served as static files at https://bipes.arrowcircuits.com. The commit that is deployed is always pushed to this public fork first, so the source of what is running is available under the GPL-3.0. The BIPES license (`LICENSE`) and credit are kept; the About text still credits the BIPES team and bipes.net.br.

## What changed from `offline`, and why

- Google Analytics removed from `ui/index.html` and `ui/ports.html`: no visitor tracking.
- EasyMQTT removed (tab, iframe, settings button, data bridge, `ui/easymqtt_bridge.html`): it depends on a service and a folder this site does not host. The user-program MQTT blocks are untouched.
- Old App Engine share client removed (`BlocklyStorage.link`, `retrieveXml`, the share button, the shared-programs tab and `ui/shared.html`): the backing service is not available. A `#hash` on load now reaches `Code.importFromShareLink`, which does nothing yet. Project storage is described under Projects on the portal below.
- References to bipes.net.br removed from `ui/core/channel.js`, `ui/core/utils.js` and `ui/manifest.json`; manifest URLs are relative. Credit links in the About text stay.
- The MicroPython library path in `ui/core/utils.js` (and the matching fetches in `ui/core/code.js`) is now relative (`pylibs/`), so it resolves to `ui/pylibs/` from `ui/index.html` instead of a fixed `/beta2/ui/` path. The language links in the welcome dialog are relative for the same reason.
- Service worker disabled (`pwa-update` import, `manup.js`, `pwabuilder-sw.js` removed); `manifest.json` is still linked. Without it, deploys are not held back by a cached copy.
- `.gitmodules` uses `https://github.com/BIPES/...` URLs so clones work without SSH keys.
- About text: added a sentence identifying this build and linking to this branch.
- `web.config` added for IIS 10: an HTTP to HTTPS 301 redirect (URL Rewrite), MIME types for every deployed file extension, no-cache revalidation, `index.html` as the default document.
- Because the shared-programs and EasyMQTT iframes are gone, the iframe indexes used for the IoT dashboard and Databoard in `ui/core/*.js` were renumbered.

## Portal sign-in (`ui/core/arc-portal.js`)

Adds a small sign-in control to the account panel (`#arc_signin`, under the "Hello, User!" line; the editable `#account_user` nickname is separate and untouched). It asks the Arrow Circuits portal who is signed in (`GET {portalBase}/api/portal/me`, with credentials) and shows "Sign in" or "Signed in as <name>" with a "Sign out" link. Both links are plain navigations to the portal, which returns to the current editor page (origin and path only; the hash is dropped).

- Config block at the top of the file: `portalBase` (default `https://arrowcircuits.com`). No other settings.
- Public surface: `window.arcPortal.user` (last answer or null), `refresh()` (returns a promise, never rejects), `onChange(callback)`.
- It refreshes when the DOM is ready, on `pageshow` from the back/forward cache, and when the tab becomes visible again. If the portal is unreachable it shows the signed-out control and logs one `console.warn`.
- For now it only reads who-am-I. Account-linked features come in a later phase. The panel text is English inline; the account panel is not translated in BIPES.

## Projects on the portal (`ui/core/storage.js`)

Projects are saved on arrowcircuits.com through the portal projects API (`arcPortal.projects` in `ui/core/arc-portal.js`), not in the browser. The editor resumes the member's current project on load and autosaves the open one (a few seconds after a change, every 30 seconds while dirty, and when the tab is hidden or closed); the status pill shows Saved, Saving, Offline or Not saved, and a "changed in another window" bar offers Reload or Keep mine.

- Sign-in gate: a full-page overlay keeps the editor unusable until the portal confirms a signed-in member and the project has opened. It shows Sign in / Create account, "Can't reach Arrow Circuits" with Retry, or "You've been signed out" (sign in again in a new tab; unsaved work is kept and saved afterwards).
- The save on page unload (`BlocklyStorage.backupOnUnload`) is removed; the autosave and the hide/close flush replace it.
- File export (`.bipes.xml` download) and import (creates a new project) are kept.
- Projects that earlier versions stored in the browser's localStorage are left there untouched and are no longer read.
