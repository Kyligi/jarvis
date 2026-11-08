# Architecture V1.0

## Flux des commandes

```text
JarvisWindow (thread GUI)
  → Runner / Task (QThread, une commande à la fois)
    → core.commands.execute
      → registry.resolve (sans effets de bord)
        → ResolvedCommand.run → service du domaine
          → intégrations système / persistence.sqlite.connect
      → historique (identifiant de commande + résultat « ok »)
  ← signal Qt → slot GUI → affichage

QTimer (2 s) → Runner indépendant → Collector.collect
  → psutil + capteurs → AlertEngine → historique (10 s)
  ← Snapshot → slot GUI → métriques, graphiques, températures
```

Les widgets sont modifiés uniquement sur le thread graphique. Un runner refuse une
nouvelle tâche tant que la précédente n'est pas terminée : aucun empilement de
collectes, aucune activation concurrente de modes dans l'interface. Les commandes
et le monitoring ont chacun leur runner. La fermeture attend les tâches en cours
pour éviter de détruire un QThread actif ou une transaction ; une commande longue
peut donc retarder la fermeture. Il n'y a pas d'annulation forcée en V1.0.

## Responsabilités

| Couche | Modules | Responsabilité |
| --- | --- | --- |
| Interface | `interface/mini.py`, `dashboard.py`, `workers.py` | Widgets existants, tâches, signaux et slots |
| Application | `core/commands.py` | Exécution, frontière d'erreurs, journalisation |
| Routage | `registry.py`, `core/text.py` | Catalogue, résolution, aide, extraction des arguments originaux |
| Services | `projects/manager.py`, `projects/sessions.py`, `modes/manager.py`, `monitoring/*` | Projets, sessions, profils, mesures, alertes et diagnostics |
| Persistance | `persistence/sqlite.py`, `memory/database.py` | Connexion par opération, transaction et fermeture ; historique des commandes |
| Intégrations | `integrations/desktop.py`, `integrations/git.py`, `omarchy.py` | Dispatchers Lua, Git en lecture seule, terminal |
| Configuration | `config.py`, `config.example.toml` | Valeurs par défaut et surcharge TOML |
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
