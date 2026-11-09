# J.A.R.V.I.S. V1.4.1 — Assistant vocal local

Assistant personnel Linux en Python/PySide6 pour Omarchy/Hyprland : commandes
françaises, monitoring, projets Rust/Python, sessions et modes Travail/Gaming/Études.
La V1.3 ajoute un moteur de scénarios à huit actions autorisées, leur éditeur HUD,
la prévisualisation, les confirmations de déplacement, l’annulation coopérative,
l’historique et les modes personnalisables. Les fonctionnalités V1.2 sont conservées.
La V1.4 ajoute le push-to-talk, une page Voix et les adaptateurs locaux PipeWire,
whisper.cpp CPU et Piper OHF. Microphone fermé au démarrage, validation visible
avant commande, interruption et paramètres TOML privés. Les moteurs/modèles sont
à installer volontairement ; la validation matérielle STT/TTS reste à effectuer.
Le wake word n'est pas activable faute de validation. Voir [Voix](docs/VOICE.md).
La V1.4.1 ajoute un pré-enregistrement de 300 ms, une détection de silence
avec hystérésis, Silero facultatif et un benchmark reproductible base/small.
Voir [audit, mesures et validation V1.4.1](docs/VOICE_V1_4_1.md).
Le registre conserve les 59 commandes historiques et ajoute 10 commandes vocales.
Aucun push ni changement système n’est requis.
Voir le [guide des scénarios](docs/SCENARIOS.md), son
[exemple de révisions](docs/examples/revisions.json) et la [recette](docs/VALIDATION.md).

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
- **Modes** : onglets Travail/Gaming/Études, workspace, applications, réutilisation,
  disposition, scénario associé, prévisualisation, activation et restauration des valeurs
  par défaut. Études conserve Chrome et `gtk-launch notion`.
- **Paramètres** : configuration métier en lecture seule, animations, intervalle du
  monitoring, version, raccourcis et emplacement des logs.

La page **Scénarios** ajoute bibliothèque, recherche, création, duplication,
suppression confirmée, nom/description/activation, étapes typées réordonnables,
prévisualisation, lancement, annulation, progression et sélection des exécutions passées.
Les déplacements demandent `confirme scénario CODE` ; les autres actions s’exécutent
dans le worker partagé. Le bouton Annuler scénario reste accessible dans Mini.

La barre de commandes globale accepte Entrée ; **Ctrl+L** lui rend le focus. Mini
et HUD partagent une seule commande en cours, les réponses et un seul collecteur.
Chaque vue conserve au maximum 500 blocs de réponses en mémoire. Les pages inactives
ne lancent pas de lectures périodiques ; le monitoring continue pour les alertes.

La page **Fenêtres** affiche les workspaces, le bureau courant, les moniteurs et
les fenêtres regroupées (classe, titre, état, adresse). Sélectionner une fenêtre
permet de lui donner le focus, choisir sa destination, la rendre flottante ou
mosaïque, ou la centrer. Les lectures et actions utilisent des workers ; Actualiser
recharge l’inventaire. Une erreur efface la sélection et une cible fermée est refusée.
Les boutons de disposition affichent un plan dans la console : y saisir le code de
confirmation fourni. `aide` expose automatiquement les **69 commandes**.

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
les bindings. La V1.1 a été validée manuellement par l’utilisateur ; la V1.2 a également été validée manuellement par l’utilisateur au lancement de V1.3 ; l'identité distincte dépend du backend **Qt Wayland natif**, pas XWayland.

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
| Fenêtres | `mes fenêtres`, `fenêtre active`, `mes bureaux`, `bureau 3`, `bureau suivant`, `bureau précédent`, `focus APPLICATION`, `où est APPLICATION` |
| Placement | `déplace APPLICATION au bureau N`, `mets APPLICATION à gauche`, `mets APPLICATION à droite`, `centre la fenêtre`, `fenêtre flottante`, `fenêtre mosaïque` |
| Dispositions | `organise mon bureau`, `disposition développement`, `disposition études`, `disposition gaming`, `confirme disposition CODE`, `annule disposition` |
| Projets | `mes projets`, `projets Rust`, `reprends mon projet Rust`, `reprends mon projet Python`, `ouvre projet NOM`, `ouvre rust NOM`, `projet actif`, `état git`, `objectif projet : TEXTE`, `sessions projets` |
| Sessions | `suis le fichier CHEMIN`, `mes fichiers suivis`, `sauvegarde ma session`, `reprends ma session`, `état session` |
| Scénarios | `mes scénarios`, `lance scénario NOM`, `prévisualise scénario NOM`, `annule scénario`, `état scénario`, `historique scénarios`, `confirme scénario CODE`, `ouvre scénarios` |
| Configuration des modes | `configure mode NOM` |
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
`active_mode.json` conservent leurs emplacements. Les surcharges de modes vont dans
`modes.json`, les scénarios dans `scenarios/*.json` et leurs 100 dernières exécutions
dans `scenarios/journal/runs.json`. Ces fichiers sont versionnés et écrits atomiquement. Les logs techniques JSON partent
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
conformément au comportement historique. Les profils personnalisés réappliquent leurs
étapes avec la politique de réutilisation choisie à chaque activation.

