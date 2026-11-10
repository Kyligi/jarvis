# Voix locale V1.4.2

## État livré et limites

V1.4.2 intègre Whisper large-v3-turbo multilingue et le choix CPU/Vulkan dans
le HUD. Voir [installation, preuves matérielles et mesures](VOICE_V1_4_2.md).
La Radeon 860M a exécuté une transcription Turbo avec poids sur Vulkan0.
Le binaire CPU précédent et Piper sont conservés. Jarvis ne télécharge jamais
un modèle automatiquement ; l'installation Turbo a été autorisée explicitement.
La qualité sur voix humaine reste à mesurer ; les mesures synthétiques ne
permettent pas de promettre une meilleure reconnaissance au microphone.

Le contrôleur ne dépend pas de Qt. `voice/backends.py` expose des adaptateurs
injectables : `capture(config, stop, cancel, progress)`,
`transcribe(pcm, config, cancel)` et `speak(text, config, cancel)`.
`VoiceBridge` transmet les événements par signaux Qt, puis soumet exclusivement au
`CommandBus` existant. Aucune action bureau n'est réimplémentée dans la voix.

États : idle → listening → transcribing → awaiting_confirmation → executing →
idle/speaking ; error en cas de panne. Annulation et fermeture invalident le texte
à confirmer. La validation expire après 30 secondes et n'est consommable qu'une
fois. Toute transcription reconnue demande un clic visible, même avec un score
élevé. Le score moyen des tokens n'est pas une probabilité de commande correcte.
Les confirmations de scénarios/dispositions doivent toujours être **saisies dans
la console** avec leur jeton V1.3 ; la voix ne peut pas les accepter.

Un thread audio par contrôleur, un seul travail à la fois ; les demandes TTS
supplémentaires sont refusées, sans accumulation. L'arrêt est vérifié toutes les
50 ms dans les boucles CLI ; terminate puis kill après 300 ms et wait assurent la
récolte du processus. Ce délai est une borne de polling, pas une mesure matérielle.
Une commande métier déjà lancée garde ses règles d'annulation V1.3.

## Installation volontaire

