# Audit et livraison V1.0 — 8 novembre 2026

## Point de départ constaté

Historique Git inspecté : `1d1be82` (initialisation), `b748fe6` (dashboard V0.5),
`cb6cdcc` (monitoring V0.6), `2235883` (projets V0.7). Les diffs du dashboard,
les statistiques des étapes V0.6/V0.7 et le diff local ont été consultés.
Il n'existe pas de commit V0.8/V0.9 dans cet historique au début de l'intervention.

Modifications préexistantes : `core/commands.py`, `registry.py`, répertoire
`modes/`, `projects/commands.py`, `projects/sessions.py`, et `backups/` non suivi.
Les fonctions V0.8/V0.9 ont été intégrées à la refonte ; les sauvegardes sont
laissées intactes, hors commits. Une copie du source initial et du diff a été
conservée dans `/tmp/jarvis-before-v1-src` et `/tmp/jarvis-before-v1.patch` pendant
l'intervention. Ces copies temporaires ne constituent pas une sauvegarde durable.
Aucun reset, clean, rebase, push, changement des bindings ou du script toggle.

`pyproject.toml` annonçait encore 0.1.0 ; dépendances PySide6/psutil, Python 3.13,
verrou uv présent. `tests/` était vide et aucun lint n'était configuré.
Les fichiers Python, configurations et documentation du dépôt ont été inspectés.
Le script externe `~/.local/bin/jarvis-toggle` et le binding SUPER+SHIFT+J ont été lus.

## Constats et traitement

| Constat | Traitement V1.0 |
| --- | --- |
| Cascade modes → sessions → projets → registre → système → ancien routeur | Catalogue unique et résolution sans effets de bord ; adaptateurs d'import pour les anciens points d'entrée |
| Registre servant surtout à l'aide, nombreux handlers absents, aide incomplète | 30 commandes avec identifiants, catégories, exemples, alias et handlers ; aide produite par le registre |
| Dépendance sessions/modes vers la normalisation du registre | Normalisation extraite dans `core/text.py` ; pas de cycle d'import statique |
| Préfixe `Jarvis :` pouvant contaminer un objectif | Préfixe retiré avant extraction ; conservation du texte original |
| Git, découverte, échantillonnage et SQLite sur le thread GUI | Workers indépendants, commande unique et collecte sans chevauchement ; slots GUI pour l'affichage |
| Connexions SQLite historique/performances sans fermeture explicite | Primitive partagée de transaction et fermeture ; schémas/emplacements inchangés |
| Erreurs génériques, silencieuses ou imprimées sans structure | Logs JSON avec identifiant et type ; erreurs visibles dans l'interface, avertissement stockage |
| Historique enregistrant potentiellement du texte sensible | Nouvelles lignes limitées à identifiant/statut ; anciennes données conservées |
| Chemins, programmes et workspaces dispersés | TOML facultatif validé, valeurs historiques par défaut |
| Mode Travail faisant confiance au chemin mémorisé | Validation contre la découverte des projets avant lancement |
| JSON de session non validé | Validation de la liste de fichiers avant restauration |
| SQLite sûr et subprocess sans shell déjà présents par endroits | Conservation et consolidation ; Git limité aux trois requêtes de lecture |
| Trois formes Lua différentes dans le code | Intégration unique conservant ces trois formes ; tests exacts ; validation native restant à faire |
| Monitoring ancien et lecture Git dupliqués | Réexport du monitoring ; lecture Git commune |
| Deux politiques de découverte Rust | Maintien intentionnel des comportements historiques, documenté |

## Changements livrés

- `registry.py`, `core/*`, adaptateurs `commands.py` : routage, aide et frontière d'erreurs.
- `config.py`, `config.example.toml` : configuration locale sans modification automatique d'Omarchy.
- `persistence/*`, `memory/database.py`, services projets/monitoring : gestion SQLite commune.
- `integrations/*`, `omarchy.py` : dispatchers Lua conservés et requêtes Git autorisées.
- `interface/*`, `monitoring/collector.py`, `main.py` : tâches Qt, collecte et identité `jarvis`.
- `projects/*`, `modes/*`, `modules/*` : fonctionnalités historiques préservées, contrôles renforcés.
- `logging_setup.py` : journaux structurés sans contenu des commandes.
- `tests/*` : unités et intégration simulée ; `pyproject.toml`/`uv.lock` : V1.0 et pytest en développement.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/VALIDATION.md` : usage, architecture, versions futures et recette.

## Validation exécutée

Résultats exécutés sur le code du commit `a090a23` :

| Vérification | Résultat |
| --- | --- |
| `uv sync` | Réussi ; dépendances installées et verrou mis à jour (cache uv autorisé hors sandbox) |
| `uv sync --locked` | Réussi ; 14 packages résolus, 13 vérifiés |
| `.venv/bin/python -m pytest -q` | **120 tests réussis** en 0,33 s |
| `.venv/bin/python -m compileall -q src tests` | Réussi, code de sortie 0 |
| `git diff --check` | Réussi, aucune erreur d'espacement |
| Qt | Tests de rendu et de réactivité exécutés hors écran, thème Fusion |
| Lint | Non exécuté : aucun linter configuré |
| Omarchy natif, programmes et matériel | Non exécutés : recette manuelle restante |

Le premier essai Qt a rencontré le thème GTK de la session ; les tests fixent
explicitement le backend hors écran et le thème Fusion pour éviter toute dépendance
à l'affichage natif. Les tests finaux ont tous été réellement exécutés.
La recette native reste distincte, et toutes ses cases dans `VALIDATION.md` restent
à effectuer. Aucun push n'a été effectué.

## Risques et limites conservés

- La fermeture peut attendre une commande en cours (Git a un timeout de cinq secondes
  par requête, mais une découverte sur un stockage lent peut durer davantage).
- Les applications sont lancées sans attendre leur fenêtre ; une activation partielle
  ne peut pas être annulée automatiquement. Le dernier mode mémorisé n'est pas une
  détection des applications réellement ouvertes.
- Les deux découvertes de projets ne sont volontairement pas fusionnées ; la route
  Rust historique peut également voir des dossiers cachés au premier niveau.
- La mémoire métier contient les objectifs/fichiers/Git souhaités par l'utilisateur ;
  la V1.0 ne chiffre pas les bases et ne purge pas les anciens historiques.
- Les capteurs absents sont signalés ; pas de simulation présentée comme une validation
  matérielle. La notification système dépend de `notify-send`.
- Les versions V1.1–V2.0 sont documentées uniquement.
