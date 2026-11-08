# J.A.R.V.I.S. V1.1 — Nebula

Assistant personnel Linux en Python/PySide6 pour Omarchy/Hyprland : commandes
françaises, monitoring, projets Rust/Python, sessions et modes Travail/Gaming/Études.
La V1.1 ajoute **Jarvis HUD**, un centre de contrôle à six pages, et modernise
**Jarvis Mini** avec le thème Nebula. La base V1.0 et ses 30 commandes sont conservées.
Les versions suivantes restent planifiées dans [la roadmap](docs/ROADMAP.md).

## Installation et démarrage

Prérequis : Linux, uv, Python 3.13, Git ; Omarchy/Hyprland avec ses dispatchers Lua
pour les actions de bureau. Foot, les éditeurs et les programmes des modes doivent
être installés séparément. Notion doit disposer du lanceur `notion.desktop`.

```bash
cd ~/Projects/jarvis-starter
uv python install 3.13
uv sync
uv run jarvis
```

Le raccourci historique **SUPER+SHIFT+J** utilise `~/.local/bin/jarvis-toggle`.
Le script et `~/.config/hypr/bindings.lua` existants n'ont pas été modifiés ; ils ne
sont pas distribués dans ce dépôt. Sur une nouvelle machine, `uv run jarvis` permet
le démarrage direct ; l'intégration du raccourci est à installer séparément.

## Deux interfaces, un seul assistant

`uv run jarvis` démarre **Mini**, toujours ciblée par SUPER+SHIFT+J. Son bouton
**Ouvrir le HUD** ouvre une seule fenêtre redimensionnable (1180 × 780 par défaut),
sans nouveau processus. La fermeture du HUD le masque ; le bouton Mini réutilise
la même instance. Fermer Mini ferme également le HUD et attend les workers en cours.
Le masquage par le raccourci Hyprland conserve Mini et son historique.

Le HUD propose :

- **Accueil** : CPU/RAM/batterie, mode enregistré, dernier projet et objectif,
  alertes émises depuis le démarrage, actions rapides.
- **Système** : monitoring partagé, graphiques CPU/RAM, tous les capteurs disponibles,
  historique et processus (actualisation à l'ouverture puis toutes les 15 s sur cette
  page visible), diagnostic avancé à la demande.
- **Projets** : recherche Rust/Python, dernière utilisation, objectif, sélection et
  consultation de la branche, du dernier commit et des modifications Git. Le bouton
  d'ouverture utilise `ouvre projet NOM` ; un nom ambigu reste refusé par le moteur.
- **Sessions** : projet actif, sauvegarde, date, objectif, fichiers suivis, historique,
  sauvegarde et restauration via les commandes existantes.
- **Modes** : profils et applications prévues, dernier mode enregistré et dernière
  demande de cette exécution, boutons d'activation. Études conserve `gtk-launch notion`.
- **Paramètres** : configuration métier en lecture seule, animations, intervalle du
  monitoring, version, raccourcis et emplacement des logs.

La barre de commandes globale accepte Entrée ; **Ctrl+L** lui rend le focus. Mini
et HUD partagent une seule commande en cours, les réponses et un seul collecteur.
Chaque vue conserve au maximum 500 blocs de réponses en mémoire. Les pages inactives
ne lancent pas de lectures périodiques ; le monitoring continue pour les alertes.

Aucune nouvelle commande textuelle n'est ajoutée : `aide` couvre toujours les
30 commandes. L'ouverture du HUD est une action de fenêtre via le bouton Mini.

### Préférences Nebula

Les animations de navigation (180 ms) et l'intervalle du monitoring (1 à 30 secondes,
2 par défaut) sont appliqués aux interfaces après **Enregistrer et appliquer**.
Ils sont persistés atomiquement dans `data_dir/ui.toml`, séparément du TOML métier :

```toml
animations = true
refresh_seconds = 2
```

Un fichier invalide reste intact et un avertissement apparaît dans Paramètres.
Le monitoring enregistre au plus toutes les dix secondes ; à un intervalle supérieur,
l'enregistrement suit les mesures disponibles. Les alertes demandent toujours trois
mesures consécutives, donc leur délai dépend de l'intervalle choisi.

Le HUD utilise la classe Wayland `jarvis-hud`, Mini conserve `jarvis`. Cette séparation
a été contrôlée nativement sur Qt 6.12 / Hyprland 0.56.2, sans modifier le script ni
les bindings. La recette avec le workspace spécial et le raccourci reste à effectuer
pour la V1.1 ; l'identité distincte dépend du backend **Qt Wayland natif**, pas XWayland.

## Configuration