Pas d'IA, voix, Spotify, domotique ou autonomie dans cette version.
Voir [ARCHITECTURE.md](docs/ARCHITECTURE.md) pour les responsabilités, la sécurité
et les compromis de compatibilité.

## Placement et protections V1.2

`APPLICATION` recherche la classe ou le titre, sans distinction de casse/accents.
Plusieurs correspondances produisent une liste : choisir dans Fenêtres ou remplacer
APPLICATION par l’adresse exacte affichée, par exemple `focus 0x123abc`.
Les destinations explicites restent bornées à 1–9 ; suivant/précédent utilise les
workspaces du moniteur courant (`m+1` / `m-1`). Les bureaux spéciaux sont lisibles.

Les placements gauche/droite passent **en flottant**, utilisent la moitié de la
zone utile du moniteur, son échelle, sa rotation et ses réservations. Les contraintes
minimales des applications et règles Hyprland peuvent limiter la géométrie obtenue.
Le mode **mosaïque** rend le placement au layout Hyprland ; aucun ordre exact n’est
garanti. Centrer exige déjà une fenêtre flottante. Redimensionnement et positionnement
arbitraires sont disponibles dans le service typé, sans interpréteur Lua libre.

Développement prépare l’éditeur à gauche et Foot à droite sur le bureau 3 ; Études
prépare Notion à gauche et Chrome à droite sur le 5 ; Gaming déplace uniquement Steam
sur le 4. Notion est reconnu aussi par sa classe webapp `chrome-www.notion.so__-Default`.
Ces dispositions ne lancent rien : les applications absentes ou ambiguës sont signalées.
Les modes historiques peuvent toujours lancer les applications manquantes, dont
**`gtk-launch notion`**, et conservent les positions des applications déjà ouvertes.
Un inventaire indisponible évite un lancement potentiellement dupliqué.

Toute disposition collective exige le code de confirmation, à usage unique et valable
60 secondes ; un nouveau plan remplace le précédent. `organise mon bureau` remet en
mosaïque les fenêtres admissibles du bureau courant. Les plans ignorent Jarvis et les
fenêtres en plein écran. Les actions refusent aussi les fenêtres devenues plein écran.
Un échec arrête les étapes restantes et signale les modifications partielles possibles,
sans rollback susceptible de perturber davantage le bureau.

Les classes `jarvis`, `jarvis-hud` et le workspace `special:jarvis` sont protégés,
y compris contre les actions individuelles de cette version. Aucun kill, fermeture,
changement de résolution, raccourci ou fichier de configuration n’est exposé.
Depuis la console, la fenêtre active peut être Mini/HUD : utiliser alors la sélection
explicite de la page Fenêtres. Les sessions et ouvertures de projets conservent leur
comportement validé : la déduplication globale d’éditeur/terminal concerne les modes,
pas la reprise de fichiers ou de répertoires de projets différents.

## Voix V1.4

Ouvrir **Voix** dans le HUD, renseigner les exécutables/modèles locaux, autoriser
le push-to-talk puis Enregistrer. Cliquer Microphone dans Mini ou HUD, parler,
cliquer de nouveau et vérifier la transcription avant **Valider**. Le bouton
Annuler / couper le son reste accessible pendant les opérations audio.
`ouvre les paramètres vocaux` ouvre directement la page ; `aide` décrit le catalogue.
Les paramètres vocaux sont séparés dans `data_dir/voice.toml`.

Le raccourci optionnel `jarvis --voice-toggle` adresse le processus existant sans
modifier le bureau. SUPER+SHIFT+V a été vérifié libre mais **n'a pas été installé**.
Voir les [instructions, licences, limites et recette manuelle](docs/VOICE.md).
Aucune fonction V1.5, IA conversationnelle, API distante ou téléchargement implicite.
