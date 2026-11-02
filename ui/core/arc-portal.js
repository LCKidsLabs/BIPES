'use strict';

/**
 * @fileoverview Arrow Circuits portal client.
 * Reads who-am-I from the portal, shows a Sign in / Sign out link in the
 * account panel, talks to the portal projects API, and owns the full-page
 * sign-in gate that keeps the editor unusable until a project can be opened.
 */

(function () {
  // Config: the portal that owns the accounts (same site, different host).
  var portalBase = 'https://arrowcircuits.com';

  var warned = false;
  var wasHidden = false;
  var prevAuthenticated = null;

  var api = {
    /** Last who-am-I answer, or null when unknown. */
    user: null,
    /**
     * 'checking' (no answer yet), 'signedIn', 'signedOut' or 'unreachable'
     * (the who-am-I call failed at the network or server level).
     */
    status: 'checking',
    portalBase: portalBase,
    listeners: []
  };

  /**
   * Absolute URL of the current editor page, without query or hash
   * (the hash will carry share tokens later).
   * @return {string}
   */
  function returnUrl_ () {
    return location.origin + location.pathname;
  }

  function warn_ (why) {
    if (warned) return;
    warned = true;
    console.warn('arcPortal: could not read sign-in state (' + why + ')');
  }

  /**
   * Build the control contents for the current state, using textContent only.
   */
  function render_ () {
    var box = document.getElementById('arc_signin');
    if (!box) return;
    var text = box.querySelector('.arc-signin-text');
    var link = box.querySelector('a');
    var ret = encodeURIComponent(returnUrl_());
    var user = api.user;

    if (user && user.authenticated) {
      text.textContent = user.displayName ? 'Signed in as ' + user.displayName : 'Signed in';
      link.textContent = 'Sign out';
      link.href = portalBase + '/Portal/Account/Logout?returnUrl=' + ret;
    } else {
      text.textContent = 'Sign in to your Arrow Circuits account';
      link.textContent = 'Sign in';
      link.href = portalBase + '/Portal/Account/Login?returnUrl=' + ret;
    }
    box.hidden = false;
  }

  function notify_ () {
    for (var i = 0; i < api.listeners.length; i++) {
      try {
        api.listeners[i](api.user);
      } catch (e) {
        console.warn('arcPortal: listener failed', e);
      }
    }
  }

  // ---------------------------------------------------------------- antiforgery

  var csrf = null;
  var csrfPromise = null;

  function resetToken_ () {
    csrf = null;
    csrfPromise = null;
  }

  function networkError_ () {
    return {status: 0, code: null};
  }

  /**
   * Normalize a failed response to {status, code} (plus savedUtc on a 409).
   * @param {!Response} r
   * @return {!Promise}
   */
  function errorOf_ (r) {
    return r.json().then(function (j) { return j || {}; }, function () { return {}; }).then(function (j) {
      var e = {status: r.status, code: (j && typeof j.code === 'string') ? j.code : null};
      if (j && j.savedUtc) e.savedUtc = j.savedUtc;
      return e;
    });
  }

  function ensureToken_ () {
    if (csrf) return Promise.resolve(csrf);
    if (!csrfPromise) {
      var p;
      try {
        p = fetch(portalBase + '/api/portal/antiforgery', {credentials: 'include', cache: 'no-store'});
      } catch (e) {
        p = Promise.reject(e);
      }
      csrfPromise = p.then(function (r) {
        if (!r.ok) return errorOf_(r).then(function (e) { throw e; });
        return r.json();
      }, function () {
        throw networkError_();
      }).then(function (j) {
        csrf = {headerName: j.headerName, requestToken: j.requestToken};
        csrfPromise = null;
        return csrf;
      }, function (e) {
        csrfPromise = null;
        throw e;
      });
    }
    return csrfPromise;
  }

  function byteLength_ (s) {
    try {
      return new Blob([s]).size;
    } catch (e) {
      return s.length * 3;
    }
  }

  /**
   * One JSON call to the portal. Rejects with {status, code}; status 0 is a
   * network failure. A 400 on a non-GET refetches the antiforgery token and
   * retries once (unless the server said the request itself was invalid).
   */
  function request_ (method, url, body, opts, retried) {
    opts = opts || {};
    var nonGet = method !== 'GET';
    var json = (body === undefined) ? undefined : JSON.stringify(body);

    function send (token) {
      var headers = {'Accept': 'application/json'};
      if (json !== undefined) headers['Content-Type'] = 'application/json';
      if (nonGet && token) headers[token.headerName] = token.requestToken;
      var init = {method: method, headers: headers, credentials: 'include', cache: 'no-store'};
      if (json !== undefined) init.body = json;
      // Browsers cap keepalive bodies at 64 KB.
      if (opts.keepalive && json !== undefined && byteLength_(json) < 60000) init.keepalive = true;
      var p;
      try {
        p = fetch(url, init);
      } catch (e) {
        return Promise.reject(networkError_());
      }
      return p.then(function (r) {
        if (r.ok) return r.status === 204 ? null : r.json().catch(function () { return null; });
        return errorOf_(r).then(function (e) {
          if (nonGet && r.status === 400 && e.code !== 'invalid' && !retried) {
            resetToken_();
            return request_(method, url, body, opts, true);
          }
          throw e;
        });
      }, function () {
        throw networkError_();
      });
    }

    if (!nonGet) return send(null);
    if (csrf) return send(csrf);
    return ensureToken_().then(send);
  }

  function projectsUrl_ (path) {
    return portalBase + '/api/portal/projects' + (path || '');
  }

  function id_ (id) {
    return encodeURIComponent(id);
  }

  /** Portal projects API. Every method returns a promise that rejects with {status, code}. */
  api.projects = {
    /** @return {!Promise} {items, totalCount, ...}, newest saved first, all rows. */
    list: function () { return request_('GET', projectsUrl_('?pageSize=0&sort=savedUtc&dir=desc')); },
    current: function () { return request_('GET', projectsUrl_('/current')); },
    get: function (id) { return request_('GET', projectsUrl_('/' + id_(id))); },
    /** @param {{name, board, xml, python}} body */
    create: function (body) { return request_('POST', projectsUrl_(''), body); },
    /** @param {{xml, python, board, savedUtc, force}} body @param {{keepalive}=} opts */
    save: function (id, body, opts) { return request_('PUT', projectsUrl_('/' + id_(id)), body, opts); },
    rename: function (id, name) { return request_('PUT', projectsUrl_('/' + id_(id) + '/name'), {name: name}); },
    remove: function (id) { return request_('DELETE', projectsUrl_('/' + id_(id))); },
    setCurrent: function (id) { return request_('PUT', projectsUrl_('/current/' + id_(id))); }
  };

  // ----------------------------------------------------------------------- gate

  var gateEl = null;
  var gateMode = null;
  var released = false;

  function el_ (tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function loginUrl_ (withReturn) {
    var url = portalBase + '/Portal/Account/Login';
    if (withReturn) url += '?returnUrl=' + encodeURIComponent(location.href);
    return url;
  }

  function linkButton_ (text, href, blank) {
    var a = el_('a', 'arc-gate-button', text);
    a.href = href;
    if (blank) {
      a.target = '_blank';
      a.rel = 'noopener';
    }
    return a;
  }

  function showGate_ (mode) {
    if (!document.body) return;
    if (!gateEl) {
      gateEl = el_('div', '');
      gateEl.id = 'arc_gate';
      gateEl.setAttribute('role', 'dialog');
      gateEl.setAttribute('aria-modal', 'true');
    }
    if (!gateEl.parentNode) document.body.appendChild(gateEl);
    gateMode = mode;
    while (gateEl.firstChild) gateEl.removeChild(gateEl.firstChild);

    var card = el_('div', 'arc-gate-card');
    var title = '';
    var text = '';
    var actions = el_('div', 'arc-gate-actions');

    if (mode === 'signedOut') {
      title = 'Sign in to use the editor';
      text = 'Your projects are saved to your Arrow Circuits account.';
      actions.appendChild(linkButton_('Sign in', loginUrl_(true)));
      actions.appendChild(linkButton_('Create account', portalBase + '/Portal/Account/Register'));
    } else if (mode === 'unreachable') {
      title = 'Can’t reach Arrow Circuits';
      text = 'Check your connection, then try again.';
      var retry = el_('button', 'arc-gate-button', 'Retry');
      retry.type = 'button';
      retry.onclick = function () {
        showGate_('checking');
        api.refresh();
      };
      actions.appendChild(retry);
    } else if (mode === 'expired') {
      title = 'You’ve been signed out';
      text = 'Sign in again in the new tab, then come back to this tab. Your work here is kept and will be saved.';
      actions.appendChild(linkButton_('Sign in (opens a new tab)', loginUrl_(false), true));
    } else if (mode === 'forbidden') {
      title = 'This account can’t save projects yet.';
      actions.appendChild(linkButton_('Sign out', portalBase + '/Portal/Account/Logout?returnUrl=' +
        encodeURIComponent(returnUrl_())));
    } else if (mode === 'loading') {
      title = 'Opening your project…';
    } else {
      title = 'Connecting to Arrow Circuits…';
    }

    card.appendChild(el_('h2', '', title));
    if (text) card.appendChild(el_('p', '', text));
    if (actions.firstChild) card.appendChild(actions);
    gateEl.appendChild(card);
  }

  function hideGate_ () {
    gateMode = null;
    if (gateEl && gateEl.parentNode) gateEl.parentNode.removeChild(gateEl);
  }

  /**
   * Before the editor has opened its first project the gate follows who-am-I.
   * After that the storage layer owns it (see BlocklyStorage in storage.js).
   */
  function followStatus_ () {
    if (released) return;
    if (api.status === 'signedIn') {
      if (gateMode !== 'forbidden') showGate_('loading');
    } else if (api.status === 'unreachable') {
      showGate_('unreachable');
    } else if (api.status === 'signedOut') {
      showGate_('signedOut');
    }
  }

  api.gate = {
    /** @param {string} mode checking, loading, signedOut, unreachable, expired or forbidden */
    show: showGate_,
    hide: hideGate_,
    /** The editor is open: from now on the storage layer drives the gate. */
    release: function () {
      released = true;
      hideGate_();
    },
    mode: function () { return gateMode; },
    isReleased: function () { return released; }
  };

  // ------------------------------------------------------------------- who-am-I

  /**
   * Ask the portal who is signed in, then update user, status, control and listeners.
   * Never rejects: a failure sets status 'unreachable' and shows the signed-out control.
   * @return {Promise}
   */
  api.refresh = function () {
    var p;
    try {
      p = fetch(portalBase + '/api/portal/me', {credentials: 'include', cache: 'no-store'})
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          api.user = {
            authenticated: !!(data && data.authenticated),
            displayName: (data && data.displayName) || null,
            roles: (data && Array.isArray(data.roles)) ? data.roles : []
          };
          api.status = api.user.authenticated ? 'signedIn' : 'signedOut';
        });
    } catch (e) {
      p = Promise.reject(e);
    }
    return p.catch(function (e) {
      warn_(e && e.message ? e.message : e);
      api.user = {authenticated: false, displayName: null, roles: []};
      api.status = 'unreachable';
    }).then(function () {
      try {
        if (api.status !== 'unreachable') {
          var now = api.status === 'signedIn';
          if (prevAuthenticated !== null && prevAuthenticated !== now) resetToken_();
          prevAuthenticated = now;
          if (now) ensureToken_().catch(function () {});
        }
        render_();
        followStatus_();
        notify_();
      } catch (e) {
        console.warn('arcPortal: render failed', e);
      }
    });
  };

  /**
   * Register a callback, called with the new user after every refresh.
   * Read arcPortal.status to tell signed out from unreachable.
   * @param {!Function} callback
   */
  api.onChange = function (callback) {
    if (typeof callback === 'function') api.listeners.push(callback);
  };

  function init_ () {
    showGate_('checking');
    api.refresh();
    window.addEventListener('pageshow', function (e) {
      if (e.persisted) api.refresh();
    });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        wasHidden = true;
      } else if (wasHidden) {
        wasHidden = false;
        api.refresh();
      }
    });
  }

  window.arcPortal = api;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init_);
  } else {
    init_();
  }
})();
