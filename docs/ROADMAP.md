# Roadmap J.A.R.V.I.S. V1.0–V2.0

Les versions suivent l'ordre ci-dessous : V1.10 vient après V1.9.
V1.0 est validée manuellement par l’utilisateur. V1.1 est implémentée ; sa recette
native complète reste à faire. V1.2–V2.0 sont des objectifs, pas des fonctionnalités disponibles. Chaque version conserve les acquis et leurs tests.

| Version | Objectif | Critères d'acceptation |
| --- | --- | --- |
| V1.0 | Architecture, commandes centralisées, stabilité | Catalogue unique avec identifiants, catégories, handlers, alias et aide générée ; tests des formulations historiques ; configuration conservant les valeurs actuelles ; SQLite compatible ; commandes et collecte hors thread graphique ; validation manuelle Omarchy sans régression. |
| V1.1 | Interface Jarvis HUD | Mini Nebula et HUD à six pages connectées ; monitoring et moteur partagés ; navigation clavier et états chargement/erreur ; préférences persistées ; tests hors écran ; validation manuelle déclarée par l’utilisateur au début du chantier V1.2. |
| V1.2 | Contrôle avancé des fenêtres Hyprland | Implémentée : inventaire, service central, 20 commandes, septième page HUD, placements flottants, dispositions confirmées, protections Jarvis, modes sans duplication applicative ; constructeurs Lua vérifiés sur 0.56.2. Recette native V1.2 à effectuer. |
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
La V1.0 a été déclarée validée manuellement par l'utilisateur au lancement du chantier
V1.1. Pour la V1.1, voir la nouvelle recette dans [VALIDATION.md](VALIDATION.md) :
les tests hors écran et le contrôle natif ciblé des identités ne remplacent pas
la validation du raccourci, des applications et de l'utilisation quotidienne.
La V1.1 est déclarée validée manuellement par l’utilisateur. La V1.2 reste à valider
sur le bureau réel ; aucune fonctionnalité V1.3+ n’est implémentée.
