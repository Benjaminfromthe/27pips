/**
 * 27pips — Theme module (system preference + manual override + persistence).
 * Depends on theme-init.js loaded in <head>.
 */
(function (global) {
  'use strict';

  var api = global.__PIPS_THEME__;
  if (!api) {
    api = {
      STORAGE_KEY: 'pips_theme',
      systemTheme: function () {
        return global.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
      },
      resolveTheme: function () { return 'dark'; },
      applyTheme: function (theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.style.colorScheme = theme;
      }
    };
  }

  var STORAGE_KEY = api.STORAGE_KEY;
  var media = global.matchMedia('(prefers-color-scheme: light)');

  function hasManualOverride() {
    try {
      var stored = global.localStorage.getItem(STORAGE_KEY);
      return stored === 'light' || stored === 'dark';
    } catch (e) {
      return false;
    }
  }

  function getStoredOverride() {
    try {
      return global.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function getTheme() {
    return api.resolveTheme();
  }

  function setTheme(theme, persist) {
    if (theme !== 'light' && theme !== 'dark') return;
    api.applyTheme(theme);
    if (persist !== false) {
      try {
        global.localStorage.setItem(STORAGE_KEY, theme);
      } catch (e) { /* ignore */ }
    }
    updateToggleUI(theme);
  }

  function toggleTheme() {
    var next = getTheme() === 'dark' ? 'light' : 'dark';
    setTheme(next, true);
  }

  function clearOverride() {
    try {
      global.localStorage.removeItem(STORAGE_KEY);
    } catch (e) { /* ignore */ }
    var resolved = api.systemTheme();
    api.applyTheme(resolved);
    updateToggleUI(resolved);
  }

  function updateToggleUI(theme) {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;

    var isDark = theme === 'dark';
    btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    btn.setAttribute(
      'aria-label',
      isDark ? 'Switch to light mode' : 'Switch to dark mode'
    );
    btn.setAttribute('title', isDark ? 'Light mode' : 'Dark mode');
    btn.dataset.theme = theme;
  }

  function enableTransitions() {
    var root = document.documentElement;
    if (global.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      root.classList.add('theme-ready');
      return;
    }
    root.classList.remove('no-theme-transition');
    root.classList.add('theme-ready');
  }

  function onSystemChange() {
    if (!hasManualOverride()) {
      var resolved = api.systemTheme();
      api.applyTheme(resolved);
      updateToggleUI(resolved);
    }
  }

  function init() {
    var theme = getTheme();
    api.applyTheme(theme);
    updateToggleUI(theme);

    var btn = document.getElementById('themeToggle');
    if (btn && !btn.dataset.bound) {
      btn.dataset.bound = '1';
      btn.addEventListener('click', toggleTheme);
    }

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onSystemChange);
    } else if (typeof media.addListener === 'function') {
      media.addListener(onSystemChange);
    }

    requestAnimationFrame(function () {
      requestAnimationFrame(enableTransitions);
    });
  }

  global.PipsTheme = {
    getTheme: getTheme,
    setTheme: setTheme,
    toggleTheme: toggleTheme,
    clearOverride: clearOverride,
    hasManualOverride: hasManualOverride,
    getStoredOverride: getStoredOverride
  };

  global.toggleTheme = toggleTheme;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
