# Modes et scénarios V1.3

## Utilisation

`ouvre scénarios` ouvre la huitième page du HUD depuis Mini. Créer un scénario,
renseigner son nom et sa description, choisir un type d’action et ses paramètres,
puis **Ajouter étape**. Sélectionner une étape pour **Appliquer à l’étape** les
changements du formulaire. Les flèches changent son ordre ; Retirer l’enlève du
brouillon. **Enregistrer** persiste le scénario. Une copie reste un brouillon
jusqu’à son enregistrement. La suppression d’un scénario enregistré demande une
confirmation ; son historique est conservé. Un changement de sélection demande
confirmation si le brouillon a été modifié. Les opérations disque passent par les
workers, et l’éditeur est désactivé pendant une commande.

La bibliothèque accepte une recherche insensible aux accents. Les identifiants
permettent de différencier les homonymes ; la commande textuelle refuse les noms
ambigus et retourne leurs identifiants. Les scénarios désactivés restent éditables
et prévisualisables mais ne peuvent pas être exécutés.

**Prévisualiser** accepte aussi les brouillons. Le résultat apparaît dans le panneau
et la console : étapes ordonnées, paramètres, politique d’erreur, préconditions,
lancements et déplacements possibles. Les vérifications ne projettent pas un futur
bureau : une application absente peut être lancée par l’étape précédente. Toutes
les préconditions sont relues à l’exécution. Aucune simulation ne lance un programme,
ne change le workspace, ne déplace de fenêtre, ne modifie un projet ou Git.

**Exécuter** utilise le scénario enregistré. Toute présence de `move_window` ou
`apply_layout`, même pour une seule fenêtre, exige un jeton à usage unique : saisir
`confirme scénario CODE` dans la console, dans les 60 secondes. La demande décrit
les cibles actuellement visibles et annonce explicitement que les groupes de
fenêtres admissibles seront résolus au moment de chaque étape, notamment après un
lancement d’application. Modifier le scénario ou le profil entre demande et
confirmation invalide l’accord. Une nouvelle demande remplace la précédente.
`prévisualise scénario NOM` seul ne crée pas de jeton : `lance scénario NOM` prépare
la demande confirmable.

Le bouton **Annuler scénario** est aussi présent dans Mini. `annule scénario` et
`état scénario` passent pendant une commande occupée, car ils ne font que toucher
l’état en mémoire. La fermeture de Mini demande également l’annulation avant
l’attente des workers. Une étape commencée peut terminer ; les suivantes deviennent
`cancelled`. Une disposition peut s’arrêter entre deux fenêtres. Aucun processus
n’est tué, aucune application fermée, et aucun rollback n’est prétendu.

## Actions et paramètres exacts

Tous les paramètres du tableau sont obligatoires ; les paramètres supplémentaires
sont rejetés. Un workspace est un entier 1–9, jamais un booléen ou une chaîne Lua.

| Type | Paramètres | Comportement |
| --- | --- | --- |
| `switch_workspace` | `workspace` | Service Hyprland V1.2, changement de bureau. |
| `open_application` | `application`, `reuse` (booléen) | `editor`, `terminal`, `browser`, `notion`, `steam` uniquement. Exécutables issus de la configuration métier autorisée. |
| `focus_window` | `target` (1–256 caractères) | Classe, titre ou adresse ; exactement une correspondance requise. |
| `move_window` | `target`, `workspace` | Même sélection, validation de la cible puis déplacement protégé. |
| `apply_layout` | `layout`, `workspace` | `developpement`, `etudes`, `gaming`. Réutilise le constructeur de plans V1.2 avec destination configurable. |
| `resume_project` | `language` (`Rust` ou `Python`) | Dernier projet connu du langage encore découvert ; à défaut, seulement un projet unique. Réutilise la reprise existante. |
| `restore_session` | aucun | Restaure la session du projet actif reconnu via le service historique. |
| `show_project_objective` | aucun | Affiche l’objectif du projet actif dans le résultat en mémoire. |

`reuse=true` conserve les fenêtres déjà ouvertes, sans les déplacer ni les focaliser.
L’inventaire indisponible fait échouer l’action plutôt que risquer un doublon.
`reuse=false` demande explicitement un nouveau lancement. Notion utilise le lanceur
existant `gtk-launch notion` et reconnaît sa classe webapp ; le fichier desktop est
cherché dans les emplacements XDG. Aucun exécutable ou argument libre n’est stocké
par un scénario. L’éditeur et Foot reçoivent le dossier du projet actif reconnu.

La reprise de projet conserve sa sémantique historique : elle ouvre l’éditeur et
mémorise la reprise, mais n’ouvre pas Foot. Ajouter `open_application: terminal` pour
compléter l’environnement. La réutilisation d’un éditeur existant ne garantit pas
son dossier. La restauration de session conserve le workspace Travail du TOML
historique ; un `switch_workspace` précédent ne change pas cette convention.

Les dispositions n’attendent pas la création des fenêtres : un lancement accepté
par le système ne garantit pas qu’une fenêtre est déjà visible. Les candidates
absentes, ambiguës ou en plein écran sont signalées et ignorées. Une disposition
sans candidate est `skipped`. Une disposition partielle précise les groupes
ignorés. Une erreur Hyprland devient `failed` et peut laisser des placements déjà
appliqués. Gaming ne cible que Steam, jamais les classes des jeux.

## Modes personnalisables

