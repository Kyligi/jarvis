# Validation V1.1 et référence V1.0

## Résultat V1.1

- Base V1.0 : `uv sync --locked` et **120 tests réussis** avant modification.
- V1.1 : `uv run pytest -q` → **147 tests réussis** (dont tous les 120 tests V1.0).
- `uv sync --locked`, `uv run python -m compileall -q src tests`, `git diff --check` : réussis.
- Aucun outil de lint configuré ; aucun lint prétendu exécuté.
- Captures des six pages et de Mini rendues hors écran avec données simulées ;
  revue visuelle et correction des métriques Mini initialement comprimées.
- Contrôle automatisé natif sur **Hyprland 0.56.2 / Qt 6.12**, avec données simulées :
  deux fenêtres du même PID, classes `jarvis` et `jarvis-hud`, conservées après
  fermeture/réouverture du HUD. Aucune activation de mode ni changement de workspace.
- Avertissement non bloquant du portail observé : pas de fichier desktop installé
  pour `jarvis`. Le test de classe et d'ouverture s'est terminé avec succès.

La V1.0 a été déclarée validée manuellement par l'utilisateur. La recette complète
V1.1 ci-dessous **n'a pas été exécutée** par l'agent.

## Recette manuelle V1.1 — à effectuer

- [ ] `uv run jarvis` : Mini Nebula 760 × 680, saisie, historique lisible, chargement,
  erreur compréhensible ; conserver les anciennes réponses après plusieurs commandes.
- [ ] SUPER+SHIFT+J : ouvrir/masquer/réafficher Mini plusieurs fois, centrage, même
  fenêtre et même processus. Refaire avec le HUD ouvert et depuis le workspace spécial.
- [ ] Ouvrir le HUD, le redimensionner, fermer/réouvrir plusieurs fois ; vérifier
  qu'il reste indépendant du ciblage de Mini. Tester « Retour à Mini » avec le
  raccourci si son workspace spécial est masqué.
- [ ] Naviguer au clavier (Tab, flèches, Entrée) sur les six pages ; Ctrl+L puis
  Entrée pour une commande ; vérifier l'historique dans les deux fenêtres.
- [ ] Vérifier l'absence de coupures de texte avec le facteur HiDPI habituel, un
  écran externe et les dimensions minimales. Les pages longues défilent.
- [ ] Accueil : dernier projet, objectif, mode et alertes réellement disponibles.
- [ ] Système : CPU/RAM/disque/batterie, capteurs, graphiques, historique et processus ;
  diagnostic pendant le monitoring sans blocage de navigation.
- [ ] Projets : recherche, sélection, branche/commit/modifications, dernière utilisation,
  ouverture Rust/Python ; noms ambigus refusés sans ouverture du mauvais projet.
- [ ] Sessions : sauvegarder puis restaurer un projet de test, vérifier fichiers,
  date, objectif, historique ; aucun fichier source modifié.
- [ ] Modes : Travail 3, Gaming 4, Études 5 (ou valeurs TOML configurées) ; vérifier
  Chrome et Notion via `gtk-launch notion`, sans fermeture automatique d'applications.
- [ ] Paramètres : désactiver/réactiver les animations, changer l'intervalle, enregistrer,
  vérifier l'effet immédiat dans les deux vues et la persistance après redémarrage.
- [ ] Fermer le HUD pendant une lecture : Mini reste active ; fermer Mini pendant
  une commande : sortie propre après attente du worker, puis relancer normalement.

## Couverture automatisée V1.1

Création/navigation ; données simulées et absence de données ; ouverture depuis
Mini ; instance unique après cycles de fermeture ; partage collecteur/bus ; refus
des commandes concurrentes ; historique ; accès aux services hors GUI ; pages
inactives ; reprise de l'historique du graphe ; erreurs/retry ; préférences invalides,
écriture atomique, échec disque, application immédiate ; distinction mode demandé/
enregistré ; alertes réellement émises ; rendu de toutes les pages. Les tests
utilisent des chemins temporaires et interdisent les processus externes non simulés.

## Automatisation V1.0 conservée

