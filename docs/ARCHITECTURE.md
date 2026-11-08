# Architecture V1.1

## Deux fenêtres et un contexte partagé

```text
JarvisWindow (Mini, classe jarvis) ─┐
                                 ├─ AppContext
HudWindow (classe jarvis-hud) ────┘    ├─ CommandBus → Runner → core.commands.execute
                                      │                        → registre V1.0 → services
                                      ├─ MonitorHub → Runner → Collector → psutil / alertes / SQLite
                                      │    └─ cache 60 mesures → vues Mini, Accueil, Système
                                      ├─ OverviewService ← runners de lecture des pages
                                      └─ préférences UI → runner d'écriture atomique
```

Les deux fenêtres utilisent Qt Widgets et le thème central `interface/theme.py`.
`interface/components.py` fournit les cartes, labels en texte brut et la console.
Les six pages sont dans `interface/pages/` ; elles ne contiennent ni SQL, ni Git,
ni dispatcher Hyprland. `services/overview.py` réutilise les services métier et
assemble les lectures nécessaires à la présentation.

Mini crée le contexte et, à la première demande seulement, le HUD. Le HUD n'a pas
de parent natif pour ne pas devenir une fenêtre transitoire du workspace spécial.
Sa fermeture le masque ; réouverture sans nouveau collecteur, widgets ou readers.
La fermeture de Mini arrête les timers, attend tous les runners, puis détruit le HUD.
`aboutToQuit` constitue une seconde protection idempotente. Le raccourci externe
masque via Hyprland et ne recrée pas Mini.

## Flux et threads

`CommandConsole` appelle `CommandBus.submit`, qui utilise exactement
`core.commands.execute` et `registry.resolve`. Une seule commande est acceptée à
la fois pour les deux fenêtres. Boutons des modes/sessions/projets et actions rapides
soumettent des formulations déjà enregistrées. Aucun second interpréteur ni nouvelle
commande textuelle. Les réponses et l'état occupé sont diffusés aux deux consoles.

`MonitorHub` détient un seul `Collector`, `Runner`, timer et historique de 60 mesures.
Les vues consomment des snapshots et ne mesurent rien elles-mêmes. La page Système
partage le dashboard V1.0 ; ses lectures complémentaires (historique et processus)
ont un timer distinct de 15 s, actif seulement lorsqu'elle est affichée. Les autres
pages relisent à l'ouverture, sur Actualiser et après une commande. Git n'est lu
que pour le projet sélectionné ; une réponse de sélection périmée est ignorée.
Les lectures en cours peuvent finir en arrière-plan après changement de page,
mais leur résultat n'est pas dessiné tant que la page reste inactive.

Tous les appels aux services, échantillonnages, Git, SQLite et écritures de préférences
se font via les workers V1.0. Les slots de widgets et les timers restent sur le thread
GUI. Un runner ne lance jamais deux tâches simultanées. Les transitions d'opacité
(180 ms) sont ponctuelles et désactivables ; aucune boucle de rendu permanente.
Les dimensions sont en pixels logiques Qt pour le HiDPI.

La fermeture attend les tâches en cours : pas de destruction d'un QThread actif ni
d'interruption d'une transaction, mais une lecture lente peut retarder la sortie.
Le monitoring continue même si le HUD est masqué pour préserver les alertes.

## Préférences et alertes

`preferences.py` lit `data_dir/ui.toml` et valide `animations` (booléen) et
`refresh_seconds` (entier 1–30). Écriture dans un temporaire du même répertoire,
flush/fsync puis remplacement atomique ; le runtime change seulement après succès.
Le TOML métier n'est jamais réécrit. Un fichier UI invalide est conservé avec des
valeurs par défaut et un avertissement. Les préférences sont chargées au démarrage ;
leur édition depuis Paramètres prend effet immédiatement.

`AlertEngine.recent` garde en mémoire les 20 dernières alertes réellement émises,
transmises dans `Snapshot.alerts`. Pas de nouvelle table ou de faux historique :
la page Accueil précise « depuis le démarrage ». Les anciennes données et la
rétention de performances restent inchangées.

## Responsabilités

| Couche | Modules | Responsabilité |
| --- | --- | --- |
| Interface | `interface/mini.py`, `hud.py`, `pages/*`, `components.py`, `theme.py`, `workers.py` | Fenêtres, vues Nebula, tâches, signaux et slots |
| Application | `core/commands.py`, `interface/context.py` | Exécution, frontière d'erreurs, journalisation |
| Routage | `registry.py`, `core/text.py` | Catalogue, résolution, aide, extraction des arguments originaux |
| Services | `projects/manager.py`, `projects/sessions.py`, `modes/manager.py`, `monitoring/*` | Projets, sessions, profils, mesures, alertes et diagnostics |
| Persistance | `persistence/sqlite.py`, `memory/database.py` | Connexion par opération, transaction et fermeture ; historique des commandes |
| Intégrations | `integrations/desktop.py`, `integrations/git.py`, `omarchy.py` | Dispatchers Lua, Git en lecture seule, terminal |
| Configuration | `config.py`, `config.example.toml`, `preferences.py` | Valeurs par défaut et surcharge TOML |
| Journalisation | `logging_setup.py` | JSON sur stderr, événements et types d'erreur sans contenu utilisateur |

