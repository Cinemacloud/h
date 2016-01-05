'use strict';

var HypothesisChromeExtension = require('./hypothesis-chrome-extension');
var extensionSettings = require('./extension-settings');

extensionSettings.init();

var browserExtension = new HypothesisChromeExtension({
  chromeTabs: chrome.tabs,
  chromeBrowserAction: chrome.browserAction,
  extensionURL: function (path) {
    return chrome.extension.getURL(path);
  },
  isAllowedFileSchemeAccess: function (fn) {
    return chrome.extension.isAllowedFileSchemeAccess(fn);
  },
});

browserExtension.listen(window);
chrome.runtime.onInstalled.addListener(onInstalled);
chrome.runtime.requestUpdateCheck(function (status) {
  chrome.runtime.onUpdateAvailable.addListener(onUpdateAvailable);
});

/**
 * Expose the HypothesisChromeExtension instance
 * for debugging purposes.
 */
window.HypothesisChromeExtension = browserExtension;

function onInstalled(installDetails) {
  if (installDetails.reason === 'install') {
    browserExtension.firstRun();
  }

/*
  temporarily disabled whilst investigating whether it is possible
  to create a Chrome extension which does not ask for scary permissions.
  See https://trello.com/c/nE95ZLr4
  
  // We need this so that 3rd party cookie blocking does not kill us.
  // See https://github.com/hypothesis/h/issues/634 for more info.
  // This is intended to be a temporary fix only.
  var details = {
    primaryPattern: 'https://hypothes.is/*',
    setting: 'allow'
  };
  chrome.contentSettings.cookies.set(details);
  chrome.contentSettings.images.set(details);
  chrome.contentSettings.javascript.set(details);
  */

  browserExtension.install();
}

function onUpdateAvailable() {
  chrome.runtime.reload();
}
