/**
 * @license
 * Copyright 2012 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @fileoverview Loading and saving blocks. Projects live on the Arrow Circuits
 * portal (see arc-portal.js); this file resumes the current project, autosaves
 * the open one, and drives the save-status pill and the "changed in another
 * window" bar.
 * @author q.neutron@gmail.com (Quynh Neutron)
 * @author gastmaier@gmail.com (Jorge Marques)
 */
'use strict';

/**
 * Create the storage namespace.
 */
var BlocklyStorage = {};

(function () {
  var DEBOUNCE_MS = 4000;
  var INTERVAL_MS = 30000;
  var QUIET_MS = 800;

  /** State of the open project and of the save loop. */
  var S = BlocklyStorage.state = {
    id: null,           // open project id
    name: '',           // name the server holds
    savedUtc: null,     // server's savedUtc string, sent back unchanged
    lastNorm: null,     // normalized XML last saved (or loaded)
    tooLargeNorm: null, // normalized XML the server refused as too large
    timer: null,
    inflight: false,
    inflightP: null,
    queued: false,
    loading: false,     // true while a project is being swapped in
    quietUntil: 0,
    started: false,
    booted: false,
    booting: false,
    switching: false,
    stale: false,       // 409 projectStale pending a user choice
    authLost: false,    // a save answered 401 or who-am-I says signed out
    forbidden: false,
    unreadable: false,  // the loaded XML could not be parsed: never save over it
    override: null,
    status: 'saved'
  };

  // ------------------------------------------------------------------ helpers

  function el_ (tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function say_ (msg) {
    try {
      UI ['notify'].send (msg);
    } catch (e) {
      console.warn (msg);
    }
  }

  /** XML without the volatile timestamp, for change detection. */
  function norm_ (xml) {
    return xml.replace (/<field name="TIMESTAMP">\d*<\/field>/, '');
  }

  /** @return {{xml:string, norm:string, python:?string, board:string}} */
  function serialize_ () {
    var ws = Code.workspace;
    var xml = UI ['workspace'].writeWorkspace (Blockly.Xml.domToText (Blockly.Xml.workspaceToDom (ws)), false);
    var python = null;
    try {
      var code = Code.generateCode ();
      if (typeof code === 'string') python = code;
    } catch (e) {}
    return {xml: xml, norm: norm_ (xml), python: python, board: UI ['workspace'].selector.value};
  }

  function isDirty_ () {
    if (S.unreadable) return false;
    return serialize_ ().norm !== S.lastNorm;
  }

  function unescape_ (s) {
    return s.replace (/&lt;/g, '<').replace (/&gt;/g, '>').replace (/&quot;/g, '"')
      .replace (/&apos;/g, "'").replace (/&amp;/g, '&');
  }

  /** The project name the XML holds (the project_description block), or ''. */
  function nameFromXml_ (xml) {
    var chunk = /<value name="project_description">.*?<\/value>/.exec (xml);
    if (!chunk) return '';
    var m = /<field name="TEXT">(.*?)<\/field>/.exec (chunk [0]);
    return m ? unescape_ (m [1]).trim ().slice (0, 120) : '';
  }

  function setBlockName_ (name) {
    try {
      Code.workspace.getBlocksByType ('project_metadata').forEach (function (block) {
        var input = block.getInput ('project_description');
        var target = input && input.connection && input.connection.targetBlock ();
        if (target) target.setFieldValue (name, 'TEXT');
      });
    } catch (e) {}
  }

  function emptyBody_ () {
    return {name: 'My project', board: UI ['workspace'].selector.value, xml: Tool.emptyXML (), python: null};
  }

  // ------------------------------------------------------- status pill and bar

  var STATUS_TEXT = {
    saved: 'Saved',
    saving: 'Saving…',
    offline: 'Offline',
    unsaved: 'Not saved',
    toolarge: 'Too large to save (8 MB limit)',
    unreadable: 'Can’t open this project'
  };

  var pill = null;

  function setStatus_ (kind) {
    S.status = kind;
    if (!document.body) return;
    if (!pill) {
      pill = el_ ('div', 'arc-save-status');
      pill.id = 'arc_save_status';
      pill.setAttribute ('role', 'status');
      document.body.appendChild (pill);
    }
    pill.textContent = STATUS_TEXT [kind] || STATUS_TEXT.unsaved;
    pill.setAttribute ('data-state', kind);
  }

  var bar = null;

  function hideStaleBar_ () {
    if (bar && bar.parentNode) bar.parentNode.removeChild (bar);
  }

  function showStaleBar_ () {
    hideStaleBar_ ();
    bar = el_ ('div', 'arc-stale-bar');
    bar.id = 'arc_stale_bar';
    bar.setAttribute ('role', 'alert');
    bar.appendChild (el_ ('span', '', 'This project was changed in another window.'));
    var reload = el_ ('button', '', 'Reload');
    reload.type = 'button';
    reload.onclick = function () {
      var id = S.id;
      arcPortal.projects.get (id).then (function (p) {
        if (S.id !== id) return;
        loadProject_ (p);
      }, function (e) {
        apiFail_ (e);
      });
    };
    var keep = el_ ('button', '', 'Keep mine');
    keep.type = 'button';
    keep.onclick = function () {
      S.stale = false;
      hideStaleBar_ ();
      saveNow_ ({force: true});
    };
    bar.appendChild (reload);
    bar.appendChild (keep);
    document.body.appendChild (bar);
  }

  // ---------------------------------------------------------------- failures

  /**
   * Handle a refusal that is the same for every call: signed out, not allowed,
   * limits, network. Returns nothing; the caller decides what else to do.
   */
  function apiFail_ (e) {
    var status = e && e.status;
    var code = e && e.code;
    if (status === 401) {
      S.authLost = true;
      arcPortal.gate.show ('expired');
    } else if (status === 403) {
      S.forbidden = true;
      arcPortal.gate.show ('forbidden');
    } else if (status === 409 && code === 'projectLimitReached') {
      say_ ('You have reached 500 projects. Delete some projects before creating or importing more.');
    } else if (status === 413) {
      say_ ('That project is too large (8 MB limit).');
    } else if (status === 0) {
      say_ ('Can’t reach Arrow Circuits. Check your connection and try again.');
    } else {
      say_ ('Arrow Circuits could not complete that (error ' + status + '). Try again.');
    }
  }

  // ------------------------------------------------------------------- saving

  function blocked_ () {
    return S.stale || S.authLost || S.forbidden || S.unreadable || S.loading || !S.id;
  }

  function schedule_ () {
    if (blocked_ ()) return;
    if (S.timer) clearTimeout (S.timer);
    S.timer = setTimeout (function () {
      S.timer = null;
      saveNow_ ();
    }, DEBOUNCE_MS);
    if (S.status === 'saved') setStatus_ ('unsaved');
  }

  /**
   * Save the open project if its XML changed. One save at a time; a call made
   * while one is in flight is remembered and runs afterwards with the latest XML.
   * @param {{force:boolean, keepalive:boolean}=} o
   * @return {!Promise}
   */
  function saveNow_ (o) {
    o = o || {};
    if (S.timer) {
      clearTimeout (S.timer);
      S.timer = null;
    }
    if (blocked_ ()) return Promise.resolve ();
    if (S.inflight) {
      S.queued = true;
      return S.inflightP;
    }
    S.inflightP = doSave_ (o);
    return S.inflightP;
  }

  function doSave_ (o) {
    var cur;
    try {
      cur = serialize_ ();
    } catch (e) {
      console.warn ('save: could not read the workspace', e);
      return Promise.resolve ();
    }
    if (!o.force && cur.norm === S.lastNorm) {
      if (S.status === 'unsaved') setStatus_ ('saved');
      return Promise.resolve ();
    }
    if (!o.force && cur.norm === S.tooLargeNorm) return Promise.resolve ();

    var id = S.id;
    S.inflight = true;
    setStatus_ ('saving');
    var body = {xml: cur.xml, python: cur.python, board: cur.board, savedUtc: S.savedUtc, force: !!o.force};

    return arcPortal.projects.save (id, body, {keepalive: !!o.keepalive}).then (function (res) {
      if (S.id !== id) return;
      S.savedUtc = res.savedUtc;
      S.lastNorm = cur.norm;
      S.tooLargeNorm = null;
      setStatus_ (S.timer ? 'unsaved' : 'saved');
      syncName_ (cur.xml);
    }, function (e) {
      if (S.id !== id) return;
      var status = e && e.status;
      if (status === 0) {
        setStatus_ ('offline');
      } else if (status === 401) {
        setStatus_ ('unsaved');
        apiFail_ (e);
      } else if (status === 403) {
        setStatus_ ('unsaved');
        apiFail_ (e);
      } else if (status === 413) {
        S.tooLargeNorm = cur.norm;
        setStatus_ ('toolarge');
      } else if (status === 409 && e.code === 'projectStale') {
        S.stale = true;
        setStatus_ ('unsaved');
        showStaleBar_ ();
      } else {
        setStatus_ ('unsaved');
      }
    }).then (function () {
      S.inflight = false;
      if (S.queued) {
        S.queued = false;
        return saveNow_ ();
      }
    });
  }

  /** Keep the server name in step with the project_description block. */
  function syncName_ (xml) {
    var name = nameFromXml_ (xml);
    if (!name || name === S.name) return;
    var id = S.id;
    var old = S.name;
    S.name = name;
    arcPortal.projects.rename (id, name).then (function () {
      try {
        UI ['account'].setProjectLabel (id, name);
      } catch (e) {}
    }, function () {
      if (S.id === id) S.name = old;
    });
  }

  /** Wait for any save in flight, then save the latest. */
  function flush_ (o) {
    if (S.timer) {
      clearTimeout (S.timer);
      S.timer = null;
    }
    var wait = function () {
      if (S.inflight) return S.inflightP.then (wait);
      return saveNow_ (o);
    };
    return wait ();
  }

  // ------------------------------------------------------------------ loading

  /**
   * Put a server project into the editor and make it the open one.
   * @param {!Object} p Project from the API.
   */
  function loadProject_ (p) {
    S.loading = true;
    if (S.timer) {
      clearTimeout (S.timer);
      S.timer = null;
    }
    S.id = p.id;
    S.name = p.name || '';
    S.savedUtc = p.savedUtc;
    S.stale = false;
    S.unreadable = false;
    S.tooLargeNorm = null;
    hideStaleBar_ ();

    var xml = p.xml || Tool.emptyXML ();
    var ok = false;
    try {
      ok = BlocklyStorage.loadXml_ (xml, Blockly.getMainWorkspace ());
    } catch (e) {
      console.warn ('load failed', e);
    }
    S.unreadable = !ok;
    if (ok) {
      // Stored in the pretty file format (an imported file): rewrite it normalized.
      S.lastNorm = /<workspace>\n/.test (xml) ? null : serialize_ ().norm;
    } else {
      S.lastNorm = null;
    }
    S.quietUntil = Date.now () + QUIET_MS;
    S.loading = false;
    setStatus_ (ok ? 'saved' : 'unreadable');
    if (ok && S.lastNorm === null) schedule_ ();

    try {
      UI ['account'].currentProject.uid = p.id;
      UI ['account'].markCurrent (p.id);
      Files.handleCurrentProject ();
    } catch (e) {}
  }

  /**
   * Load blocks from XML (the stored format: workspace chunk plus Blockly XML).
   * @param {string} xml Text representation of XML.
   * @param {!Blockly.WorkspaceSvg} workspace Workspace.
   * @return {boolean} False if the XML could not be read (the workspace is untouched).
   * @private
   */
  BlocklyStorage.loadXml_ = function (xml, workspace) {
    var pretty = /<workspace>\n/.test (xml);
    xml = UI ['workspace'].readWorkspace (xml, pretty);
    try {
      xml = Blockly.Xml.textToDom (xml);
    } catch (e) {
      BlocklyStorage.alert (BlocklyStorage.XML_ERROR + '\nXML: ' + xml);
      return false;
    }
    // Clear the workspace to avoid merge.
    workspace.clear ();
    Blockly.Xml.domToWorkspace (xml, workspace);
    return true;
  };

  // --------------------------------------------------------------------- boot

  function bootFailed_ (e) {
    var status = e && e.status;
    if (status === 401) {
      arcPortal.gate.show ('signedOut');
    } else if (status === 403) {
      S.forbidden = true;
      arcPortal.gate.show ('forbidden');
    } else {
      arcPortal.gate.show ('unreachable');
    }
  }

  function boot_ () {
    S.booting = true;
    arcPortal.projects.current ().then (null, function (e) {
      if (e && e.status === 404 && e.code === 'noCurrentProject') {
        return arcPortal.projects.create (emptyBody_ ());
      }
      throw e;
    }).then (function (p) {
      loadProject_ (p);
      if (S.override) {
        try {
          Code.workspace.clear ();
          Blockly.Xml.domToWorkspace (Blockly.Xml.textToDom (S.override), Code.workspace);
          S.quietUntil = 0;
          schedule_ ();
        } catch (e) {
          console.warn ('could not apply the carried-over blocks', e);
        }
        S.override = null;
      }
      S.booted = true;
      S.booting = false;
      arcPortal.gate.release ();
      try {
        UI ['account'].refreshList ();
      } catch (e) {}
    }).catch (function (e) {
      S.booting = false;
      bootFailed_ (e);
    });
  }

  function onPortal_ () {
    var st = arcPortal.status;
    if (!S.booted) {
      if (st === 'signedIn' && !S.booting && !S.forbidden) boot_ ();
      return;
    }
    if (st === 'signedOut') {
      if (!S.authLost) {
        S.authLost = true;
        arcPortal.gate.show ('expired');
      }
    } else if (st === 'signedIn' && S.authLost) {
      S.authLost = false;
      arcPortal.gate.hide ();
      saveNow_ ();
    }
  }

  /**
   * Begin: once the editor may be used (signed in), resume the current project.
   * Called when the board list has loaded.
   * @param {?string=} override Blockly XML to put on top of the resumed project
   *     (the blocks kept across a language switch).
   */
  BlocklyStorage.start = function (override) {
    if (override) S.override = override;
    if (!S.started) {
      S.started = true;
      arcPortal.onChange (onPortal_);
      Code.workspace.addChangeListener (function (ev) {
        if (blocked_ () || Date.now () < S.quietUntil) return;
        if (ev.isUiEvent || ev.type === 'ui' || ev.type === 'finished_loading') return;
        schedule_ ();
      });
      UI ['workspace'].selector.addEventListener ('change', schedule_);
      setInterval (function () {
        if (blocked_ () || S.inflight) return;
        if (isDirty_ ()) saveNow_ ();
      }, INTERVAL_MS);
      document.addEventListener ('visibilitychange', function () {
        if (document.hidden) flush_ ({keepalive: true});
      });
      window.addEventListener ('pagehide', function () {
        flush_ ({keepalive: true});
      });
      window.addEventListener ('online', function () {
        if (S.status === 'offline') saveNow_ ();
      });
    }
    onPortal_ ();
  };

  // --------------------------------------------------- project list operations

  /**
   * Leave the open project: save it, or ask before dropping changes that could not be saved.
   * @return {!Promise<boolean>} True if it is fine to replace the workspace.
   */
  function leaveCurrent_ () {
    if (!S.id) return Promise.resolve (true);
    return flush_ ().then (function () {
      if (!isDirty_ ()) return true;
      return window.confirm ('Your latest changes could not be saved. Switch anyway and lose them?');
    });
  }

  function guarded_ (fn) {
    return function () {
      if (S.switching || !S.booted) return Promise.resolve ();
      S.switching = true;
      var args = arguments;
      return Promise.resolve ().then (function () {
        return fn.apply (null, args);
      }).catch (apiFail_).then (function () {
        S.switching = false;
      });
    };
  }

  /** Open a project from the list. */
  BlocklyStorage.openProject = guarded_ (function (id) {
    if (id === S.id) return;
    return leaveCurrent_ ().then (function (go) {
      if (!go) return;
      return arcPortal.projects.setCurrent (id).then (function () {
        return arcPortal.projects.get (id);
      }).then (function (p) {
        loadProject_ (p);
        UI ['account'].refreshList ();
      });
    });
  });

  /** Create an empty project and open it. */
  BlocklyStorage.newProject = guarded_ (function () {
    return leaveCurrent_ ().then (function (go) {
      if (!go) return;
      return arcPortal.projects.create (emptyBody_ ()).then (function (p) {
        loadProject_ (p);
        UI ['account'].refreshList ();
      });
    });
  });

  /**
   * Create a project from the text of a .bipes.xml file and open it.
   * @param {string} xml File contents.
   * @param {string=} fallbackName Used when the XML holds no project name.
   */
  BlocklyStorage.importProject = guarded_ (function (xml, fallbackName) {
    return leaveCurrent_ ().then (function (go) {
      if (!go) return;
      var name = nameFromXml_ (xml) || (fallbackName || '').replace (/\.bipes\.xml$|\.xml$/i, '').slice (0, 120) || 'Imported project';
      var board = '';
      var m = /<field name="DEVICE">(.+?)<\/field>/.exec (xml);
      board = m ? m [1] : UI ['workspace'].selector.value;
      return arcPortal.projects.create ({name: name, board: board, xml: xml, python: null}).then (function (p) {
        loadProject_ (p);
        UI ['account'].refreshList ();
      });
    });
  });

  /** Delete a project; if it was open, open the most recent other one or a new one. */
  BlocklyStorage.deleteProject = guarded_ (function (id) {
    var wasOpen = id === S.id;
    if (wasOpen) {
      if (S.timer) {
        clearTimeout (S.timer);
        S.timer = null;
      }
      S.loading = true;   // no saves while the project goes away
    }
    var settle = wasOpen && S.inflight ? S.inflightP : Promise.resolve ();
    return settle.then (function () {
      return arcPortal.projects.remove (id);
    }).then (function () {
      if (!wasOpen) {
        UI ['account'].refreshList ();
        return;
      }
      return arcPortal.projects.list ().then (function (res) {
        var items = (res && res.items) || [];
        if (items.length) {
          return arcPortal.projects.setCurrent (items [0].id).then (function () {
            return arcPortal.projects.get (items [0].id);
          });
        }
        return arcPortal.projects.create (emptyBody_ ());
      }).then (function (p) {
        loadProject_ (p);
        UI ['account'].refreshList ();
      });
    }).catch (function (e) {
      if (wasOpen && S.id === id) S.loading = false;
      throw e;
    });
  });

  /** Rename a project on the server and, if it is open, in its description block. */
  BlocklyStorage.renameProject = guarded_ (function (id, name) {
    name = (name || '').trim ().slice (0, 120);
    if (!name) return;
    return arcPortal.projects.rename (id, name).then (function () {
      try {
        UI ['account'].setProjectLabel (id, name);
      } catch (e) {}
      if (id === S.id) {
        S.name = name;
        setBlockName_ (name);
      }
    });
  });

  /** @return {!Promise<?string>} The XML of a project, from the editor if it is the open one. */
  BlocklyStorage.projectXml = function (id) {
    if (id === S.id) {
      try {
        return Promise.resolve (serialize_ ().xml);
      } catch (e) {}
    }
    return arcPortal.projects.get (id).then (function (p) {
      return p.xml;
    });
  };

  /**
   * Present a text message to the user.
   * Designed to be overridden if an app has custom dialogs, or a butter bar.
   * @param {string} message Text to alert.
   */
  BlocklyStorage.alert = function (message) {
    window.alert (message);
  };
})();