Les schémas et requêtes métier restent près des services qui les possèdent. Les
lancements d'éditeur et d'applications restent dans leurs services, sous forme de
listes d'arguments explicites. Aucun service ne dépend de Qt. Les anciens points
d'entrée `commands.py`, `projects/commands.py`, `modes/commands.py` et
`handle_project_command` sont des adaptateurs vers le registre, avec imports locaux
pour ne pas introduire de cycle. Le monitoring V0.1 est un simple réexport.

## Contrat du registre

Chaque `Command` définit `id`, `name`, `description`, `examples`, `handler`,
`category`, les alias exacts et éventuellement un motif dynamique et son type de
paramètre. `resolve` ne lance aucune action. Les mots sont normalisés (casse,
accents, espaces et préfixe « Jarvis ») ; chemins et objectifs sont extraits du texte
original. Les routes structurées passent avant les anciennes expressions libres,
pour qu'un objectif contenant « ouvre un terminal » n'ouvre pas d'application.

L'aide parcourt le même catalogue ; chaque commande apparaît une seule fois.
L'intégrité des identifiants et des alias est vérifiée au chargement. Les tests
résolvent tous les exemples et alias, avec majuscules et préfixes, et vérifient les
paramètres. Pour ajouter une commande, enregistrer son handler et ses formulations
ici, puis ajouter les tests métier appropriés ; ne pas ajouter d'interpréteur ailleurs.

## Compatibilité des données

Les emplacements par défaut restent `~/.local/share/jarvis/` :

- `projects.db` : `projects`, `sessions`, `tracked_files`, `saved_sessions`.
- `performance.db` : `metrics`, index temporel ; rétention historique de sept jours.
- `memory.sqlite3` : `history` ; anciennes lignes conservées, nouvelles lignes
  limitées à l'identifiant de commande et au statut.
- `active_mode.json` : dernier mode ; écriture temporaire puis remplacement atomique.

Aucune migration destructive, copie ou réinitialisation des bases existantes.
Les tables et index sont créés avec `IF NOT EXISTS`. La primitive SQLite utilise
une connexion propre à chaque opération/thread, un délai de verrouillage de cinq
secondes, commit/rollback et fermeture dans un `finally`. Les tests n'accèdent
qu'à des bases temporaires. Changer `data_dir` choisit un autre emplacement, sans
migration automatique des données.

Les objectifs, noms de fichiers et états Git sont volontairement conservés dans
la mémoire métier locale. Ne pas y saisir de secrets. Les logs techniques et les
nouvelles lignes d'historique de commandes n'enregistrent pas ces contenus ; les
anciens historiques ne sont pas purgés automatiquement.

## Compatibilité Omarchy et sécurité

Les trois formes Lua observées sont conservées dans une seule intégration, avec
validation du numéro (entier de 1 à 9) :

- commande workspace : `hyprctl dispatch 'hl.dsp.focus({workspace=3})'` ;
- modes : `hyprctl dispatch 'hl.dsp.focus({ workspace = "3" })'` ;
- sessions : `hyprctl eval 'hl.dispatch(hl.dsp.focus({workspace=3}))'`.

Leur équivalence native n'est pas présumée. Les tests vérifient les arguments et
les erreurs, pas leur exécution réelle. `jarvis-toggle`, les bindings Lua, le titre
et les dimensions de fenêtre sont conservés ; l'identité Qt est explicitement
`jarvis`. Études lance toujours Notion via `gtk-launch notion` par défaut.

Pas de `shell=True`, pas d'évaluation de texte utilisateur, pas de Git destructeur.
Git accepte seulement les trois requêtes de lecture utilisées par les services.
Les reprises de projets et le mode Travail vérifient les projets reconnus. Les
fichiers suivis sont résolus et bornés au projet, y compris au moment de leur
réouverture pour résister aux liens symboliques remplacés. Les sessions JSON
corrompues sont refusées. La configuration locale est une entrée de confiance,
modifiée par l'utilisateur : elle choisit des exécutables, jamais une chaîne shell.

## Compromis conservés

La découverte Rust V0.1 reste à un ou deux niveaux, avec son ordre par date de
modification et ses éditeurs historiques (dont Zed). La découverte V0.7 traite
Rust/Python jusqu'à trois niveaux, trie par nom et ignore les dossiers cachés et
les dossiers de build. Ces deux politiques restent distinctes pour compatibilité ;
la lecture Git est partagée. `ouvre rust` garde son ancien comportement d'ouverture
sans mise à jour du projet actif ; utiliser `ouvre projet` pour les sessions.

Le diagnostic avancé et la liste de processus gardent leurs échantillons courts.
Les erreurs prévues deviennent des réponses lisibles ; la frontière applicative
intercepte aussi les erreurs inattendues et journalise leur type sans leur contenu.
Les logs ne contiennent donc pas de traceback avec des paramètres privés.

## Identité des fenêtres Qt Wayland

Le backend Qt Wayland lit `QGuiApplication.desktopFileName()` lors de la création
du rôle de surface. `HudWindow.show()` utilise `jarvis-hud` pendant cet appel,
puis restaure la valeur de Mini dans un `finally`. Pas de propriété privée supposée,
pas de dispatcher ajouté ni de processus séparé. Ce comportement a été vérifié en
lisant les clients Hyprland du processus de test, avant et après réouverture.

Référence de l'implémentation Qt consultée :
[QWaylandWindow, Qt](https://github.com/qt/qtbase/blob/dev/src/plugins/platforms/wayland/qwaylandwindow.cpp).
Les signaux et workers suivent la
[documentation QThread](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html).
La recette du raccourci et du workspace spécial reste nécessaire ; le backend
XWayland n'est pas couvert par cette séparation d'identité.
