import json
from pathlib import Path

LOCALES = Path(__file__).resolve().parents[1] / 'locales'

EXTRA = {
    'en': {
        'lesson_back_education': 'Back to Education',
        'lesson_mark_complete': 'Mark as Completed',
        'lesson_completed': "You've completed this lesson!",
        'lesson_next': 'Next Lesson',
        'lesson_back_all': 'Back to All Courses',
        'lesson_track_title': 'Track Your Progress',
        'lesson_track_sub': 'Sign in to mark lessons complete and track your learning journey.',
        'lesson_sign_in_track': 'Sign In to Track Progress',
        'upgrade_hero_title': 'Unlock',
        'upgrade_hero_brand': '27pips Premium',
        'upgrade_already_title': "You're already Premium!",
        'upgrade_already_sub': 'All institutional signals are unlocked. Enjoy the full 27pips experience.',
        'upgrade_back_dashboard': 'Back to Dashboard',
        'upgrade_recommended': 'RECOMMENDED',
        'upgrade_tier_premium': 'Premium',
        'upgrade_current_plan': 'Current Plan',
        'upgrade_cta': 'Upgrade to Premium Now',
        'upgrade_cta_signup': 'Create Account & Upgrade',
        'upgrade_demo_note': 'Simulated upgrade — no payment required for demo',
        'upgrade_social_proof': 'Trusted by traders across Africa and beyond',
        'upgrade_members': 'Active Members',
    },
    'fr': {
        'lesson_back_education': 'Retour à la formation',
        'lesson_mark_complete': 'Marquer comme terminé',
        'lesson_completed': 'Vous avez terminé cette leçon !',
        'lesson_next': 'Leçon suivante',
        'lesson_back_all': 'Retour aux cours',
        'lesson_track_title': 'Suivez votre progression',
        'lesson_track_sub': 'Connectez-vous pour marquer les leçons et suivre votre parcours.',
        'lesson_sign_in_track': 'Connectez-vous pour suivre',
        'upgrade_hero_title': 'Débloquer',
        'upgrade_hero_brand': '27pips Premium',
        'upgrade_already_title': 'Vous êtes déjà Premium !',
        'upgrade_already_sub': 'Tous les signaux institutionnels sont débloqués.',
        'upgrade_back_dashboard': 'Retour au tableau de bord',
        'upgrade_recommended': 'RECOMMANDÉ',
        'upgrade_tier_premium': 'Premium',
        'upgrade_current_plan': 'Plan actuel',
        'upgrade_cta': 'Passer Premium maintenant',
        'upgrade_cta_signup': 'Créer un compte et passer Premium',
        'upgrade_demo_note': 'Mise à niveau simulée — pas de paiement pour la démo',
        'upgrade_social_proof': 'Approuvé par des traders en Afrique et au-delà',
        'upgrade_members': 'Membres actifs',
    },
    'rw': {
        'lesson_back_education': 'Subira mu Kwiga',
        'lesson_mark_complete': "Shyira nk'byarangiye",
        'lesson_completed': 'Warangije isomo!',
        'lesson_next': 'Isomo rikurikira',
        'lesson_back_all': 'Subira ku masomo yose',
        'lesson_track_title': 'Kurikirana iterambere ryawe',
        'lesson_track_sub': 'Injira kugira ngo wandike isomo nk\'iryarangiye.',
        'lesson_sign_in_track': 'Injira ukurikirane',
        'upgrade_hero_title': 'Fungura',
        'upgrade_hero_brand': '27pips Premium',
        'upgrade_already_title': 'Usanzwe uri Premium!',
        'upgrade_already_sub': 'Amakuru yose y\'inzobere afunguwe.',
        'upgrade_back_dashboard': 'Subira ahabanza',
        'upgrade_recommended': 'BYASABWE',
        'upgrade_tier_premium': 'Premium',
        'upgrade_current_plan': 'Gahunda ubu',
        'upgrade_cta': 'Iyongere Premium ubu',
        'upgrade_cta_signup': 'Fungura konti & iyongere',
        'upgrade_demo_note': 'Iyongera ry\'igerageza — nta wishyura',
        'upgrade_social_proof': 'Byizewe n\'abacuruzi mu Afrika n\'ahandi',
        'upgrade_members': 'Abanyamuryango bakora',
    },
}

for lang, keys in EXTRA.items():
    path = LOCALES / f'{lang}.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data.update(keys)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print('done')
