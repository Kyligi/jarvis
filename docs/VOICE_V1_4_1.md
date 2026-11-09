# Voix V1.4.1 : audit et validation

## Audit et changements

V1.4 : PCM PipeWire mono signé 16 bits, 16 kHz ; seuil RMS fixe 0,015 ;
silence mesuré à l'horloge des lectures ; tout le silence initial conservé ;
maximum par défaut 15 s. Whisper français CPU sans VAD ni prompt. Piper,
registre, confirmations sensibles et IPC Mini sont indépendants de cette capture.
Les **384 tests initiaux** ont passé avant modification (3,89 s).

V1.4.1 traite des trames de 20 ms, même si PipeWire les fragmente. Un tampon
circulaire logique borné conserve les dernières 300 ms avant le franchissement
du seuil. Il existe uniquement après activation explicite du micro : rien ne peut
récupérer une syllabe prononcée avant l'ouverture effective du périphérique.
Le silence final est conservé (1,5 s par défaut), avec hystérésis à 60 % du seuil
après détection pour préserver les fins de mots faibles. Le silence est mesuré en
échantillons, indépendamment de l'ordonnancement des lectures. La durée totale
est limitée à la fois par le nombre d'échantillons et par l'horloge réelle.

L'estimation exponentielle du bruit ne suit que les trames initiales sous le
seuil ; le seuil effectif vaut max(seuil configuré, 2,5 × bruit estimé).
Cela reste une heuristique d'énergie : un bruit fort peut déclencher, une voix
faible peut être manquée. Silero intervient ensuite dans Whisper, pas dans
l'arrêt temps réel PipeWire. Aucun gain de WER n'est attribué à cette heuristique.

Les nouvelles options se règlent dans la page Voix ou `voice.toml` ; le choix
CPU/Vulkan avancé se règle dans le TOML. Exemple complet :
[voice.example.toml](examples/voice.example.toml).

| Paramètre | Défaut | Limites / rôle |
|---|---|---|
| `pre_recording_ms` | 300 | 0–1000 ms, avant détection uniquement |
| `max_recording_seconds` | 12 | 5–30 s, silence initial inclus |
| `adaptive_noise` | true | estimation du bruit initial |
| `silence_seconds` | 1.5 | 0,3–10 s de silence final |
| `vad_enabled` | false | Silero facultatif |
| `vad_model` | vide | fichier GGML local |
| `whisper_prompt` | vide | contexte facultatif, 256 caractères maximum |
| `compute_backend` | cpu | cpu ou vulkan |
| `gpu_executable` | vide | exécutable distinct, explicitement configuré |

Les anciennes configurations sans nouvelles clés chargent les défauts. Les
valeurs déjà enregistrées restent prioritaires : sur la machine auditée, le
modèle est **small** et le maximum **5 s**. Pour bénéficier de 12 s, enregistrer
cette valeur dans la page Voix. Les anciennes valeurs hors 5–30 doivent être
corrigées explicitement. Aucun fichier de préférences utilisateur n'a été modifié.

## Silero facultatif

L'aide du binaire installé (source whisper.cpp commit
`bd9e1a12352fa57e448bdea6a0649aa9c24c64aa`) confirme les options utilisées :
`--vad --vad-model CHEMIN --vad-speech-pad-ms 300 --vad-min-speech-duration-ms 100`.
Ces marges sont proposées pour les commandes courtes, sans gain mesuré à ce jour.

Installation **manuelle**, depuis une copie de whisper.cpp correspondant au binaire :

```bash
./models/download-vad-model.sh silero-v6.2.0
```

