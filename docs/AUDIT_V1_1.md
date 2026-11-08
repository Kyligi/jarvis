# Livraison V1.1 — Jarvis HUD / Nebula

## Inspection et périmètre

Base inspectée : commits `a090a23`, `2e60e50`, arbre Git propre au début.
Lecture du README, de l'architecture, de la roadmap, de la validation et de l'audit
V1.0 ; inspection des widgets, workers, services et tests. Le script
`~/.local/bin/jarvis-toggle` et le binding SUPER+SHIFT+J ont été lus, non modifiés.
Aucune donnée utilisateur ni sauvegarde dans `backups/` n'a été modifiée.
La base passe 120 tests avant intervention et sa validation manuelle est confirmée
par l'utilisateur dans la mission.

## Implémentation

- Thème Nebula centralisé : fond/surfaces, cyan/violet, cartes, typographie,
  sélection/focus clavier, transition d'opacité de 180 ms désactivable.
- Mini conserve son identité, dimensions, commande et monitoring ; bouton HUD,
  réponses successives et indication d'exécution. Disposition compacte des métriques.
- HUD redimensionnable, navigation Accueil/Système/Projets/Sessions/Modes/Paramètres,
  lectures réelles via services, console globale, Ctrl+L, pages défilantes.
- Un contexte partagé, un collecteur périodique, un bus de commandes, un seul HUD
  réutilisé ; aucune création de processus à l'ouverture du HUD.
- Monitoring V1.0 réutilisé ; cache de 60 échantillons pour réafficher le graphe.
  Historique/processus à l'ouverture de Système puis toutes les 15 s tant que visible.
- Git à la sélection d'un projet, hors GUI ; recherche locale, mémoire projet,
  reprise via la commande enregistrée. Les noms ambigus conservent leur refus sûr.
- Sessions et modes utilisent les services et commandes existants ; aucune logique
  nouvelle de lancement ou d'édition des projets, Notion inchangé.
- Préférences dans `data_dir/ui.toml`, validation, fichier temporaire/fsync/remplacement,
  erreurs visibles et runtime inchangé si écriture échoue. TOML métier en lecture seule.
- Mémoire bornée des 20 alertes émises depuis le démarrage ; aucun changement de schéma.
- Les 30 commandes et leurs alias restent inchangés ; seule la version affichée par
  l'aide suit désormais les métadonnées du paquet. Pas de commande HUD supplémentaire.

## Fichiers

Nouveaux : `interface/{theme,components,context,hud}.py`, `interface/pages/*`,
`preferences.py`, `services/{__init__,overview}.py`, `tests/test_hud.py`,
`tests/test_overview.py`, `tests/test_ui_preferences.py`, ce document.

Modifiés : `interface/{mini,dashboard}.py`, `monitoring/{collector,intelligence}.py`,
`registry.py` (version de l'aide uniquement), `tests/conftest.py`,
`tests/test_monitoring.py`, `pyproject.toml`, `uv.lock`, `README.md`,
`docs/{ARCHITECTURE,ROADMAP,VALIDATION}.md`.

## Validation

- `uv sync --locked` avant et après mise à jour de version : réussi.
- `uv sync` pour passer les métadonnées du paquet de 1.0.0 à 1.1.0 : réussi,
  aucune nouvelle dépendance.
- `uv run pytest -q` : **147 tests réussis**, dont les 120 historiques.
- `uv run python -m compileall -q src tests` : réussi.
- `git diff --check` : réussi. Aucun linter configuré.
- Rendu Qt hors écran des six pages et de Mini avec données simulées ; captures
  inspectées, métriques Mini corrigées et actions principales remontées avant les
  zones défilantes. Ces captures ne sont pas des mesures du PC réel.
- Test automatisé natif ciblé sur Qt 6.12 / Hyprland 0.56.2 : lecture `hyprctl clients -j`,
  deux fenêtres du même PID, classes `jarvis` et `jarvis-hud`, mêmes identités après
  fermeture/réouverture. Test terminé, fenêtres de test fermées. Aucune application
  externe, notification, commande de mode, ni déplacement de workspace exécutés.

La recette complète V1.1 reste à effectuer dans [VALIDATION.md](VALIDATION.md).

## Limites connues

- La séparation des classes est vérifiée avec Qt Wayland natif. Le script n'est pas
  adapté à XWayland ; ne pas forcer `QT_QPA_PLATFORM=xcb` pour cette intégration.
- L'ouverture depuis le workspace spécial et le cycle complet SUPER+SHIFT+J nécessitent
  la recette utilisateur ; le test natif a eu lieu sur le workspace courant normal.
- « Retour à Mini » masque le HUD et demande le focus de Mini ; si son workspace
  spécial est masqué, utiliser SUPER+SHIFT+J. Aucun contrôle avancé Hyprland ajouté.
- Pas d'installation automatique de fichier desktop ; avertissement du portail Qt
  possible pour `jarvis`, sans échec des fenêtres dans le test réalisé.
- Les préférences peuvent ralentir la détection des alertes en augmentant l'intervalle
  (trois mesures consécutives requises). Les alertes affichées ne survivent pas au
  redémarrage. La mémoire des réponses est limitée à 500 blocs par console.
- Les lectures déjà engagées finissent après changement de page. Fermer Mini attend
  les workers ; un disque lent peut retarder la sortie, comme en V1.0.
- Les services V1.0 signalent le lancement demandé, pas l'apparition effective d'une
  application ; aucune nouvelle garantie de supervision des processus n'est ajoutée.
- Aucun travail V1.2+ : voix, LLM, Spotify, domotique, mobile et autonomie exclus.
