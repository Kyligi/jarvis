"""Descriptions du registre ; l'instance de session appartient au CommandBus."""

def request(action, *args):
    return 'Commande IA locale disponible dans Mini et la page Assistant du HUD.'


def route(session, text, executor):
    from dataclasses import replace

    from jarvis.registry import resolve
    resolved = resolve(text)
    if resolved is None:
        return session.respond(text)
    identifier = resolved.command.id
    if not identifier.startswith('ai.'):
        # Existing registry and command logging retain priority, including legacy aliases.
        return executor(text)
    action = identifier[3:]
    if action in ('open', 'talk'):
        return 'Assistant local ouvert. Saisir un message ; activer IA si nécessaire.'
    if action == 'status':
        return session.status()
    if action == 'model':
        return f'Modèle local : {session.config.model}. Sélection dans Assistant.'
    if action == 'clear':
        return session.clear()
    if action in ('stop', 'cancel'):
        return session.stop()
    if action == 'disable':
        session.clear()
        session.config = replace(session.config, enabled=False)
        return 'IA locale désactivée pour cette session.'
    if action == 'enable':
        session.configure(replace(session.config, enabled=action == 'enable'))
        return 'IA locale ' + ('activée' if action == 'enable' else 'désactivée') + ' pour cette session.'
    if action == 'confirm':
        return session.confirm(resolved.arguments[0])
    raise ValueError('Commande IA inconnue.')