Consulter les sources officielles avant toute installation :
[whisper.cpp](https://github.com/ggml-org/whisper.cpp),
[Piper OHF](https://github.com/OHF-Voice/piper1-gpl),
[CLI Piper](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md).
Les commandes génériques suivantes servent de référence pour une autre machine.
L’installation V1.4.2 réellement effectuée est détaillée dans son rapport.
Installer les prérequis avec le gestionnaire Omarchy habituel si nécessaire ;
ne pas utiliser le Python système 3.14 pour l'environnement Jarvis (3.13).

Whisper : utiliser un dépôt officiel dans un dossier dédié. La procédure
V1.4.2 construit `whisper-cli` avec `-DGGML_VULKAN=ON` dans un dossier distinct
et installe `ggml-large-v3-turbo.bin`, après accord et contrôle d’intégrité.
Voir [la procédure reproductible](VOICE_V1_4_2.md).

Dans Voix, choisir CPU ou Vulkan, renseigner les exécutables distincts et choisir
le fichier modèle multilingue `.bin` avec le sélecteur local. Les modèles `.en`
sont refusés. Jarvis passe `-l fr -ojf` et ajoute `-ng` **uniquement en CPU**.
Chaque invocation recharge le modèle dans le thread audio ; aucun chargement ni
transcription dans le thread Qt. Pas de serveur permanent. Le délai configurable
(60 s par défaut) couvre aussi l’éventuelle nouvelle tentative sans VAD.

Le HUD affiche le backend réellement validé de la dernière transcription, le
modèle, le temps incluant le chargement et le pic RSS échantillonné. Avant une
transcription, le backend est annoncé comme demandé/non vérifié. Les diagnostics
Vulkan doivent confirmer une allocation de poids et la sélection de Vulkan0
(ou autre indice), sans échec d’initialisation. Une simple détection de GPU ne
suffit pas. En cas d’absence ou d’échec : résultat rejeté, aucune commande en
attente ; sélectionner CPU, enregistrer et refaire une capture. Pour retrouver
le comportement précédent, sélectionner également l’ancien modèle small.
Aucun repli CPU automatique ni réutilisation de la transcription échouée.

Piper : installer le paquet maintenu `piper-tts` dans un environnement isolé, par
exemple avec `uv tool install piper-tts`, puis vérifier le chemin du binaire `piper`.
Choisir une voix française dans le
[catalogue Piper](https://huggingface.co/rhasspy/piper-voices/tree/main/fr/fr_FR).
Télécharger explicitement le `.onnx`, son `.onnx.json` et consulter son `MODEL_CARD`
avant usage. Configurer le chemin absolu `.onnx`, pas seulement un nom de voix.
Le backend exige les deux fichiers locaux, utilise stdin pour le texte, et lit le
WAV via `pw-play`. Vitesse 0,5–2, volume 0–1, sans changer le volume système.
Un résultat de plus de 240 caractères est remplacé à l'oral par une invitation à
lire le résultat affiché ; aucun résumé inventé. Le texte intégral reste en console.

### Licences

whisper.cpp est sous MIT ; vérifier aussi la provenance/licence du fichier de
poids choisi ([Whisper](https://github.com/openai/whisper)). Piper OHF est sous GPL-3.0,
contrairement à l'ancien moteur Rhasspy. Les voix ont des licences et jeux de
source distincts : leur MODEL_CARD fait autorité. Le modèle Turbo a été téléchargé avec accord explicite ; aucun poids ni voix
n’est redistribué dans Git.

## Microphone, paramètres et push-to-talk

La page Voix propose inventaire, microphone/sortie par nom stable PipeWire,
modèles, exécutables, vitesse, volume, seuil de parole, silence et durée maximale.
La sélection vide utilise le périphérique par défaut. Cliquer Périphériques pour
actualiser ; un périphérique disparu reste affiché comme déconnecté, sans bascule
silencieuse sur un autre microphone sélectionné explicitement.

Les paramètres sont dans `data_dir/voice.toml`, table `[voice]`, cohérente avec les
préférences UI séparées. Enregistrer applique atomiquement un fichier privé sans
réécrire config.toml ni ui.toml. Un fichier invalide est conservé et refuse l'écriture.
La configuration métier principale n'accepte pas une nouvelle table `[voice]` :
utiliser le fichier dédié. Exemple complet : [voice.example.toml](examples/voice.example.toml).

1. Renseigner les chemins et autoriser le push-to-talk, puis Enregistrer.
2. Premier clic Microphone : écoute avec niveau RMS et durée visibles.
3. Second clic : fin de capture puis transcription ; le silence après parole et
   la durée maximale arrêtent aussi la capture.
4. Vérifier le texte, cliquer Valider ou Annuler. En cas de doute, utiliser le clavier.
5. Annuler / couper le son interrompt capture, transcription ou lecture.

Le signal PCM est mono signé 16 bits little-endian à 16 kHz ; PipeWire effectue la
conversion depuis la fréquence matérielle. Le seuil RMS est une détection d'énergie,
pas un VAD neuronal : bruit, voix basse et silence initial peuvent réduire la qualité.
Aucune parole détectée signifie aucune transcription. Le test micro/transcription
n'exécute jamais de commande. Le test de voix ne capture rien.

Les commandes `active la voix` / `coupe la voix` changent l'autorisation de la
session ; Enregistrer dans Voix assure la persistance. `répète` reprend le dernier
résultat d'une commande vocale. Les dix commandes vocales sont détaillées dans
`aide`, générée depuis le catalogue unique (69 entrées actuellement).

### Raccourci optionnel, non installé

L'audit `hyprctl binds -j` n'a trouvé aucun SUPER+SHIFT+V sur cette machine.
Le revérifier au moment de l'installation. Exemple Lua à adapter volontairement :

```lua
o.bind("SUPER + SHIFT + V", "Jarvis microphone", "/home/kylian/Projects/jarvis-starter/.venv/bin/jarvis --voice-toggle")
```

L'option envoie seulement `toggle` au socket privé `$XDG_RUNTIME_DIR/jarvis-voice.sock`
du processus déjà lancé, puis quitte. Aucun déplacement, focus ou ouverture de
fenêtre ; SUPER+SHIFT+J n'est pas modifié. Une interface Jarvis doit être visible
pour démarrer. Si Mini et HUD sont masqués, la demande est ignorée ; masquer les
deux pendant la capture l'annule. L'indicateur et l'arrêt restent dans les deux
fenêtres, indépendamment de la page HUD. Le maintien pour parler n'est pas livré :
les événements pression/relâchement n'ont pas été validés matériellement.

## Wake word

[openWakeWord](https://github.com/dscripka/openWakeWord) propose `hey jarvis`, mais
ses modèles préentraînés visent l'anglais ; l'accent français doit être évalué.
Code Apache-2.0, modèles fournis CC-BY-NC-SA-4.0 selon le README officiel : vérifier
la licence de la version choisie avant distribution ou usage commercial.

Cette livraison contient uniquement la garde de scores injectable `WakeGate`,
testée avec seuil, trois scores consécutifs, cooldown et désactivation immédiate.
**Pas de moteur openWakeWord ni de capture continue raccordés.** Le contrôle HUD
reste indisponible et les commandes expliquent la limitation. Aucun téléchargement
implicite, aucune affirmation que « Hey Jarvis » fonctionne. Une intégration future
exigera activation explicite, indicateur permanent, arrêt pendant TTS et tests
sur faux positifs. Le mot-clé ne sera jamais une authentification et ne validera
jamais une action sensible. L'écoute continue consommerait du CPU et traiterait
également les conversations proches : c'est pourquoi elle reste désactivée.

## Confidentialité et dépannage

Aucun appel réseau dans le service vocal. Aucun microphone ouvert au démarrage,
même si l'autorisation est persistée. Aucun journal des transcriptions, aucune
sauvegarde audio proposée. PCM limité en RAM à 60 s maximum ; Whisper et Piper
utilisent des dossiers temporaires privés (0700), supprimés après succès, erreur
ou annulation. Un arrêt brutal du système/SIGKILL peut laisser ces temporaires ;
utiliser un TMPDIR en mémoire si cette menace importe. Pas de garantie d'effacement
physique de la RAM ou d'un support persistant. Aucun modèle dans Git.

- PipeWire : `wpctl status`, `pactl list short sources`, `pactl list short sinks`.
  Vérifier mute matériel, source sélectionnée et session utilisateur ; Jarvis ne
  modifie ni WirePlumber ni les réglages système. Absence de flux pendant 2 s : erreur.
- Whisper : modèle multilingue local, binaire exécutable, version supportant `-ojf`.
  Un JSON absent/incompatible est une erreur lisible. Pas de commande approchante.
- Piper : `.onnx.json` adjacent, version OHF, sortie disponible, vérifier `piper --help`.
  Les erreurs conservent le résultat écrit ; ne pas réexécuter une action pour réentendre.
- Les diagnostics Whisper sont lus en mémoire bornée puis supprimés ; seules
  les preuves de backend et mesures numériques sont conservées, sans texte privé.
  Pour diagnostiquer le moteur, utiliser un corpus non sensible hors Jarvis.

## AMD et mesures

Audit : Python projet 3.13.18 (système 3.14.8), PipeWire 1.6.9, WirePlumber 0.5.18,
Hyprland 0.56.2, Vulkan Radeon 860M / RADV KRACKAN1 / Mesa 26.2.5.
`vulkaninfo --summary` réussit. Ni ROCm ni le NPU ne sont utilisés.
L’utilisation réelle de Whisper Vulkan est vérifiée en V1.4.2 à chaque
transcription. Les [mesures Turbo CPU/Vulkan](VOICE_V1_4_2.md) incluent temps muraux
et RSS ; la RSS n’est pas la totalité de la mémoire GPU partagée. Les anciennes
[mesures V1.4.1](VOICE_V1_4_1.md) restent historiques. La précision sur voix humaine
n’est pas encore mesurée. Au repos le contrôleur ne crée aucun
thread audio ni sous-processus ; un timer Qt vérifie l'expiration toutes les 250 ms.
Cette propriété du code n'est pas une mesure de consommation matérielle.

## Corpus et recette manuelle

`tools/voice_corpus.py` contient quatre phrases françaises originales CC0-1.0 et
un générateur local volontaire Piper, avec benchmark Whisper optionnel :

```sh
uv run python tools/voice_corpus.py --voice /chemin/fr_FR-voix.onnx \
  --model /chemin/ggml-base.bin
```

Ce script crée exclusivement un nouveau dossier `voice-corpus/` privé, WAV et
manifest des phrases/résultats/temps. Il exige ffmpeg pour le rééchantillonnage du
benchmark. Il ne lit pas le micro et ne joue pas les commandes. Les temps incluent
le chargement CLI ; ce n'est pas une mesure séparée d'initialisation. Respecter la
licence de la voix pour redistribuer les WAV. **Le corpus audio n'a pas été généré
ici**, faute de modèle : seuls le texte et le générateur sont livrés.

- [ ] Installer volontairement les moteurs/modèles, vérifier licences et versions.
- [ ] Générer le corpus, écouter les phrases, comparer base et small sans commande réelle.
- [ ] Démarrer Jarvis : aucun flux microphone dans wpctl ; tester les erreurs de chemins.
- [ ] Tester micro/transcription, parole française et silence, durée max, arrêt, annulation.
- [ ] Débrancher le micro puis la sortie : erreur lisible, pas de flux laissé ouvert.
- [ ] Tester Piper, volume/vitesse, répétition, arrêt pendant génération puis lecture.
- [ ] Dire « Jarvis, aide » ; vérifier texte et clic requis, expiration 30 s, pas de doublon.
- [ ] Lancer un scénario de test : conserver la demande exacte V1.3 ; dicter son code
  doit être refusé, saisir le code doit conserver les validations V1.3.
- [ ] Tester Mini/HUD, masquer les deux pendant écoute, raccourcis J et V sans déplacement.
- [ ] Fermer pendant capture/STT/TTS, vérifier absence de processus et de temporaires.
- [ ] Redémarrer : préférences conservées, aucun microphone ouvert ; réseau déconnecté,
  toutes les étapes vocales doivent encore fonctionner avec les modèles installés.


## Raccordement V1.5

La page Assistant et `active IA` permettent d’interpréter les formulations libres.
Le contrôleur accepte alors une transcription inconnue du registre **en attente de
validation visible**, jamais directement en exécution. Après validation, le bus
choisit le registre prioritaire ou le moteur conversationnel. L’action éventuellement
proposée exige encore une confirmation IA, puis les confirmations historiques.
`confirme action IA CODE` est refusé à la voix comme les codes de scénarios et de
dispositions. IA inactive : le comportement V1.4.2 des commandes inconnues demeure.

Aucun second microphone ni moteur Piper. L’inférence IA et la capture/transcription/
synthèse ne démarrent pas simultanément dans le flux partagé. Résidence Ollama 0 par
défaut ; aucun modèle externe fermé de force. Texte intégral affiché, réponse vocale
courte ou message neutre existant, conservation du bouton de désactivation et des
timeouts. Voir [AI_V1_5.md](AI_V1_5.md). Les performances voix→LLM n’ont pas été
mesurées faute d’Ollama installé ; les mesures Whisper antérieures restent distinctes.