Puis renseigner le chemin absolu de `models/ggml-silero-v6.2.0.bin` et activer
`vad_enabled`. Voir le [README officiel whisper.cpp](https://github.com/ggml-org/whisper.cpp#voice-activity-detection-vad).
Ne pas utiliser les modèles `for-tests-*` comme modèles de production.
Jarvis ne lance jamais ce téléchargement. Modèle absent : repli CPU/GPU configuré
sans VAD et avertissement. Échec d'une invocation avec VAD : une seule nouvelle
tentative sans VAD ; une annulation ne provoque aucune nouvelle tentative.
Chaque invocation conserve son délai configuré (un repli peut donc doubler le
délai STT). Un JSON invalide reste une erreur, sans commande proposée.

## Contexte et sécurité

`whisper_prompt` reste vide par défaut. Essai facultatif :
`Jarvis, Omarchy, Hyprland, Rust, Python, Git, Steam, Notion.`
Le prompt est un biais de décodage, pas une instruction fiable contre les
hallucinations. Aucun prompt impératif, grammaire forcée, remplacement phonétique
ou correspondance approximative n'est ajouté. Ne garder ce contexte qu'après
comparaison sur le même corpus, notamment silence et phrases sans ces termes.
Le texte du contexte est transmis dans argv : ne pas y mettre de secrets.

« Aide-moi. » n'est jamais transformé en « aide ». Seule la ponctuation finale
d'une commande sans arguments peut être retirée, comme en V1.4. Toute commande
reconnue nécessite validation visible ; les confirmations sensibles restent
saisies dans la console. Les caractères de contrôle et textes trop longs sont
rejetés. Le score moyen de tokens n'est pas une probabilité de commande correcte.
Piper, les 69 commandes, l'aide et le raccourci Mini sont conservés.

## Benchmark reproductible

Créer volontairement un dossier privé contenant des WAV PCM mono 16 bits 16 kHz,
30 s maximum, et un `manifest.json` :

```json
[
  {"file": "aide.wav", "expected": "aide"},
  {"file": "phrase.wav", "expected": "Je développe avec Python et Rust sur Omarchy."},
  {"file": "silence.wav", "expected": ""}
]
```

Prévoir plusieurs locuteurs, répétitions, voix basse, bruit, pauses, phrases
courtes et longues et sons sans parole. Conserver exactement les mêmes fichiers
pour chaque comparaison ; ne pas réenregistrer entre modèles. Pour convertir
une copie : `ffmpeg -i original.wav -ar 16000 -ac 1 -c:a pcm_s16le copie.wav`.

```bash
uv run python tools/voice_benchmark.py /chemin/corpus/manifest.json \
  --base /chemin/ggml-base.bin --small /chemin/ggml-small.bin \
  --whisper /chemin/whisper-cli --vad-model /chemin/ggml-silero-v6.2.0.bin \
  --repeats 3 --output /chemin/resultats-sans-prompt.json
```

Répéter avec `--prompt 'Jarvis, Omarchy, Hyprland, Rust, Python, Git, Steam, Notion.'`
et un autre fichier de sortie. Le rapport contient les SHA-256 des WAV, modèles
et binaire, configuration, hypothèses, temps muraux incluant chargement modèle,
échecs, VAD demandé/effectif, repli et WER. Normalisation : NFC, minuscules Unicode,
ponctuation ignorée, accents conservés. WER = distance de Levenshtein en mots /
nombre de mots de référence ; le WER agrégé est pondéré par les mots, pas par
les extraits. Les échecs sont comptés séparément, jamais comme succès à WER nul.
Les sorties sur silence comptent comme hallucinations et insertions ; leur WER
individuel est indéfini. Sur parole, une erreur de mots n'est pas automatiquement
une hallucination : lire les hypothèses et annoter les inventions manuellement
(`review_required`). Les replis VAD sont exclus des agrégats VAD actif.

Aucun appel au registre ou au microphone. Les fichiers de benchmark et leurs
transcriptions sont persistants **uniquement à la demande de l'opérateur** ; les
sessions interactives restent temporaires. Utiliser un corpus non sensible.

## Préparation Vulkan Radeon 860M

`vulkaninfo --summary` vérifié : AMD Radeon 860M, RADV KRACKAN1, Mesa
26.2.5-arch1.1, API Vulkan 1.4.354. Le cache CMake actuel indique
`GGML_VULKAN=OFF`. Cela prouve la disponibilité du pilote, pas un gain Whisper.

Construction future volontaire dans un dossier distinct, jamais par-dessus `build` :

```bash
cmake -S /chemin/whisper.cpp -B /chemin/whisper.cpp/build-vulkan -DGGML_VULKAN=1 -DCMAKE_BUILD_TYPE=Release
cmake --build /chemin/whisper.cpp/build-vulkan -j --config Release
```

Dépendances : compilateur, CMake, en-têtes/loader Vulkan et compilateur de shaders
compatibles avec la version choisie ; vérifier les erreurs CMake sans toucher au
binaire CPU. [Instructions officielles](https://github.com/ggml-org/whisper.cpp#vulkan-gpu-support).
Comparer ensuite le corpus avec `--backend vulkan --whisper /chemin/build-vulkan/bin/whisper-cli`.
Vérifier dans une invocation CLI non sensible que Vulkan est réellement utilisé :
l'absence de `-ng` ne prouve pas l'accélération. Après validation seulement,
renseigner `gpu_executable` et `compute_backend = "vulkan"`. Le retour CPU est
`compute_backend = "cpu"` et garde l'ancien `stt_executable` avec `-ng`.
Pas de compilation, remplacement, activation GPU ou téléchargement effectué ici.

## Recette manuelle Omarchy

1. Ouvrir Mini avec le raccourci existant ; vérifier qu'aucun micro ne s'ouvre au
   démarrage. Tester Piper puis « arrête de parler » et le résultat textuel.
2. Dans Voix, régler maximum 12 s et tampon 300 ms. Utiliser **Tester micro /
   transcription**, attendre l'indication d'écoute, dire « aide », « état système »,
   puis des termes techniques. Ce bouton n'exécute rien.
3. Tester début doux, dernière syllabe faible, pause courte, silence complet,
   ventilateur et clavier. Comparer tampon 0/300 ms avec des extraits identiques
   pour une mesure ; l'appréciation en direct seule n'est pas une preuve de WER.
4. Tester les limites 5, 12, 30 s, second clic, annulation pendant capture/STT,
   débranchement et fermeture du HUD. Vérifier dans PipeWire qu'aucun `pw-record`
   Jarvis ne subsiste après chaque fin de session.
5. Essayer VAD absent puis modèle réel ; vérifier le message de repli et comparer
   le même corpus. Annuler pendant VAD : aucune transcription tardive proposée.
6. « Aide-moi », commande inventée et transcription ambiguë : aucune exécution.
   « aide » : validation explicite, aide complète. Tester scénario sensible :
   confirmation console toujours requise. Vérifier les commandes historiques.
7. Effectuer la comparaison base/small × VAD avec et sans prompt sur voix humaine.
   Ne changer le modèle, le prompt ou le backend par défaut qu'après ces mesures.

## Mesures locales du 9 novembre 2026

[Rapport brut et hypothèses](benchmarks/voice-v1.4.1-synthetic.json).
Six phrases synthétisées avec la voix installée `fr_FR-siwis-medium`, puis
rééchantillonnées par ffmpeg, et 2 s de silence numérique ; 20 mots de référence.
Une répétition par condition, CPU, prompt vide. Pour régénérer la même liste :

```bash
uv run python tools/voice_corpus.py --voice /chemin/fr_FR-siwis-medium.onnx \
  --benchmark-suite --output /chemin/nouveau-corpus
```

Le corpus de cette mesure se trouve dans `/tmp/jarvis-v141-corpus` (temporaire,
non livré dans Git). Le rapport garde ses empreintes ; régénérer avec une autre
version de Piper/voix peut changer l'audio. L'ordre fixe base puis small et le
cache OS peuvent biaiser les temps : répéter les mesures en inversant l'ordre
pour une étude de performance approfondie.

| Modèle / condition | WER | Temps moyen/extrait | Échecs | Hallucinations lexicales sur silence |
|---|---:|---:|---:|---:|
| base CPU sans VAD | 75 % (15/20) | 0,764 s | 0/7 | 0/1 |
| small CPU sans VAD | 125 % (25/20) | 2,658 s | 0/7 | 1/1 |
| base / small VAD demandé | non mesuré | non comparable | 0 | non évalué |

Les sept essais VAD de chaque modèle ont tous utilisé le repli sans VAD,
faute de modèle Silero de production. Ils ne constituent pas une mesure VAD.
Un WER peut dépasser 100 % à cause des insertions. Sur parole seule, base fait
15 erreurs/20 mots, small 16/20 ; small ajoute 9 mots sur le silence.
Exemples : « aide » → « H ! » (base), « Aïe ! » (small) ; « mes projets » correct
sur les deux. La prononciation synthétique des termes techniques est un facteur
confondant. Ces résultats ne démontrent **aucune amélioration de reconnaissance**,
aucun avantage général de base, ni l'effet du nouveau tampon sur une vraie voix.
Le benchmark contourne la capture : celle-ci est validée fonctionnellement par
les tests simulés, et doit encore être mesurée au microphone.

Validation automatisée finale : **421 tests réussis**, dont les 384 tests V1.4
conservés ; vérification des différences Git sans erreur de blancs.
