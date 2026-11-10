# Audit préalable V1.5 — 10 novembre 2026

Dépôt propre au départ, HEAD `96e4438`, précédent `e607de0`. Aucun AGENTS.md
trouvé dans l'arborescence parente. Lecture de README, ARCHITECTURE, ROADMAP,
VALIDATION, SCENARIOS, VOICE et des notes V1.4.1/V1.4.2 avant modification.

- `registry.Command`, `resolve`, 69 entrées : alias et expressions historiques.
- `core.commands.execute` : exceptions présentables et journal limité aux identifiants.
- `interface.context.CommandBus` : un Runner commun Mini/HUD ; commandes d'arrêt hors verrou.
- `AppContext` : services, monitoring, préférences et VoiceBridge partagés.
- Projets : `projects.manager` (découverte, actif, Git, ouverture, sessions).
- Fenêtres : `services.windows.service` et `window_commands`, cibles revalidées,
  dispatchers Lua construits uniquement par le service, applications Jarvis protégées.
- Modes : `modes.manager`, profils et scénarios associés.
- Scénarios : `scenarios.engine.engine`, store, preview, request, confirm ;
  validation des déplacements par code unique, expiration et empreinte du plan.
- HUD : neuf widgets conservés dans l'ordre existant ; workers et vues inactives.
- Voix : PipeWireCapture → WhisperCLI subprocess terminé → transcription affichée
  et validation 30 s → VoiceBridge → CommandBus → PiperCLI ; réponse parlée déjà
  limitée à 240 caractères ou message neutre. Confirmation sensible uniquement console.

Validation initiale : `uv run pytest -q` → **447 passed in 7.15s**.
Aucun linter déclaré dans pyproject ; Python 3.13, PySide6 et psutil existants.

Matériel observé : lspci identifie AMD Krackan Radeon 840M/860M [1002:1114].
`ollama --version` : commande absente. `/api/version` local : connexion refusée.
`vulkaninfo --summary` dans l'environnement restreint : ERROR_INITIALIZATION_FAILED.
Ce diagnostic ne réfute pas les mesures Whisper V1.4.2 ; il ne prouve aucune
accélération LLM. Aucune installation, modification système ou capture micro.

Plan : backend et session indépendants de Qt ; catalogue typé et permissions ;
page Assistant et raccordement vocal ; validation automatisée et documentation.
Documentation officielle Ollama API vérifiée via Context7 et docs.ollama.com.
