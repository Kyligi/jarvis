# Validation V1.2

## Résultat automatisé

- Référence avant modification : **147 tests V1.1 réussis**.
- V1.2 : **233 tests réussis**, sortie pytest 0. Tous les anciens scénarios sont
  conservés ; les assertions de navigation ont été adaptées de six à sept pages.
- `uv sync --locked`, `uv run pytest -q`,
  `uv run python -m compileall -q src/jarvis`, `git diff --check` : réussis.
- Aucun outil de qualité supplémentaire configuré dans le dépôt. Pas de mesure de
  couverture en pourcentage : couverture fonctionnelle décrite ci-dessous.
- Hyprland **0.56.2** vérifié en lecture ; constructeurs Lua focus, float on/off,
  move workspace, move position, resize et center acceptés via assertions dans
  `hyprctl eval`, **sans `hl.dispatch`**. Aucun placement réel testé.
- Script `jarvis-toggle`, bindings et configuration Hyprland lus ou laissés intacts.
- Tests Hyprland simulés, sous-processus réels interdits par les fixtures et Qt hors écran.
- Un premier passage affichait 226 succès mais sortait avec un segfault lors du
  nettoyage Qt des nouveaux tests ; destruction explicite des widgets ajoutée aux
  fixtures concernées, puis suite complète terminée avec code 0.

Couverture ajoutée : JSON invalide, inventaire, recherches classe/titre/adresse et
accents, ambiguïté, disparition/remplacement de cible, bureaux et paramètres typés,
allowlist Lua et injections refusées, Jarvis et workspace spécial, plein écran,
placement flottant/HiDPI, contrôle à chaque étape, confirmations expirées/consommées,
organisation modifiée, erreurs partielles, Notion webapp, déduplication des modes,
page Fenêtres (sélection, conservation, disparition, vide, erreur, actions en worker,
verrou partagé), registre/aide/alias et navigation à sept pages.

La V1.0 et la V1.1 ont été déclarées validées manuellement par l’utilisateur.
**La recette manuelle V1.2 ci-dessous n’a pas été effectuée par l’agent.**

## Recette manuelle V1.2 sur Omarchy

Utiliser des fenêtres de test et terminer/enregistrer le travail avant de confirmer
une disposition. Ne pas tester de déplacement sur une partie de jeu en cours.

- [ ] Démarrer `uv run jarvis`, vérifier V1.2 dans `aide` et Paramètres ; ouvrir HUD.
- [ ] SUPER+SHIFT+J : masquer/réafficher Mini depuis plusieurs workspaces, HUD ouvert
  puis fermé ; vérifier les classes distinctes, `special:jarvis` et l’absence de doublon.
- [ ] Naviguer vers **07 Fenêtres**, comparer workspaces, moniteurs, classes et titres
  avec le bureau réel. Actualiser, y compris après fermeture/ouverture d’une application.
- [ ] Ouvrir deux Foot. `focus Foot` doit demander un choix sans action ; choisir
  l’une dans Fenêtres, puis Focus. Tester aussi `focus ADRESSE` et `où est Foot`.
- [ ] Déplacer une fenêtre de test vers le bureau 3. `bureau 3`, suivant/précédent
  doivent agir sur le moniteur courant ; vérifier aussi l’ancien `passe au workspace 2`.
- [ ] Sélectionner une fenêtre puis la fermer avant une action : message explicite,
  aucune action sur une autre fenêtre. Tester une erreur Hyprland via mocks seulement.
- [ ] Mettre Foot à gauche puis à droite : vérifier le passage en flottant et la zone
  utile, aussi sur écran externe/HiDPI/rotation. Repasser en mosaïque et vérifier le
  layout actif ; l’ordre exact en mosaïque n’est pas garanti.
- [ ] Centrer une flottante. Depuis la console, Mini peut être la fenêtre active et
  sera protégée : utiliser le bouton Centrer sur une sélection dans Fenêtres.
- [ ] Demander une disposition Développement puis Annuler : aucun déplacement.
  Refaire et saisir `confirme disposition CODE` : éditeur/Foot existants sur 3.
  Tester un code expiré (60 s), réutilisé et un changement manuel avant confirmation.
- [ ] Études : Notion webapp à gauche, Chrome à droite sur 5 ; application absente ou
  plusieurs candidates signalées, aucun lancement par la disposition. Vérifier le mode
  Études et `gtk-launch notion` seulement si Notion n’est pas déjà ouvert.
- [ ] Gaming : seul Steam est candidat sur 4, jeux et plein écran conservés.
- [ ] `organise mon bureau` : examiner puis confirmer la liste ; Jarvis, HUD et fenêtres
  plein écran sont absents du plan. Vérifier les messages en cas d’application partielle.
- [ ] Relancer les modes Travail/Gaming/Études : workspaces 3/4/5, pas de duplication
  d’applications déjà ouvertes. Une fenêtre existante ailleurs reste à sa place ; utiliser
  une disposition confirmée pour la déplacer.
- [ ] Ouvrir puis reprendre un projet Rust/Python et une session de test, vérifier les
  fichiers suivis et le répertoire du terminal ; aucune donnée ou configuration écrasée.
- [ ] Pendant les actions/lectures, naviguer et masquer/réouvrir le HUD : GUI réactive.
  Fermer Mini pendant une lecture : arrêt propre après attente des workers.

## Limites V1.2

Les constructeurs Lua acceptés ne prouvent pas le résultat géométrique réel. Les
contraintes d’application et règles locales restent prioritaires. La relecture avant
chaque mutation n’est pas une transaction IPC atomique. Les dispositions ne font pas
de rollback ; elles s’arrêtent au premier échec et signalent les étapes déjà tentées.
Pas de lancement par les dispositions, pas de permutation précise en tiling, pas de
modification du HUD/Mini par le gestionnaire. La déduplication des modes ne garantit
pas le répertoire de travail d’une fenêtre existante ; projets et sessions gardent
leurs lancements spécifiques historiques. La sélection HUD reste la voie fiable
lorsque la fenêtre active est l’interface Jarvis elle-même.

---

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
