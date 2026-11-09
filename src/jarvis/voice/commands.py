"""Registry handlers request actions through the application's Qt bridge."""
listener = None


def request(action):
    if listener is None:
        return 'Interface vocale non démarrée.'
    listener(action)
    return 'Demande vocale transmise à l’interface.'
