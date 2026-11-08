# Validation V1.0

## Automatisation

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

## Recette manuelle Omarchy — à effectuer

Toutes les cases ci-dessous restent non cochées à la livraison.

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
