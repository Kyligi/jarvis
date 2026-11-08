# Audit V1.2 — 8 novembre 2026

## Avant modification

- Dépôt propre, HEAD `c9152c2` (documentation V1.1), implémentation V1.1
  `45d1467`, base registre/services V1.0 `a090a23`. Aucun reset/rebase/clean.
- README, ARCHITECTURE, ROADMAP et VALIDATION lus ; six pages HUD, DataPage et
  CommandBus partagés, workers V1.0, registre à aide générée examinés.
- `uv sync --locked` et référence pytest : **147 succès**.
- Pas de linter ni de plugin de couverture configuré. Tests existants : registre,
  monitoring, données, projets/sessions, modes, workers Qt, HUD et préférences.
- Intégration existante : `integrations/desktop.py` possède les trois formes Lua
  de focus workspace ; modes, sessions et omarchy y font appel directement.
- `~/.local/bin/jarvis-toggle` lu uniquement : classe jarvis, float/resize/move/center,
  workspace spécial et toggle Lua. Aucun changement au script ou aux raccourcis.
- Version native : Hyprland 0.56.2. Sources Omarchy installées lues :
  `workspace-modes.lua`, `monitor-workspaces.lua`, `bindings/tiling.lua` et stubs Lua.
  Elles confirment float on/off, déplacement par adresse, géométrie absolue,
  focus et navigation m+1/m-1. Assertions des constructeurs effectuées sans dispatch.
- `notion.desktop` lu : lancement webapp Omarchy, StartupWMClass spécifique Chrome.
  Le lancement métier `gtk-launch notion` est préservé.

## Plan exécuté

1. Inventaire, modèles de fenêtre, validations, construction Lua et service central.
2. Commandes, choix ambigu par adresse, plans de disposition et confirmation éphémère.
3. Page Fenêtres Nebula, lectures asynchrones, actions typées sur le bus partagé.
4. Modes avec détection des applications déjà ouvertes ; workspaces centralisés pour
   les anciennes commandes et les sessions, sans remplacer leurs formes Lua.
5. Tests simulés, vérifications, documentation et commits locaux sans push.

Les résultats et la recette native restante sont dans [VALIDATION.md](VALIDATION.md).
Aucune fonctionnalité V1.3+ ajoutée ; aucun déplacement réel réalisé pendant les tests.
