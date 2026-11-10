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

    # ==========================================
    # V1.6 — HISTORIQUE CONVERSATIONNEL
    # ==========================================

    if action == "history.enable":
        session.set_conversation_persistence(True)
        return (
            "Historique IA activé pour cette session. "
            "Les échanges conversationnels éligibles seront enregistrés "
            "dans une conversation créée ou reprise."
        )

    if action == "history.disable":
        session.set_conversation_persistence(False)
        return (
            "Historique IA désactivé. "
            "Les conversations déjà enregistrées sont conservées."
        )

    if action == "history.status":
        enabled = session.persist_conversations
        identifier = session.conversation_id

        state = "activé" if enabled else "désactivé"
        current = (
            f"Conversation actuelle : n° {identifier}"
            if identifier is not None
            else "Aucune conversation persistante sélectionnée."
        )

        return (
            f"Historique IA : {state}\n"
            f"{current}\n"
            "Stockage local SQLite uniquement."
        )

    if action == "history.new":
        if not session.persist_conversations:
            return (
                "Active d'abord l'historique IA avec "
                "« active historique IA »."
            )

        conversation = session.start_persistent_conversation()

        if conversation is None:
            return "Stockage des conversations indisponible."

        return (
            f"Nouvelle conversation créée : n° {conversation.id}\n"
            "Tu peux maintenant discuter avec Jarvis."
        )

    if action == "history.list":
        store = session.conversation_service

        if store is None or not store.enabled:
            return "Stockage des conversations indisponible."

        conversations = store.list_conversations()

        if not conversations:
            return "Aucune conversation enregistrée."

        lines = ["CONVERSATIONS ENREGISTRÉES"]

        for conversation in conversations[:30]:
            lines.append(
                f"• {conversation.id} — {conversation.title}"
            )

        if len(conversations) > 30:
            lines.append(
                f"… {len(conversations) - 30} conversation(s) supplémentaires."
            )

        return "\n".join(lines)

    if action == "history.resume":
        if not session.persist_conversations:
            return (
                "Active d'abord l'historique IA avec "
                "« active historique IA »."
            )

        conversation_id = int(resolved.arguments[0])

        if conversation_id <= 0:
            return "Identifiant de conversation invalide."

        if session.resume_conversation(conversation_id):
            return (
                f"Conversation n° {conversation_id} reprise.\n"
                "Le contexte précédent est de nouveau disponible."
            )

        return "Conversation introuvable ou inaccessible."

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
