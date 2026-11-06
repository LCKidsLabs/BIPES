# Arrow Circuits build of BIPES

This is the `arrowcircuits` branch of the LCKidsLabs fork of BIPES (https://github.com/LCKidsLabs/BIPES). It is based on the upstream `offline` branch at commit `06a31030c08be22e6ad9d1d3493d4d54d63bb68c`.

It is served as static files at https://bipes.arrowcircuits.com. The commit that is deployed is always pushed to this public fork first, so the source of what is running is available under the GPL-3.0. The BIPES license (`LICENSE`) and credit are kept; the About text still credits the BIPES team and bipes.net.br.

## What changed from `offline`, and why

- Google Analytics removed from `ui/index.html` and `ui/ports.html`: no visitor tracking.
- EasyMQTT removed (tab, iframe, settings button, data bridge, `ui/easymqtt_bridge.html`): it depends on a service and a folder this site does not host. The user-program MQTT blocks are untouched.
- Old App Engine share client removed (`BlocklyStorage.link`, `retrieveXml`, the share button, the shared-programs tab and `ui/shared.html`): the backing service is not available. A `#hash` on load still reaches `Code.importFromShareLink`, which now imports portal share links (see Share links below). Project storage is described under Projects on the portal below.
- The site root `index.html` redirects to `ui/` with a script that keeps the `#hash` (a `<noscript>` meta refresh is the fallback), so `/#token` share links survive the redirect.
- References to bipes.net.br removed from `ui/core/channel.js`, `ui/core/utils.js` and `ui/manifest.json`; manifest URLs are relative. Credit links in the About text stay.
- The MicroPython library path in `ui/core/utils.js` (and the matching fetches in `ui/core/code.js`) is now relative (`pylibs/`), so it resolves to `ui/pylibs/` from `ui/index.html` instead of a fixed `/beta2/ui/` path. The language links in the welcome dialog are relative for the same reason.
- Service worker disabled (`pwa-update` import, `manup.js`, `pwabuilder-sw.js` removed); `manifest.json` is still linked. Without it, deploys are not held back by a cached copy.
- `.gitmodules` uses `https://github.com/BIPES/...` URLs so clones work without SSH keys.
- About text: added a sentence identifying this build and linking to this branch.
- `web.config` added for IIS 10: an HTTP to HTTPS 301 redirect (URL Rewrite), MIME types for every deployed file extension, no-cache revalidation, `index.html` as the default document.
- Because the shared-programs and EasyMQTT iframes are gone, the iframe indexes used for the IoT dashboard and Databoard in `ui/core/*.js` were renumbered.

## HippaFone handset board

Adds a board for the Adafruit ESP32-S3 Feather (product 5477) with the 3.5 inch capacitive TFT FeatherWing (product 5872), running MicroPython.

- Board id `FEATHER_S3_MPY`: an entry in `ui/devinfo/devinfo.json`, a line in the device list in `ui/index.html`, and the picture `ui/devinfo/hippafone.svg`.
- Toolbox `ui/toolbox/hippafone.xml`: the stock Logic, Loops, Math, Text, Lists, Variables and Functions categories plus Timing and HippaFone. It offers no stock hardware blocks, so only the `hippa_*` blocks touch the hardware.
- Blocks `ui/core/hippa_blocks.js`, loaded after `core/generator_stubs.js`: screen title, write and clear; radio send and new message; BOOT button pressed and held; light and light off; line typed on the computer; wait; seconds now; forever. Each one generates a call into the helper library, with `import hippa` at the top of the program.
- Helper library `ui/pylibs/hippa.py`, `hippa_io.py` and `hippa_screen.py`, described in `ui/pylibs/README-hippa.md`. The editor does not put these files on the board yet: until they are on it, a program stops with an ImportError.

These blocks have only been tested off the board, with mock hardware and in a headless browser.

## Portal sign-in (`ui/core/arc-portal.js`)

Adds a small sign-in control to the account panel (`#arc_signin`, under the "Hello, User!" line; the editable `#account_user` nickname is separate and untouched). It asks the Arrow Circuits portal who is signed in (`GET {portalBase}/api/portal/me`, with credentials) and shows "Sign in" or "Signed in as <name>" with a "Sign out" link. Both links are plain navigations to the portal, which returns to the current editor page. Sign in (and the gate's Sign in button) returns to the full address, hash included, so a share link survives signing in; Sign out returns to origin and path only.

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

## Share links

A member can share the open project by link; whoever opens the link gets their own copy, never access to the original.

- Account panel, above the project list: "Share by link", or once shared, the link (`https://bipes.arrowcircuits.com/ui/#<token>`) with "Copy link" and "Stop sharing". Stopping kills the link; sharing again makes a new one. Calls: `arcPortal.projects.share`, `unshare` (the portal's `POST`/`DELETE /api/portal/projects/{id}/share`).
- Opening `…/ui/#<token>` (a 22-character token; any other hash is ignored): signed out, the sign-in gate shows first and the token survives sign-in. Once the member's current project has resumed, the editor reads `GET /api/portal/projects/shared/{token}` (signed-in members only, rate limited; name, board, XML and the owner's display name), creates a new project in the member's account from it, opens it and says "Copied … by …", then removes the hash so a reload does not copy again.
- A link that no longer works says so and removes the hash. The 500-project limit, a project too large, too many requests or a network error show a message, keep the hash (reload to retry) and leave the resumed project open.
