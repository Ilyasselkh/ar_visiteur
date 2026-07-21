{
    "name": "AR - Visiteur",
    "version": "1.0.0",
    "summary": "Gestion des visiteurs",
    "description": """
Module de gestion des visiteurs :
- Enregistrement des entrées visiteurs
- Suivi des sorties
- Archive des visites terminees
- Affichage d'un PDF d'accueil paramétré
    """,
    "author": "AR IT Department",
    "category": "Operations",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "survey",
    ],
    "data": [
        "data/sequence.xml",
        "data/mail_templates.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/ar_visiteur_quiz_wizard_views.xml",
        "views/ar_visiteur_signature_wizard_views.xml",
        "views/ar_visiteur_views.xml",
        "views/ar_visiteur_config_views.xml",
        "views/ar_visiteur_quiz_result_views.xml",
        "views/ar_visiteur_menu.xml",
        "reports/report_araymond_layout.xml",
        "reports/ar_visiteur_signed_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ar_visiteur/static/src/scss/ar_visiteur.scss",
            "ar_visiteur/static/src/js/ar_visiteur_quiz_iframe.js",
        ],
        "web.assets_frontend": [
            "ar_visiteur/static/src/scss/ar_visiteur_survey.scss",
            "ar_visiteur/static/src/js/ar_visiteur_survey.js",
        ],
    },
    "application": True,
    "installable": True,
}