Les valeurs par défaut conservent `~/Projects`, les bases dans
`~/.local/share/jarvis`, les workspaces **Travail 3**, **Gaming 4**, **Études 5**,
Foot, les éditeurs existants, Chrome, Steam et **`gtk-launch notion`**.

Configuration facultative : copier [config.example.toml](config.example.toml) vers
`~/.config/jarvis/config.toml`, ou choisir un fichier avec `JARVIS_CONFIG` :

```bash
JARVIS_CONFIG="$PWD/config.example.toml" uv run jarvis
```

Redémarrer après modification. Les clés inconnues et workspaces invalides sont
refusés. Le changement de dossier de données ne déplace pas les anciennes bases.
Les programmes sont des noms d'exécutables, sans arguments shell.

## Commandes

`aide` génère le catalogue complet avec exemples et alias. « Jarvis, » est un
préfixe facultatif ; les mots de commande acceptent majuscules et accents. La casse
et les accents des chemins et objectifs sont préservés.

| Domaine | Commandes principales |
| --- | --- |
| Aide | `aide` (`help`, `commandes`) |
| Monitoring | `état système` (`statut`, `status`, `monitoring`, `état du pc`), `processus`, `diagnostic`, `batterie`, `capteurs`, `historique`, `pourquoi mon pc ralentit` |
| Omarchy | `ouvre un terminal`, `passe au workspace 2` (1 à 9 ; bureau/espace acceptés) |
| Projets | `mes projets`, `projets Rust`, `reprends mon projet Rust`, `reprends mon projet Python`, `ouvre projet NOM`, `ouvre rust NOM`, `projet actif`, `état git`, `objectif projet : TEXTE`, `sessions projets` |
| Sessions | `suis le fichier CHEMIN`, `mes fichiers suivis`, `sauvegarde ma session`, `reprends ma session`, `état session` |
| Modes | `mode Travail`, `mode Gaming`, `mode Études`, `mode actuel`, `mes modes` ; `active le mode …` reste accepté |

Exemple de session : `ouvre projet MonProjet`, puis `suis le fichier src/main.rs`,
`objectif projet : Terminer le module`, `sauvegarde ma session` et
`reprends ma session`. Cette dernière rouvre l'environnement et les fichiers
encore présents ; elle ne restaure pas leur contenu et ne modifie pas Git.

La découverte générale ignore les dossiers cachés/build et s'arrête à trois
niveaux. Les commandes Rust historiques conservent leur découverte à un ou deux
niveaux ; `ouvre rust` ne modifie pas le projet actif. Pour les sessions, préférer
`ouvre projet`. Un nom ambigu demande une sélection ; aucun code utilisateur
n'est exécuté ni modifié automatiquement.

## Tests

```bash
uv sync --locked
uv run pytest -q
uv run python -m compileall -q src tests
git diff --check
```

Les tests utilisent des bases et projets temporaires, des mocks pour Hyprland,
Git, les programmes et notifications, et Qt **hors écran** avec le style Fusion.
Ils n'ouvrent ni Steam, ni Chrome, ni Notion et ne modifient pas les workspaces.
Aucun linter n'est configuré dans le projet.

La validation native reste distincte : consulter [VALIDATION.md](docs/VALIDATION.md).
Le résultat des tests et les limites sont consignés avec l'audit dans
[AUDIT_V1.md](docs/AUDIT_V1.md) et [AUDIT_V1_1.md](docs/AUDIT_V1_1.md).

## Données et limites

Les bases `projects.db`, `performance.db`, `memory.sqlite3` et l'état
`active_mode.json` conservent leurs emplacements. Les logs techniques JSON partent
sur stderr ; le script d'ouverture existant les capture dans
`~/.local/state/jarvis.log`. Ils contiennent des identifiants et types d'erreur,
pas le texte des commandes. Les nouveaux historiques de commandes stockent
uniquement l'identifiant et le statut ; les anciennes lignes sont préservées.
Les objectifs et sessions restent des données personnelles locales : ne pas y
saisir de secrets.

Les commandes sont exécutées une à la fois en arrière-plan. Le dashboard collecte
selon la préférence (deux secondes par défaut) et enregistre au plus toutes les dix secondes. La
fermeture attend les tâches en cours. Une application lancée peut échouer après
son démarrage : Jarvis ne garantit pas qu'une fenêtre est apparue. L'état de mode
est persistant : réactiver le même mode change de workspace sans relancer ses apps,
conformément au comportement historique.

Pas d'IA, voix, Spotify, domotique ou autonomie dans cette version.
Voir [ARCHITECTURE.md](docs/ARCHITECTURE.md) pour les responsabilités, la sécurité
et les compromis de compatibilité.