`configure mode Travail`, `configure mode Gaming` ou `configure mode Études` ouvre
l’onglet correspondant dans Modes. Workspace, applications autorisées, réutilisation,
disposition et scénario associé sont éditables. **Enregistrer le mode** puis
**Prévisualiser le mode enregistré** ou **Activer**. Les étapes du scénario associé
s’exécutent après le workspace, les applications et la disposition du profil.
Une association manquante ou désactivée empêche l’activation, sans modifier le bureau.

Sans surcharge, les valeurs historiques restent Travail 3, Gaming 4, Études 5,
Chrome et Notion pour Études, ou les valeurs explicitement choisies dans le TOML.
Les profils historiques conservent le non-relancement lorsque le même mode est
déjà actif. Les profils personnalisés réappliquent leurs étapes à chaque activation,
avec la politique `reuse` choisie. Un mode personnalisé n’est enregistré comme actif
qu’après réussite de toutes ses étapes (les étapes sans candidate peuvent être ignorées).

**Restaurer les paramètres par défaut** rétablit les valeurs dérivées du TOML sans
réécrire ce dernier. L’absence de `modes.json` importe simplement ces valeurs en
mémoire : aucune migration manuelle, aucune suppression des anciens fichiers.
Une version inconnue ou un fichier invalide est conservé et bloque l’édition/
activation personnalisée ; il faut le corriger ou le sauvegarder ailleurs avant
recréation, jamais le supprimer silencieusement. Aucun profil énergétique, son,
résolution, binding ou fichier système n’est changé.

## Format et stockage

JSON a été choisi pour des définitions autonomes, lisibles et copiables, sans
introduire de migration dans les bases métier existantes. Les fichiers sont :

- `data_dir/scenarios/IDENTIFIANT.json` : définition de schéma 1.
- `data_dir/scenarios/journal/runs.json` : schéma 1, 100 dernières exécutions.
- `data_dir/modes.json` : schéma 1, profils de modes.

Chaque définition contient exactement `id`, `name` (100 caractères), `description`
(2 000 caractères), `schema_version`, `enabled`, `actions` (100 maximum), `created_at`
et `updated_at` (dates ISO avec fuseau). Chaque action contient exactement `id`,
`type`, `parameters` et `failure_policy`. Les identifiants sont stables et bornés ;
les doublons d’étapes, clés JSON répétées, champs inconnus et versions non supportées
sont refusés. Le préfixe `mode_` est réservé aux scénarios composés depuis les profils.
Il n’y a pas d’icône ou de catégorie personnalisée dans ce premier schéma.

Écriture dans un fichier temporaire du même dossier, permissions privées à la
création, flush/fsync puis remplacement atomique. Les écritures concurrentes sont
verrouillées ; une révision périmée d’un scénario ne peut écraser la nouvelle.
Un fichier invalide ne disparaît pas de la bibliothèque sans avertissement et ne
peut être écrasé par l’éditeur. Limite de lecture de 2 Mo par définition et 8 Mo pour le journal borné. Les historiques
invalides sont aussi conservés et empêchent un nouveau lancement avant mutation.
Un échec d’écriture du journal après exécution est signalé sans rejouer les actions.

L’exemple [revisions.json](examples/revisions.json) peut être reproduit dans le HUD
ou copié manuellement dans le dossier des scénarios sous le nom
`exemple_revisions.json`, sans écraser un fichier existant. Aucun exemple n’est
installé implicitement. Les noms et descriptions sont du texte libre local :
ne pas y saisir de secrets. Aucun champ d’authentification n’est prévu.

## Résultats, erreurs et concurrence

Les événements transportent un instantané indépendant : identifiant d’exécution,
scénario, dates, état global et résultats par étape. États : `pending`, `running`,
`success`, `skipped`, `failed`, `cancelled`. Par défaut `stop` ignore les étapes
suivantes au premier échec ; `continue_on_error` est une décision explicite par
étape. Une exécution avec un échec reste `failed`, même si les suivantes réussissent
ou si l’utilisateur annule ensuite. Annuler après la dernière étape réussie ne
réécrit pas celle-ci comme annulée.

La progression et les messages détaillés restent en mémoire pour `état scénario`.
L’historique conserve dates, noms, types et états de chaque étape, mais ne duplique
pas les objectifs, chemins, titres et messages privés. Dans le HUD, choisir une
exécution dans la liste Historique affiche les états de ses étapes. Le détail des
messages disparaît après redémarrage. Le journal est écrit en fin d’exécution :
un arrêt brutal du processus avant cette écriture peut perdre cette exécution.

Le moteur refuse toute seconde exécution concurrente, même d’un autre scénario :
verrou mémoire et `flock` non bloquant commun aux moteurs partageant `data_dir`.
Mini et HUD utilisent en plus le bus de commandes existant, donc ne peuvent pas
intercaler une autre mutation Jarvis. Cela ne verrouille pas les gestes manuels,
les applications externes ou les commandes historiques d’un autre processus.
Les validations V1.2 sont répétées avant chaque action ; l’IPC reste non atomique.

## Limites de sécurité et extension

Aucun shell arbitraire, `shell=True`, évaluation de configuration, fermeture,
kill, sudo, écriture dans les projets ou Git destructeur. Le service V1.2 protège
`jarvis`, `jarvis-hud`, `special:jarvis` et les placements en plein écran. Les
scénarios ne modifient ni `jarvis-toggle` ni `SUPER+SHIFT+J`.

Le catalogue `scenarios/model.py` définit la validation et les formulaires ;
`scenarios/actions.py` fournit les préconditions et adaptateurs. Ajouter une action
future exige une entrée explicite dans ces deux couches et ses tests. Le moteur,
la persistance et le worker n’ont pas à être remplacés. Aucun chargement de code
depuis JSON, intégration Spotify, domotique ou fonctionnalité V1.4 n’est inclus.
