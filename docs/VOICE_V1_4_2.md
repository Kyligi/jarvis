# Voix V1.4.2 — Turbo et Radeon 860M

## Installation et provenance

Validation du 9 novembre 2026, Omarchy, AMD Radeon 860M Graphics
(RADV KRACKAN1), Mesa 26.2.5-arch1.1, API Vulkan 1.4.354.
`vulkaninfo --summary` échoue dans le sandbox sans accès matériel, mais réussit
hors sandbox. Ne pas confondre cette restriction avec une panne du pilote.
Aucun usage de ROCm ni du NPU.

Source whisper.cpp installée : `/home/kylian/Applications/whisper.cpp`, commit
`bd9e1a12352fa57e448bdea6a0649aa9c24c64aa`, version 1.9.5-dev.
Le README de ce commit documente `GGML_VULKAN`; son CMake exige Vulkan/glslc
et SPIRV-Headers. Installation autorisée via Omarchy de `vulkan-headers` et
`spirv-headers` 1:1.4.363.0-1. `shaderc` 2026.4-1 et le loader existaient déjà.
La première configuration a échoué faute d’en-têtes ; elle a réussi après
installation. Compilation GCC 16.2.1 terminée avec avertissements upstream,
sans modification des sources de calcul.

```sh
cmake -S /home/kylian/Applications/whisper.cpp \
  -B /home/kylian/Projects/jarvis-starter/.local/whisper-vulkan \
  -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /home/kylian/Projects/jarvis-starter/.local/whisper-vulkan \
  --target whisper-cli -j 4
```

