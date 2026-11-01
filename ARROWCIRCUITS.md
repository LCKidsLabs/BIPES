# Arrow Circuits build of BIPES

This is the `arrowcircuits` branch of the LCKidsLabs fork of BIPES (https://github.com/LCKidsLabs/BIPES). It is based on the upstream `offline` branch at commit `06a31030c08be22e6ad9d1d3493d4d54d63bb68c`.

It is served as static files at https://bipes.arrowcircuits.com. The commit that is deployed is always pushed to this public fork first, so the source of what is running is available under the GPL-3.0. The BIPES license (`LICENSE`) and credit are kept; the About text still credits the BIPES team and bipes.net.br.

## What changed from `offline`, and why

- Google Analytics removed from `ui/index.html` and `ui/ports.html`: no visitor tracking.
- EasyMQTT removed (tab, iframe, settings button, data bridge, `ui/easymqtt_bridge.html`): it depends on a service and a folder this site does not host. The user-program MQTT blocks are untouched.
- Old App Engine share client removed (`BlocklyStorage.link`, `retrieveXml`, the share button, the shared-programs tab and `ui/shared.html`): the backing service is not available. A `#hash` on load now reaches `Code.importFromShareLink`, which does nothing yet. Browser (localStorage) project storage is unchanged.
- References to bipes.net.br removed from `ui/core/channel.js`, `ui/core/utils.js` and `ui/manifest.json`; manifest URLs are relative. Credit links in the About text stay.
- The MicroPython library path in `ui/core/utils.js` (and the matching fetches in `ui/core/code.js`) is now relative (`pylibs/`), so it resolves to `ui/pylibs/` from `ui/index.html` instead of a fixed `/beta2/ui/` path. The language links in the welcome dialog are relative for the same reason.
- Service worker disabled (`pwa-update` import, `manup.js`, `pwabuilder-sw.js` removed); `manifest.json` is still linked. Without it, deploys are not held back by a cached copy.
- `.gitmodules` uses `https://github.com/BIPES/...` URLs so clones work without SSH keys.
- About text: added a sentence identifying this build and linking to this branch.
- `web.config` added for IIS 10: MIME types for every deployed file extension, no-cache revalidation, `index.html` as the default document.
- Because the shared-programs and EasyMQTT iframes are gone, the iframe indexes used for the IoT dashboard and Databoard in `ui/core/*.js` were renumbered.
