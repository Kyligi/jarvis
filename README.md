# Jarvis

Assistant personnel modulaire pour Omarchy, avec interface PySide6.

## Installer

```bash
cd ~/Projects
git clone https://github.com/Kyligi/jarvis.git
cd jarvis
uv python install 3.13
uv sync
uv run jarvis
```

Prérequis : Linux avec Omarchy, Git et uv. Les commandes de bureau utilisent Hyprland et Foot.

## Commandes
- `aide`
- `statut`
- `projets rust`
- `Jarvis, reprends mon projet Rust`
- `ouvre rust NOM`

La reprise n'ouvre automatiquement un projet que lorsqu'un seul projet Rust est détecté. En cas de plusieurs projets, Jarvis demande de sélectionner le nom exact. Aucun code utilisateur n'est exécuté.

## Limites
Ce prototype ne comprend pas encore d'IA, de voix, d'intégration Spotify ni de domotique. La découverte de projets inspecte les dossiers à 1 ou 2 niveaux sous `~/Projects` sans suivre les symlinks. La mémoire SQLite se trouve dans `~/.local/share/jarvis/memory.sqlite3`.

## Données locales

L’historique des commandes reste dans la base SQLite locale. Les environnements Python, caches, sauvegardes, bases de données et fichiers `.env` sont exclus de Git par le `.gitignore`. Ne pas placer de clés ou de mots de passe dans le code source.
