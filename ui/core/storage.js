/**
 * @license
 * Copyright 2012 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @fileoverview Loading and saving blocks with localStorage and cloud storage.
 * @author q.neutron@gmail.com (Quynh Neutron)
 * @author gastmaier@gmail.com (Jorge Marques)
 */
'use strict';

/**
 * Create the storage namespace.
 */
var BlocklyStorage = {};

/**
 * Backup code blocks to localStorage.
 * @param {!Blockly.WorkspaceSvg} opt_workspace Workspace.
 * @private
 */
BlocklyStorage.backupBlocks_ = function(opt_workspace) {
  if ('localStorage' in window) {
    var workspace =  opt_workspace || Blockly.getMainWorkspace();

    var xml = Blockly.Xml.workspaceToDom(workspace);
    var data = Blockly.Xml.domToText(xml);
    data = UI ['workspace'].writeWorkspace (data, false);
    localStorage.setItem(UI ['account'].currentProject.uid, data)
    localStorage.setItem('bipes_projects', JSON.stringify(UI ['account'].projects))
  }
};
/**
 * Bind the localStorage backup function to the unload event.
 * @param {Blockly.WorkspaceSvg=} opt_workspace Workspace.
 */
BlocklyStorage.backupOnUnload = function(opt_workspace) {
  var workspace = opt_workspace || Blockly.getMainWorkspace();
  window.addEventListener('unload',
      function() {BlocklyStorage.backupBlocks_(workspace);}, false);
};
/**
 * Restore code blocks from localStorage.
 * @param {Blockly.WorkspaceSvg=} opt_workspace Workspace.
 */
BlocklyStorage.restoreBlocks = function(opt_workspace) {
  if ('localStorage' in window) {
    var workspace = opt_workspace || Blockly.getMainWorkspace();
    /** Import project list*/
    if (localStorage['bipes_projects'] && localStorage['bipes_projects'] != '[]') {
      try {
        let projects = JSON.parse(localStorage['bipes_projects'])
        UI ['account'].restoreProjects (projects);
      } catch (e) {
        UI ['notify'].log(e)
      }
    } else {
      let uid = Tool.uid ();
      localStorage.setItem (uid, Tool.emptyXML ())
      let emptyProject = `{"${uid}":"${+new Date}"}`;
      localStorage.setItem('bipes_projects', emptyProject)
      UI ['account'].restoreProjects (JSON.parse(emptyProject));
    }
  }
};



/**
 * Load blocks from XML.
 * @param {string} xml Text representation of XML.
 * @param {!Blockly.WorkspaceSvg} workspace Workspace.
 * @private
 */
BlocklyStorage.loadXml_ = function(xml, workspace) {
  xml = UI ['workspace'].readWorkspace (xml, false);
  try {
    xml = Blockly.Xml.textToDom(xml);
  } catch (e) {
    BlocklyStorage.alert(BlocklyStorage.XML_ERROR + '\nXML: ' + xml);
    return;
  }
  // Clear the workspace to avoid merge.
  workspace.clear();
  Blockly.Xml.domToWorkspace(xml, workspace);
};

/**
 * Present a text message to the user.
 * Designed to be overridden if an app has custom dialogs, or a butter bar.
 * @param {string} message Text to alert.
 */
BlocklyStorage.alert = function(message) {
  window.alert(message);
};
