# Roadmap J.A.R.V.I.S. V1.0–V2.0

Les versions suivent l'ordre ci-dessous : V1.10 vient après V1.9.
Seule la V1.0 est implémentée dans ce chantier. Les autres lignes sont des objectifs,
pas des fonctionnalités disponibles. Chaque version conserve les acquis et leurs tests.

| Version | Objectif | Critères d'acceptation |
| --- | --- | --- |
| V1.0 | Architecture, commandes centralisées, stabilité | Catalogue unique avec identifiants, catégories, handlers, alias et aide générée ; tests des formulations historiques ; configuration conservant les valeurs actuelles ; SQLite compatible ; commandes et collecte hors thread graphique ; validation manuelle Omarchy sans régression. |
| V1.1 | Interface Jarvis HUD | Maquette approuvée ; lisibilité et navigation clavier ; états chargement/erreur accessibles ; monitoring et commandes historiques utilisables sans perte de fonctions. |
| V1.2 | Contrôle avancé des fenêtres Hyprland | Inventaire et ciblage explicite des fenêtres ; déplacements et dispositions testés sur les dispatchers Lua installés ; erreurs de cible gérées ; raccourcis existants préservés. |
| V1.3 | Modes et scénarios personnalisables | Profils éditables et validés ; actions autorisées uniquement ; prévisualisation avant activation ; modes Travail/Gaming/Études importés sans changement de workspaces. |
| V1.4 | Assistant vocal local | Reconnaissance et synthèse locales ; activation/désactivation explicite du microphone ; indication visible ; aucun envoi audio externe par défaut ; confirmation des actions sensibles. |
| V1.5 | IA conversationnelle et outils autorisés | Séparation conversation/exécution ; outils en liste d'autorisation ; paramètres validés ; gestion des erreurs et injections de consignes ; secrets hors prompts et logs ; confirmation selon risque. |
| V1.6 | Mémoire personnelle avancée | Consultation, correction, export et suppression explicites ; provenance et durée de conservation ; migration compatible des objectifs et sessions ; informations sensibles maîtrisées. |
| V1.7 | Recherche fichiers et documents | Répertoires choisis par l'utilisateur ; exclusions respectées ; résultats avec chemin et extrait ; index incrémental ; aucun accès hors périmètre ni modification des documents. |
| V1.8 | Assistant développeur Rust/Python/Git | Détection des outils et environnements ; diagnostics reproductibles ; modifications présentées comme diffs à approuver ; aucune commande Git destructrice automatique ; tests en projets temporaires. |
| V1.9 | Spotify / MPRIS | Détection du lecteur actif ; lecture/pause et navigation explicitement demandées ; absence de lecteur gérée ; authentification si nécessaire sans secret dans les logs. |
| V1.10 | Home Assistant, éclairage et routines compatibles | Connexion configurable ; découverte des entités réellement disponibles ; commandes bornées aux capacités autorisées ; fonctionnement dégradé hors réseau ; routines testées sur appareils simulés avant usage réel. |
| V1.11 | Télécommande smartphone | Appairage explicite ; authentification et chiffrement ; révocation d'un appareil ; commandes autorisées identiques au desktop ; aucune exposition publique implicite. |
| V1.12 | Automatisations intelligentes | Déclencheurs et actions visibles ; simulation avant activation ; anti-boucle et limites de fréquence ; arrêt global ; historique sans données sensibles. |
| V1.13 | Sécurité, sauvegardes et diagnostics système | Sauvegardes vérifiées par restauration ; politique de rétention ; diagnostic en lecture seule par défaut ; tests des droits et des limites d'accès ; revue de sécurité documentée. |
| V2.0 | Proactivité et autonomie contrôlée | Suggestions explicables ; périmètre d'autonomie choisi par l'utilisateur ; budgets et arrêt immédiat ; approbation des actions à risque ; traçabilité, récupération après erreur et tests des refus. |

## Barrière de validation

Une version n'est pas déclarée validée uniquement parce que les tests simulés passent.
Pour V1.0, la recette native de [VALIDATION.md](VALIDATION.md) reste à effectuer par
l'utilisateur sur Omarchy, notamment SUPER+SHIFT+J, les trois syntaxes Lua historiques
et les lanceurs réels. Aucun travail V1.1+ n'est requis pour cette recette.
