'use strict';

/**
 * @fileoverview Arrow Circuits portal sign-in control.
 * Reads who-am-I from the portal and shows a Sign in / Sign out link in the
 * account panel. It does not change how the editor works.
 */

(function () {
  // Config: the portal that owns the accounts (same site, different host).
  var portalBase = 'https://arrowcircuits.com';

  var warned = false;
  var wasHidden = false;

  var api = {
    /** Last who-am-I answer, or null when unknown. */
    user: null,
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

  /**
   * Ask the portal who is signed in, then update user, control and listeners.
   * Never rejects: a failure leaves the signed-out control showing.
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
        });
    } catch (e) {
      p = Promise.reject(e);
    }
    return p.catch(function (e) {
      warn_(e && e.message ? e.message : e);
      api.user = {authenticated: false, displayName: null, roles: []};
    }).then(function () {
      try {
        render_();
        notify_();
      } catch (e) {
        console.warn('arcPortal: render failed', e);
      }
    });
  };

  /**
   * Register a callback, called with the new user after every refresh.
   * @param {!Function} callback
   */
  api.onChange = function (callback) {
    if (typeof callback === 'function') api.listeners.push(callback);
  };

  function init_ () {
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
