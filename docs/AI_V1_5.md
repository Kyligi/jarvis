# V1.5 — Intelligence conversationnelle locale

## État de livraison

Code Python/PySide6, 17 outils, 79 commandes (69 historiques + 10 IA), dix pages
HUD. Aucun service métier réimplémenté. IA désactivée par défaut, activable dans
Assistant ou par `active IA`. Texte utilisable sans Whisper/Piper.

Adaptateur implémenté : **Ollama HTTP local**. Modèle initial configuré :
**qwen3:4b**, pas installé pendant cette mission. La fiche officielle consultée
le 10 novembre 2026 annonce Q4_K_M, 4,02 milliards de paramètres, fichier de
2,5 GB ; l’occupation réelle inclut aussi contexte et buffers et doit être mesurée.
[Modèle officiel](https://ollama.com/library/qwen3:4b).

**Ollama est absent sur la machine auditée.** Ni version installée, ni qualité
linguistique réelle du LLM, ni débit, ni accélération Ollama ne sont validés.
Le test d’intégration et le benchmark sont livrés pour cette validation volontaire.

## Installation volontaire sur Omarchy

Ces commandes sont des instructions pour l’utilisateur, pas des opérations
exécutées par Jarvis ou durant cette livraison. Elles installent des logiciels et
un modèle volumineux : accord explicite requis avant de les exécuter via un agent.

1. Lire la [procédure officielle Linux](https://docs.ollama.com/linux). Son script
   d’installation est `https://ollama.com/install.sh`. Pour l’inspecter avant
   exécution :

   ```bash
   curl -fsSL https://ollama.com/install.sh -o /tmp/install-ollama.sh
   less /tmp/install-ollama.sh
   sh /tmp/install-ollama.sh
   ```

   Vérifier les éventuelles modifications système/service qu’il propose.
   Ne pas superposer cette installation à un paquet Arch existant sans examiner
   ses chemins et son service. Aucune dépendance Ollama n’est ajoutée à uv.

2. Démarrer une seule instance locale selon l’installation choisie. Pour une
   instance manuelle, serveur non déjà démarré :

   ```bash
   OLLAMA_HOST=127.0.0.1:11434 OLLAMA_VULKAN=1 ollama serve
   ```

   Pour une installation gérée par systemd, configurer volontairement les variables
   dans le service selon la documentation officielle, puis redémarrer le service.
   Jarvis ne le fait pas. Ne pas exposer le port sur le réseau.

3. Vérifier `ollama --version`, `curl http://127.0.0.1:11434/api/version`, puis
   télécharger volontairement le modèle (environ 2,5 GB selon la fiche consultée) :

   ```bash
   ollama pull qwen3:4b
   ollama list
   ollama show qwen3:4b
   ```

4. Démarrer Jarvis avec `uv run jarvis`, ouvrir Assistant, Actualiser Ollama,
   sélectionner le modèle local, cocher l’activation et Appliquer à la session.
   Enregistrer les préférences est facultatif et ne conserve aucune conversation.

### Vulkan, CPU et mémoire partagée

La [documentation GPU officielle](https://docs.ollama.com/gpu), consultée lors de
la livraison, indique Vulkan actif par défaut lorsque son backend est installé ;
les versions antérieures peuvent exiger `OLLAMA_VULKAN=1`. L’installation effective
et les logs du moteur font autorité. `GGML_VK_VISIBLE_DEVICES` permet de sélectionner
un GPU. `OLLAMA_VULKAN=0` désactive Vulkan ; un autre backend GPU pourrait rester
actif. Pour un essai CPU, désactiver les GPU du serveur selon sa version, puis
**vérifier** `ollama ps` et les logs : ne pas déduire CPU d’une simple variable.
Aucun override ROCm, ajout de droits, changement de groupe ou de pilote automatique.

Le diagnostic matériel en lecture seule, hors bac à sable, a confirmé :

- AMD Radeon 860M Graphics (RADV KRACKAN1), GPU intégré, PCI 1002:1114.
- Mesa 26.2.5-arch1.1, API périphérique Vulkan 1.4.354 ; instance 1.4.363.
- Le même diagnostic dans le bac à sable échouait à initialiser Vulkan.

Cela prouve la disponibilité de Vulkan sur l’hôte, **pas son utilisation par Ollama**.
`/api/ps.size_vram > 0` prouve une allocation GPU déclarée, sans identifier Vulkan.
`size` est l’empreinte modèle annoncée, pas la RSS du processus ni une mesure de
mémoire physique exclusive sur cet iGPU. Pour une preuve Vulkan, conserver les
lignes de diagnostic identifiant le backend et les couches effectivement déportées.

`keep_alive=0` demande de libérer le modèle après chaque requête. Le coût est un
rechargement plus fréquent. Une valeur 1–300 s peut améliorer la latence mais
augmente le risque de concurrence mémoire avec Whisper ou d’autres applications.
Jarvis ne ferme aucune autre application et ne décharge pas leurs modèles.
Le bus refuse une inférence IA pendant capture/transcription/synthèse. Le microphone
via Mini/HUD et le test de capture sont bloqués pendant une commande. Whisper CLI
se termine avant la validation de sa transcription ; le LLM démarre ensuite.
Les autres processus externes à Jarvis ne sont pas sérialisés par ce verrou.

## Architecture et flux

```text
Mini / HUD / transcription affichée puis validée
  → CommandBus (verrou partagé, Runner hors Qt GUI)
  → registry.resolve
      commande reconnue → core.commands.execute → service historique
      formulation libre → ai.conversation.Conversation
        → contexte borné → Backend abstrait → OllamaBackend
        → JSON complet validé → catalogue fermé
          lecture → service → résultat réel et source
          action → cible résolue + conséquences + code Jarvis
            → saisie humaine → expiration/usage unique/revalidation
              → service historique → confirmations V1.2/V1.3 si applicables
  → texte complet → Piper existant si autorisé
```

`ai/config.py` valide et sauvegarde uniquement `data_dir/ai.toml` (atomique, 0600).
`ai/backend.py` utilise la bibliothèque standard, HTTP sans proxy ni redirection.
`Backend` abstrait expose `inspect` et `generate`, sans Qt. `OllamaBackend` consulte
`/api/version`, `/api/tags`, `/api/ps`, puis `/api/show` avant `/api/chat`.
Le modèle doit être installé et ne doit pas être un alias cloud. Aucun appel à
pull/create/delete, aucun téléchargement implicite, aucune API Ollama Cloud.

`format` contient un schéma JSON pour `{reply, calls}`. Ce protocole n’exige pas
le tool calling natif du modèle. `think=false` est envoyé seulement si `/api/show`
annonce la capacité `thinking`. Un moteur incompatible est signalé ; aucun repli
cloud ni réparation permissive d’une sortie invalide.

Les fragments alimentent un **brouillon non vérifié**. Aucune action ni donnée
vérifiée n’est affichée comme résultat avant validation complète et exécution du
service. Une réponse libre est marquée « Conversation IA — non vérifiée ».
Pour un appel d’outil, la réponse finale est le texte réel du service, pas une
réécriture potentiellement hallucinée par le modèle. Au-delà de 16 000 caractères,
le résultat est explicitement abrégé en conservant son début et sa fin (dont les
éventuelles instructions de confirmation du service).

## Catalogue fermé

Chaque `Tool` déclare id, description, schéma, validation, handler, provenance,
risque, confirmation, budget temporel et format text/plain. Schémas : objets à
champs exacts, types stricts (booléen refusé comme entier), bornes et identifiants.

| Outil | Service existant | Politique |
| --- | --- | --- |
| list_projects | projects.manager.list_projects | Lecture |
| get_active_project | projects.manager.active_project_text | Lecture |
| get_git_status | projects.manager.active_git | Lecture Git |
| get_system_metrics | monitoring.system.system_status | Mesures réelles |
| get_diagnostics | monitoring.diagnostics.explain_slowdown | Lecture |
| list_workspaces | services.window_commands.desktops | Lecture Hyprland |
| list_windows | services.window_commands.inventory | Lecture et adresses |
| list_modes | modes.profiles.load | Lecture |
| list_scenarios | scenarios.commands.library | Lecture |
| get_scenario_status | scenarios.commands.status | Lecture |
| get_recent_project_sessions | projects.manager.recent_sessions | Lecture |
| preview_scenario | scenarios.commands.preview | Prévisualisation sans action |
| activate_mode | modes.manager.activate_mode | Confirmation IA + protections historiques |
| focus_window | window_commands.action('focus', adresse) | Confirmation IA |
| switch_workspace | window_commands.switch | Confirmation IA, bureaux 1–9 |
| open_project | projects.manager.open_named_project | Confirmation IA, nom unique |
| run_scenario | scenarios.commands.launch | Confirmation IA puis code scénario si déplacements |

L’ouverture de projet exige une cible unique découverte réellement ; le chemin
résolu est mémorisé pour la confirmation. Le focus exige une adresse réelle,
une fenêtre non protégée et une identité inchangée (notamment PID). Les scénarios
utilisent leur identifiant stable et une empreinte de contenu ; les modes incluent
leur profil, les actions du scénario associé, le projet actif et une prévisualisation.
Une modification invalide la proposition. Les services revalident ensuite leurs
propres cibles. Un bureau numéroté vide reste une destination Hyprland valide.

## Permissions et confidentialité

- Une commande reconnue par le registre conserve son chemin historique, ses alias,
  ses validations et sa priorité. Les expressions historiques restent inchangées.
- Le LLM ne reçoit aucune fonction Python, aucun code Lua ou capacité système.
  Aucun outil shell, sudo, eval, exécution Python, édition ou confirmation de code.
- Au plus trois appels par message par défaut ; aucune boucle de relance du LLM.
  Une action doit être seule, sans lecture combinée. Tous les schémas sont validés
  avant le premier appel. Champs inconnus, clés dupliquées et nombres non JSON refusés.
- Toute action issue du LLM exige `confirme action IA CODE`, généré par Jarvis,
  valable 60 s et consommé avant exécution. Un mauvais code consomme aussi la demande.
  Une nouvelle demande libre, arrêt, désactivation ou effacement annule la proposition.
- La validation vocale dure 30 s et autorise seulement l’interprétation de la phrase.
  Les codes IA, scénarios et dispositions sont refusés à la voix. « Jarvis » n’authentifie rien.
- Les résultats Git, fenêtres et autres services sont affichés en **texte brut**,
  avec leur source, sans interprétation HTML et **sans réinjection au modèle**, même
  dans l’historique. Une injection dans un résultat ne peut donc demander un outil.
- Les erreurs techniques ne journalisent pas les conversations. L’historique métier
  des commandes exactes conserve seulement les identifiants, comme auparavant.
- La configuration n’accepte que HTTP avec IP numérique loopback et port explicite.
  `localhost` est volontairement refusé pour éviter toute résolution DNS ambiguë.
  Aucun proxy système, redirection ou endpoint distant. L’extension distante est
  indisponible en V1.5 ; elle exigerait un mécanisme séparé d’accord de confidentialité.
  Le serveur Ollama local reste une frontière de confiance : utiliser une installation
  maîtrisée, sans alias distant ni relais cloud ajouté par un tiers.

## Contexte, arrêt et limites

Au maximum six échanges et un budget conservateur en octets UTF-8, réservé à
l’intérieur de `num_ctx`, avec place pour sortie et gabarit. Le budget exact du
tokenizer dépend du modèle : il ne s’agit pas d’un comptage exact de tokens.
Les messages dépassant 2048 caractères ou le budget disponible sont refusés.
Aucune conversation n’est persistée. Décocher « Conserver quelques échanges »
permet un fonctionnement sans historique ; effacer annule aussi les propositions,
nettoie les consoles et la dernière réponse vocale.

Les suivis conversationnels utilisent les échanges récents et les appels proposés.
Par choix de sécurité, les textes de résultats d’outils ne reviennent pas dans le
contexte : « ouvre le deuxième projet de cette liste » peut nécessiter de préciser
son nom exact. Aucun choix arbitraire d’une cible ambiguë. Le petit modèle peut
refuser, mal classer ou halluciner une réponse libre ; les informations locales
ne sont vérifiées que lorsqu’elles portent une source de service.

L’adaptateur impose un délai total d’inférence (détection incluse), limite les
réponses et ferme la connexion sur arrêt/délai dépassé. Les sondes locales ont
un délai maximal de 5 s chacune. Le serveur coopère à l’interruption HTTP ; Jarvis
ne tue pas le processus Ollama. Aucun redémarrage ou répétition automatique d’action.

Les budgets d’outils sont de 30 s, 60 s pour un mode, 300 s pour un scénario.
**Ils signalent un dépassement au retour ; ils ne tuent pas une fonction métier.**
Les timeouts des sous-processus restent ceux des services existants. Une action déjà
commencée n’est pas annulée par Arrêter IA ; utiliser Annuler scénario pour arrêter
les étapes restantes d’un scénario. Aucun rollback destructif. Une lecture métier
bloquée peut retarder la fin du worker : limite connue de cette version.

## Paramètres et commandes

Exemple complet : [ai.example.toml](examples/ai.example.toml). Les préférences UI,
voix, projets, modes et scénarios ne sont pas réécrites. Température 0,2, contexte
8192, sortie 768 tokens, timeout 90 s, trois outils, streaming activé et résidence 0.
Un contexte 4096 peut être insuffisant pour le catalogue actuel : refus explicite,
préférer 8192. Persistance true refusée, aucun profil personnel ni index vectoriel.

Les huit commandes demandées sont ajoutées à l’aide automatique :
`parle avec Jarvis`, `ouvre assistant`, `état IA`, `modèle IA`,
`efface conversation`, `arrête génération`, `active IA`, `désactive IA`.
Deux commandes de sécurité s’ajoutent : `confirme action IA CODE`, `annule action IA`.
Activer/désactiver par commande modifie uniquement la session ; le bouton Enregistrer
écrit les préférences explicites. La sélection du modèle est dans Assistant.

## Validation et performances

Les tests ordinaires utilisent un faux backend, des transports HTTP simulés et Qt
hors écran. Pas de microphone, téléchargement, GPU, serveur Ollama ni déplacement
réel de workspace. Les 447 tests historiques restent présents ; seules les
assertions de nombre de pages/commandes évoluent en conservant le sous-ensemble V1.4.2.
Voir [VALIDATION.md](VALIDATION.md) pour les résultats exacts.

Après installation volontaire seulement :

```bash
JARVIS_TEST_OLLAMA=1 uv run pytest -q tests/test_ai_ollama_integration.py
uv run python tools/ai_benchmark.py                 # détection seule
uv run python tools/ai_benchmark.py --run           # inférence, aucun outil exécuté
```

Le benchmark vérifie l’intention « Affiche mes projets », mesure temps mural,
premier fragment, durée totale, tokens/s et échantillonne `/api/ps` pour mémoire
modèle/GPU. Il n’enregistre ni requêtes personnelles ni réponses complètes.
Lancer à froid puis à chaud, relever `ollama ps` et les logs du moteur pendant
l’inférence. Avec résidence 0, le modèle peut déjà être déchargé au diagnostic suivant.
Le premier fragment inclut éventuellement de la structure JSON, pas nécessairement
le premier mot visible. Le débit provient de `eval_count / eval_duration`.

Mesures réelles de cette mission : **aucune inférence Ollama**, donc première
réponse, débit, mémoire LLM et latence voix→intention→réponse **non mesurés**.
Les chiffres Whisper historiques ne constituent pas une mesure de V1.5.
Tester la séquence voix puis LLM, comparer résidence 0/30 s et observer la mémoire
partagée ; ne pas lancer deux inférences lourdes simultanées pour établir une recette.

## Recette manuelle Omarchy

1. SUPER+SHIFT+J : vérifier Mini, centrage et raccourci inchangés ; ouvrir les dix
   pages HUD. Vérifier aide, projets, fenêtres, modes et scénarios historiques.
2. Ollama arrêté : question libre activée → erreur claire ; `aide` fonctionne.
   Modèle absent → état explicite, aucune installation automatique.
3. Ollama local disponible : activer IA, demander « Affiche mes projets. », puis
   métriques, Git, fenêtres. Comparer les sources aux commandes exactes.
4. Conversation libre et suivi ; désactiver le contexte puis l’effacer ; vérifier
   consoles et absence de fichier conversation/log de contenu.
5. Demander une ouverture de projet : lire cible/conséquences, ne pas confirmer,
   vérifier absence d’effet. Tester annulation, expiration et double soumission.
6. Confirmer une cible choisie ; comparer le résultat réel. Scénario déplaçant une
   fenêtre : vérifier que le second code historique reste indispensable.
7. Génération lente : naviguer, arrêter, reprendre ; désactiver IA pendant l’attente.
8. Voix : capture existante, transcription affichée, validation puis interprétation ;
   action proposée encore non exécutée. Code de confirmation vocal refusé. Piper
   désactivable, réponse longue résumée par son message neutre, texte complet visible.
9. Relever mémoire/CPU-GPU pendant une inférence, puis logs Vulkan. Tester CPU
   explicitement. Relever toute la latence vocale séparément, sans extrapoler.

V1.6/V1.7 et intégrations Spotify/domotique/téléphone/autonomie hors périmètre.
