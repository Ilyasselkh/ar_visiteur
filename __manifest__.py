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
    ],
    "data": [
        "data/sequence.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/ar_visiteur_views.xml",
        "views/ar_visiteur_config_views.xml",
        "views/ar_visiteur_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ar_visiteur/static/src/scss/ar_visiteur.scss",
        ],
    },
    "application": True,
    "installable": True,
}