Les tests sont exécutables avec `uv run pytest -q` après `uv sync`. Ils couvrent :

- résolution des 30 commandes, tous leurs exemples et alias, préfixes et paramètres ;
- génération de l'aide, absence d'identifiants/alias ambigus, dispatch et erreurs ;
- découverte des projets, noms ambigus, objectifs, Git en lecture seule ;
- fichiers suivis, confinement des chemins et symlinks, sauvegarde/restauration ;
- trois modes, workspaces historiques, `gtk-launch notion`, non-relancement ;
- trois formes Lua, retours d'erreur même avec code de sortie nul ;
- configuration, transactions SQLite, fermeture, rollback et données existantes ;
- capteurs ASUS, batterie absente, processus disparus, historique et alertes ;
- cadence d'enregistrement et panne de stockage ;
- rendu Qt hors écran, métriques/graphe, collecte en erreur, commandes sur worker,
  boucle GUI réactive et refus des tâches concurrentes.

Le rendu hors écran n'est **pas** une validation native Wayland/Hyprland.
Aucun test n'écrit dans les bases réelles ou ne lance une application réelle.

## Recette de référence V1.0

Liste historique conservée comme référence de non-régression. La validation globale
V1.0 a été rapportée par l’utilisateur ; ces cases ne représentent pas des actions
réalisées par l’agent pendant V1.1.

- [ ] Depuis l'environnement uv, démarrer Jarvis ; vérifier titre, taille et absence
  de message d'erreur dans `~/.local/state/jarvis.log` si lancé via le script.
- [ ] SUPER+SHIFT+J : première ouverture, centrage, masquage, réaffichage, plusieurs
  cycles, absence de doublon de processus/fenêtre ; vérifier la classe `jarvis`.
- [ ] `aide`, quelques alias accentués et préfixés « Jarvis, » ; vérifier le catalogue.
- [ ] `passe au workspace 2` : confirmer la syntaxe Lua sur la version installée.
- [ ] Mode Travail : workspace 3, éditeur et Foot, projet actif reconnu ; nouvelle
  activation sans duplication des applications.
- [ ] Mode Gaming : workspace 4 et Steam ; les tests automatisés n'ont pas lancé Steam.
- [ ] Mode Études : workspace 5, Chrome et **Notion via `gtk-launch notion`**.
- [ ] Ouvrir un projet de test Rust puis Python ; vérifier Git, objectif, reprise
  après redémarrage. Ne pas utiliser de commande Git destructive.
- [ ] Suivre un fichier accentué/avec espaces, sauvegarder, reprendre la session :
  workspace 3, éditeur et terminal dans le bon dossier, objectif et état Git affichés.
- [ ] Supprimer ou déplacer un fichier de test suivi : la reprise ignore le fichier
  absent. Vérifier le refus d'un fichier hors projet.
- [ ] Vérifier les données historiques des bases existantes : objectifs, sessions,
  historique des performances ; aucune migration manuelle requise par défaut.
- [ ] Vérifier CPU/RAM/disque/batterie et capteurs `k10temp`, `amdgpu`, `nvme`,
  `mt7921_phy0`, `acpitz` selon leur disponibilité ; graphe et rafraîchissement 2 s.
- [ ] Exécuter `processus`, `diagnostic` et le diagnostic avancé pendant le monitoring :
  vérifier que déplacement et masquage de la fenêtre restent réactifs.
- [ ] Vérifier les notifications avec des mesures simulées dans les tests ; ne pas
  provoquer volontairement de surchauffe/saturation pour cette recette.
- [ ] Fermer pendant une commande ; vérifier la sortie propre après sa fin, puis
  relancer avec le raccourci. Pas d'interruption forcée des workers en V1.0.

## Limites explicites

La compatibilité native des dispatchers et des lanceurs dépend de l'installation.
Les syntaxes historiques ont été conservées et testées par inspection des arguments,
sans changer le bureau pendant la validation automatique. Les capteurs réels et
l'apparition effective des fenêtres doivent être contrôlés sur la machine.
Le résultat d'un diagnostic est ponctuel, pas une preuve de l'origine d'un problème.