[Instructions officielles Vulkan](https://github.com/ggml-org/whisper.cpp/blob/bd9e1a12352fa57e448bdea6a0649aa9c24c64aa/README.md#vulkan-gpu-support).
CMake génère aussi le fichier de métadonnées JavaScript dans les sources :
l’autorisation hors sandbox était nécessaire pour cette étape. Le `build` CPU
n’a pas été recompilé/remplacé. Le dossier `.local` est exclu de Git et doit
rester présent pour l’installation locale ; ses bibliothèques partagées font
partie du binaire Vulkan (ne pas déplacer seulement `whisper-cli`).

Téléchargement **explicitement autorisé** :
[ggml-large-v3-turbo.bin](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin),
source utilisée par le script officiel `models/download-ggml-model.sh`.
Modèle multilingue F16 non quantifié, environ 1,5 Gio. Téléchargé avec suffixe
`.part`, renommé seulement après comparaison avec le SHA-1 publié dans
[models/README.md](https://github.com/ggml-org/whisper.cpp/blob/bd9e1a12352fa57e448bdea6a0649aa9c24c64aa/models/README.md).

- SHA-1 attendu et obtenu : `4af2b29d7ec73d781377bfd1758ca957a807e941`.
- SHA-256 obtenu : `1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69`.
- Fichier local : `/home/kylian/Projects/jarvis-starter/.local/models/ggml-large-v3-turbo.bin`.

## Preuve d’exécution et mémoire

Essai CLI sur un WAV synthétique français, sans `-ng`, terminé avec code 0 :

```text
ggml_vulkan: 0 = AMD Radeon 860M Graphics (RADV KRACKAN1) (radv)
whisper_model_load:      Vulkan0 total size =  1623.92 MB
whisper_backend_init_gpu: using Vulkan0 backend
```

Le moteur a chargé 100 langues, 32 couches encodeur et 4 couches décodeur,
128 bandes mel, conformément au modèle Turbo. Sur « état système », il a
produit « Etat Système. ». Son premier chronométrage interne : chargement
477,29 ms, encodage 1 235,89 ms, total 2 435,61 ms. Ce total interne n’inclut
pas tout le coût de création/destruction du processus ; utiliser le benchmark
mural ci-dessous pour la latence utilisateur.

Le moteur annonce 1 623,92 Mo de poids sur Vulkan0 ; buffers de calcul :
37,69 + 55,35 + 39,99 + 100,04 Mo, caches KV : 10,49 + 31,46 + 7,86 Mo.
Ces allocations ne représentent pas un pic global de mémoire physique et
ne doivent pas être additionnées à la RSS comme si elles étaient disjointes.
L’iGPU dispose de 512 Mio de VRAM réservée et d’environ 15,23 Gio de GTT selon
sysfs : il utilise la mémoire partagée. La RSS est échantillonnée séparément
par processus, toutes les 50 ms au plus ; elle peut sous-estimer un pic bref
et ne mesure pas toute la mémoire GPU.

## Sélection et repli

Dans **Voix**, sélectionner le backend, les exécutables CPU/Vulkan distincts
et le modèle via le sélecteur de fichier local, puis **Enregistrer**. Les
modifications sont refusées pendant capture, transcription ou validation en
attente. Aucun téléchargement depuis le HUD. Le délai moteur est réglable.

- CPU : ancien `stt_executable`, toujours avec `-ng`.
- Vulkan : `gpu_executable`, **jamais `-ng`**.
- Vulkan non confirmé, binaire/modèle absent, erreur ou timeout : aucune
  transcription proposée à l’exécution. Choisir CPU explicitement, enregistrer
  et refaire une capture. Le même audio n’est jamais réexécuté sur CPU en secret.
- Pour revenir à l’installation CPU précédente, choisir CPU et le modèle
  `/home/kylian/Applications/whisper.cpp/models/ggml-small.bin` ; le binaire CPU
  `/home/kylian/Applications/whisper.cpp/build/bin/whisper-cli` est conservé.

Le HUD distingue backend demandé, chargement en cours et dernière transcription
validée. La preuve Vulkan exige à la fois une allocation positive de poids sur
Vulkan et sa sélection effective, avec code retour nul et absence de diagnostic
d’échec GPU. La seule présence d’un GPU ou d’une option de compilation ne suffit
pas. Le parseur vise les diagnostics du commit installé : un changement de
format upstream échoue de manière sûre plutôt que d’annoncer une accélération
non prouvée. Les diagnostics sont drainés sans blocage et sans journalisation
de texte ; seuls les booléens de preuve et mesures numériques sont conservés.

Capture PipeWire, tampon pré-enregistrement, estimation du bruit, arrêt sur
silence et Piper restent inchangés. Le silence rejeté par la capture n’atteint
pas Whisper. Un bruit au-dessus du seuil peut toujours le déclencher ; aucun
modèle ne garantit l’absence d’hallucination. Toute commande reconnue exige la
validation visible ; les confirmations sensibles restent au clavier. Ni le
modèle ni le backend ne contournent le registre. Chargement, inférence et
surveillance des processus restent dans le thread audio, hors Qt.

Le repli facultatif **sans VAD**, déjà existant, conserve le backend choisi et
un avertissement. V1.4.2 partage un seul budget de timeout entre les deux essais.
Aucun modèle Silero de production n’a été téléchargé et aucune performance VAD
n’est revendiquée. Les 69 commandes restent inchangées : pas d’ajout à `aide`.

## Benchmark reproductible

`tools/voice_turbo_benchmark.py` compare seulement Turbo CPU/Vulkan, sans base
ni small. Aucun microphone, aucune commande Jarvis, aucun accès au registre.
Le corpus synthétique Piper est généré explicitement avec les six phrases
historiques et 2 s de silence ; ce n’est pas un corpus de voix humaine.
Deux répétitions, ordre CPU/Vulkan puis Vulkan/CPU ; mêmes WAV, prompt vide,
VAD désactivé, français forcé, paramètres CLI par défaut, chargement inclus.
Aucun essai du rapport exclu. Le cache OS et les autres activités peuvent influencer
ces mesures ; ce n’est pas une étude statistique de performance.

```sh
uv run python tools/voice_corpus.py \
  --voice /home/kylian/Applications/piper-voices/fr_FR-siwis-medium.onnx \
  --piper /home/kylian/.local/bin/piper --benchmark-suite \
  --output /tmp/nouveau-corpus-turbo
uv run python tools/voice_turbo_benchmark.py /tmp/nouveau-corpus-turbo/manifest.json \
  --model /home/kylian/Projects/jarvis-starter/.local/models/ggml-large-v3-turbo.bin \
  --cpu /home/kylian/Applications/whisper.cpp/build/bin/whisper-cli \
  --vulkan /home/kylian/Projects/jarvis-starter/.local/whisper-vulkan/bin/whisper-cli \
  --repeats 2 --output /tmp/nouveau-rapport-turbo.json
```

Le rapport conserve les empreintes du modèle, des binaires et des WAV, les
hypothèses synthétiques, erreurs de mots (accents conservés), échecs, preuves
Vulkan, temps muraux et pics RSS. Un échec est exclu du WER et compté séparément.
La sortie sur silence compte comme insertion ; le benchmark contourne
volontairement le filtre de capture pour observer le moteur brut. Les sorties
interactives ne sont jamais conservées ainsi.

## Configuration locale activée et retour arrière

`/home/kylian/.local/share/jarvis/voice.toml` sélectionne désormais Vulkan,
le binaire `.local/whisper-vulkan/bin/whisper-cli` et le modèle Turbo local.
Sauvegarde exacte avant changement :
`/home/kylian/.local/share/jarvis/voice.pre-v1.4.2-20261109.toml` (permissions 0600).
Seuls les trois réglages de backend/binaire GPU/modèle changent de valeur ;
les nouvelles clés manquantes sont matérialisées avec leurs défauts V1.4.1.
Piper, périphériques, volume, confirmations et durée maximale utilisateur de
5 s sont conservés. Le HUD permet de choisir 12 s si une phrase plus longue
est souhaitée. Aucun microphone n’a été activé lors de l’installation.

Relancer le HUD pour charger cette configuration s’il était déjà ouvert.
Pour un retour complet aux préférences précédentes, fermer Jarvis, conserver
une copie des préférences courantes si elles ont été modifiées depuis, puis
restaurer le fichier de sauvegarde sous le nom `voice.toml`. Pour une bascule
simple, choisir CPU et l’ancien modèle small dans le HUD et enregistrer.
Le binaire CPU et ses modèles n’ont été ni remplacés ni supprimés.

## Résultats mesurés

[Rapport brut](benchmarks/voice-v1.4.2-turbo-synthetic.json), 7 extraits ×
2 répétitions par backend, 40 mots de référence par backend.

| Turbo | Essais / échecs | Temps mural moyen | Pic RSS échantillonné | WER avec insertions sur silence |
|---|---:|---:|---:|---:|
| CPU, binaire précédent avec `-ng` | 14 / 0 | 19,80 s | 1 811,48 Mio | 60 % |
| Vulkan, preuve effective sur chaque essai | 14 / 0 | 1,65 s | 200,10 Mio | 60 % |

Les deux backends produisent les mêmes hypothèses sur ce petit corpus. Sur
parole seulement, WER 35 % (14 erreurs / 40 mots), avec accents conservés.
Chaque backend invente « Sous-titrage Société Radio-Canada » sur les deux
essais de silence brut ; ces 10 insertions portent le WER global à 60 %.
« aide » reste mal reconnu (« Aïc. »). Ce résultat ne permet **pas** de promettre
une reconnaissance française suffisamment précise pour l’utilisateur.
L’accélération matérielle est fonctionnelle, mais le gain de précision sur voix
humaine n’est pas établi. Aucun nouveau test base/small n’a été demandé ni exécuté.

Le rapport moyen donne un rapport de latence CPU/Vulkan d’environ 12, mais la
première passe CPU prend 27,35 s/extrait contre 12,25 s à la seconde ; cette
variation n’est pas expliquée par la mesure. Les deux passes Vulkan sont à
1,65 s. Ne pas extrapoler un facteur fixe à tous les audios, machines ou états
énergétiques. Les tests automatisés ont aussi tourné pendant une partie de la
première passe CPU. L’essai initial de chargement Vulkan a précédé ce benchmark
et peut avoir rempli le cache de shaders ; aucun essai du benchmark n’a été
écarté. Les modèles sont rechargés à chaque fois mais les caches OS persistent.

Le pic RSS de 200 Mio ne signifie **pas** que Turbo tient dans 200 Mio : les
1 623,92 Mo de poids Vulkan et les allocations partagées GPU ne sont pas tous
représentés dans cette RSS. Les buffers annoncés par le moteur figurent plus haut.
L’essai synthétique direct de silence contourne le filtre de capture ; dans
Jarvis le silence numérique est rejeté avant Whisper. Cela n’annule pas le
risque d’hallucination sur bruit, d’où la validation visible obligatoire.

Validation logicielle : **447 tests réussis**, dont les 421 existants. Couverture
ajoutée : CPU/Vulkan/CPU, arguments `-ng`, backend réellement confirmé, refus du
GPU détecté mais inutilisé, modèle/binaire absent, erreurs, timeout, annulation,
drainage stderr volumineux, thread de transcription, sauvegarde et contrôles HUD,
silence et refus de confirmations sensibles vocales. Aucun changement V1.5.

Un essai d’intégration supplémentaire a relu les préférences réellement activées,
puis fait passer un WAV synthétique par `CaptureBuffer`, le worker du contrôleur
et Whisper Turbo en mode test uniquement : Vulkan validé, 1,35 s, RSS
échantillonnée 194 Mio. Le silence numérique a ensuite été filtré avant Whisper ;
aucune commande en attente. Cet essai ne remplace pas une recette au microphone.
