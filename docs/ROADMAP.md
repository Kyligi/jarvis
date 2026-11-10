# Livraison V1.5 — 10 novembre 2026

- Implémenté : adaptateur Ollama loopback, JSON strict, streaming, arrêt et timeout.
- Implémenté : 17 outils métier, provenance, confirmation IA puis validations historiques.
- Implémenté : mémoire limitée à la session et effacement, sans persistance.
- Implémenté : Assistant dixième page Nebula, Mini conservée, pipeline vocal partagé.
- Livré : tests simulés, intégration Ollama et benchmark facultatifs, documentation.
- À valider après installation volontaire : qualité française qwen3:4b, accélération
  effective Ollama/Vulkan, latences et contention mémoire avec Whisper.
- Non commencé : mémoire personnelle V1.6, recherche V1.7, Spotify V1.9, domotique
  V1.10, téléphone V1.11, automatisations proactives V1.12.

La disponibilité matérielle Vulkan a été vérifiée ; aucun modèle LLM installé.
Voir [V1.5](AI_V1_5.md) et [validation](VALIDATION.md).

---

# Roadmap J.A.R.V.I.S. V1.0–V2.0

Les versions suivent l’ordre ci-dessous : V1.10 vient après V1.9.
V1.0, V1.1 et V1.2 sont déclarées validées manuellement par l’utilisateur.
V1.3 est implémentée et testée automatiquement ; sa recette native reste à faire.
V1.4.2 est livrée et fonctionnelle selon le contexte utilisateur. V1.5 est
implémentée et validée automatiquement ; sa recette LLM réelle reste à faire.
V1.6–V2.0 restent des objectifs.

| Version | Objectif | Critères d'acceptation |
| --- | --- | --- |
| V1.0 | Architecture, commandes centralisées, stabilité | Catalogue unique avec identifiants, catégories, handlers, alias et aide générée ; tests des formulations historiques ; configuration conservant les valeurs actuelles ; SQLite compatible ; commandes et collecte hors thread graphique ; validation manuelle Omarchy sans régression. |
| V1.1 | Interface Jarvis HUD | Mini Nebula et HUD à six pages connectées ; monitoring et moteur partagés ; navigation clavier et états chargement/erreur ; préférences persistées ; tests hors écran ; validation manuelle déclarée par l’utilisateur au début du chantier V1.2. |
| V1.2 | Contrôle avancé des fenêtres Hyprland | Implémentée : inventaire, service central, 20 commandes, septième page HUD, placements flottants, dispositions confirmées, protections Jarvis, modes sans duplication applicative ; constructeurs Lua vérifiés sur 0.56.2. Validation native déclarée par l’utilisateur au lancement de V1.3. |
| V1.3 | Modes et scénarios personnalisables | Implémentée : huit actions typées, JSON atomique versionné, CRUD HUD, simulation, confirmations, exécution en worker, annulation, historique borné, profils persistants et 59 commandes. Modes historiques préservés. Recette native V1.3 à effectuer. |
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

Une version n’est pas déclarée validée nativement uniquement parce que les tests
simulés passent. Les validations V1.0–V1.2 ont été déclarées par l’utilisateur au
lancement de cette mission. Les tests hors écran V1.3 et la revue des captures ne
remplacent pas les vérifications du raccourci, des fenêtres, des applications et
des sessions sur le bureau Omarchy. Suivre [VALIDATION.md](VALIDATION.md).

## Historique V1.4 — implémentation vocale locale (9 novembre 2026)

- Livré : adaptateurs PipeWire/whisper.cpp CPU/Piper OHF, service sans Qt,
  états, annulation, transcription et validation visible, registre commun,
  commandes vocales, Mini/HUD, paramètres privés, IPC push-to-talk optionnel.
- Automatisation : périphériques simulés, garde wake word sans moteur actif,
  tests de non-régression et générateur explicite de corpus français.
- À valider matériellement : moteurs et voix installés volontairement, français,
  latences/RAM/CPU, comportement micro/sortie, raccourci natif et fin de processus.
- Non livré : écoute continue openWakeWord, hold-to-talk, accélération Vulkan,
  réutilisation du modèle chargé, corpus WAV déjà généré. Ces points ne sont pas
  marqués terminés. Le guide VOICE décrit les raisons et la recette.
- À cette étape V1.4, V1.5 n’était pas commencée. Elle est maintenant livrée
  logiciellement selon le bilan en tête de cette page ; Vulkan Whisper a été
  livré entre-temps en V1.4.2 (voir VOICE_V1_4_2.md).
