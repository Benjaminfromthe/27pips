/**
 * 27pips — Blocking theme bootstrap (load in <head> before CSS).
 * Applies saved or system preference immediately to prevent flash.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY = 'pips_theme';

  function systemTheme() {
    return global.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function resolveTheme() {
    try {
      var stored = global.localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') return stored;
    } catch (e) { /* private browsing */ }
    return systemTheme();
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    root.setAttribute('data-theme', theme);
    root.style.colorScheme = theme;
  }

  applyTheme(resolveTheme());
  document.documentElement.classList.add('no-theme-transition');

  global.__PIPS_THEME__ = {
    STORAGE_KEY: STORAGE_KEY,
    systemTheme: systemTheme,
    resolveTheme: resolveTheme,
    applyTheme: applyTheme
  };
})(window);
