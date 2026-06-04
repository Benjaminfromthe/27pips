# ============================================================
# 27pips — i18n.py  |  JSON locales + session/cookie persistence
# ============================================================
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from flask import Flask, redirect, request, session

LOCALES_DIR = Path(__file__).resolve().parent / 'locales'
SUPPORTED_LANGS = ('en', 'fr', 'rw')
DEFAULT_LANG = 'en'
LANG_COOKIE = 'pips_lang'
LANG_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year

LANG_META = {
    'en': {'label': 'English', 'native': 'English', 'flag': '🇬🇧', 'code': 'EN'},
    'fr': {'label': 'French',  'native': 'Français', 'flag': '🇫🇷', 'code': 'FR'},
    'rw': {'label': 'Kinyarwanda', 'native': 'Kinyarwanda', 'flag': '🇷🇼', 'code': 'RW'},
}


@lru_cache(maxsize=len(SUPPORTED_LANGS) + 1)
def _load_locale(lang: str) -> dict:
    path = LOCALES_DIR / f'{lang}.json'
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as fh:
        return json.load(fh)


def get_translations(lang: str) -> dict:
    """Return merged strings for lang (locale overrides + English fallback)."""
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    base = _load_locale(DEFAULT_LANG)
    if lang == DEFAULT_LANG:
        return dict(base)
    locale = _load_locale(lang)
    return {**base, **locale}


def resolve_language() -> str:
    """Pick language from session, then cookie, then Accept-Language."""
    lang = session.get('lang')
    if lang in SUPPORTED_LANGS:
        return lang

    lang = request.cookies.get(LANG_COOKIE)
    if lang in SUPPORTED_LANGS:
        session['lang'] = lang
        return lang

    best = request.accept_languages.best_match(SUPPORTED_LANGS)
    return best or DEFAULT_LANG


def register_i18n(app: Flask) -> None:
    """Wire language resolution, template helpers, and switch route."""

    @app.before_request
    def _sync_language():
        session['lang'] = resolve_language()

    @app.context_processor
    def _inject_i18n():
        import os
        lang = session.get('lang', DEFAULT_LANG)
        strings = get_translations(lang)

        def t(key: str, fallback: str | None = None, **kwargs) -> str:
            text = strings.get(key, fallback if fallback is not None else key)
            if kwargs:
                try:
                    return text.format(**kwargs)
                except (KeyError, ValueError):
                    return text
            return text

        # email_sandbox_mode = True when RESEND_TEST_EMAIL is set AND
        # RESEND_API_KEY is present. This means emails go to the owner's
        # inbox only — users won't receive them directly.
        from flask import current_app
        resend_key        = current_app.config.get('RESEND_API_KEY',    '').strip()
        resend_test_email = current_app.config.get('RESEND_TEST_EMAIL', '').strip()
        email_sandbox_mode = bool(resend_key and resend_test_email)

        return dict(
            t=t,
            lang=lang,
            supported_langs=SUPPORTED_LANGS,
            lang_meta=LANG_META,
            current_lang_meta=LANG_META.get(lang, LANG_META[DEFAULT_LANG]),
            email_sandbox_mode=email_sandbox_mode,
        )

    @app.route('/lang/<lang_code>')
    def set_language(lang_code: str):
        if lang_code in SUPPORTED_LANGS:
            session['lang'] = lang_code
            session.modified = True
            resp = redirect(request.referrer or '/')
            resp.set_cookie(
                LANG_COOKIE,
                lang_code,
                max_age=LANG_COOKIE_MAX_AGE,
                httponly=True,
                samesite='Lax',
            )
            return resp
        return redirect(request.referrer or '/')
