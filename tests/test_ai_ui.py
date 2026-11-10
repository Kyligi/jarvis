import threading
from dataclasses import replace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QTimer
from test_ai import FakeBackend, call
from test_interface import pump

from jarvis.ai.backend import Cancelled
from jarvis.interface.context import AppContext
from jarvis.interface.mini import JarvisWindow
from jarvis.monitoring.collector import Snapshot
from jarvis.voice.backends import Transcript
from jarvis.voice.controller import State


@pytest.fixture
def ai_ui(qapp):
    context = AppContext(collector=Mock(collect=Mock(return_value=Snapshot(1, 2, 3, None, {}))))
    session = context.commands.conversation
    session.config = replace(session.config, enabled=True)
    session.backend = FakeBackend('Bonjour')
    mini = JarvisWindow(context)
    mini.show()
    mini.open_hud()
    page = mini.hud.pages[9]
    try:
        yield context, mini, page
    finally:
        mini.close()
        qapp.processEvents()


def test_assistant_navigation_text_and_clear(ai_ui, qapp):
    context, mini, page = ai_ui
    assert len(mini.hud.pages) == 12
    assert context.commands.submit('ouvre assistant')
    pump(qapp, lambda: not context.commands.busy)
    assert mini.hud.navigation.currentRow() == 9
    page.input.setText('Bonjour mon ami')
    page.send()
    pump(qapp, lambda: not context.commands.busy)
    assert 'Vous : Bonjour mon ami' in page.output.toPlainText()
    assert 'Conversation IA — non vérifiée' in page.output.toPlainText()
    assert 'Bonjour' in mini.output.toPlainText()
    assert not page.grab().isNull()
    assert context.commands.submit('efface conversation')
    qapp.processEvents()
    assert context.commands.conversation.history == []
    assert 'Bonjour mon ami' not in page.output.toPlainText()
    assert 'Bonjour' not in mini.output.toPlainText()


def test_stop_responsive_and_single_bus(ai_ui, qapp):
    context, mini, page = ai_ui
    entered = threading.Event()
    def generate(config, messages, schema, cancelled, chunk):
        entered.set()
        assert cancelled.wait(2)
        raise Cancelled()
    context.commands.conversation.backend.generate = generate
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    try:
        assert context.commands.submit('Dis bonjour')
        pump(qapp, lambda: entered.is_set() and len(ticks) >= 3)
        assert not context.commands.submit('aide')
        page.stop.click()
        pump(qapp, lambda: not context.commands.busy)
        assert 'annulée' in mini.output.toPlainText()
        assert context.commands.conversation.pending is None
    finally:
        timer.stop()


def test_immediate_stop_is_not_lost(ai_ui, qapp):
    context, _, _ = ai_ui
    s = context.commands.conversation
    s.prepare()
    s.stop()
    assert 'annulée' in s.respond('Bonjour')
    assert s.backend.messages == []


def test_voice_natural_language_needs_visible_validation(ai_ui, qapp, project):
    context, mini, page = ai_ui
    bridge = context.voice
    controller = bridge.controller
    controller.config = replace(controller.config, enabled=True, spoken_responses=False)
    controller.capture = Mock(capture=Mock(return_value=b'\0\1' * 16000))
    controller.stt = Mock(transcribe=Mock(return_value=Transcript('Affiche mes projets.', .9)))
    controller.tts = Mock()
    s = context.commands.conversation
    s.backend = FakeBackend(calls=[call('list_projects')])
    bridge.toggle()
    controller.thread.join(2)
    assert controller.snapshot.state == State.AWAITING_CONFIRMATION
    assert s.backend.messages == []
    bridge.confirm()
    pump(qapp, lambda: not context.commands.busy)
    assert 'ProjetÉcole' in mini.output.toPlainText()
    assert len(s.backend.messages) == 1
    controller.tts.speak.assert_not_called()
    assert controller.snapshot.state == State.IDLE


def test_voice_validation_does_not_approve_llm_action(ai_ui, qapp, project):
    context, _, _ = ai_ui
    c = context.voice.controller
    c.config = replace(c.config, enabled=True)
    c.capture = Mock(capture=Mock(return_value=b'\0\1'))
    c.stt = Mock(transcribe=Mock(return_value=Transcript('Je voudrais voir un autre espace.', .9)))
    s = context.commands.conversation
    s.backend = FakeBackend(calls=[call('switch_workspace', number=3)])
    context.voice.toggle()
    c.thread.join(2)
    context.voice.confirm()
    pump(qapp, lambda: not context.commands.busy)
    assert s.pending is not None
    assert 'Action proposée' in c.last_response
    c.stt.transcribe.return_value = Transcript('confirme action IA ' + s.pending.token, .99)
    context.voice.toggle()
    c.thread.join(2)
    assert c.snapshot.state == State.ERROR
    assert c.pending is None


@pytest.mark.parametrize('state', [State.LISTENING, State.TRANSCRIBING, State.SPEAKING])
def test_no_concurrent_voice_and_llm(ai_ui, state):
    context, _, _ = ai_ui
    context.voice.controller.emit(state)
    assert not context.commands.submit('Une question libre')
    assert context.commands.conversation.backend.messages == []


def test_no_microphone_during_generation(ai_ui, qapp):
    context, _, _ = ai_ui
    context.commands.busy = True
    context.voice.controller.capture = Mock()
    context.voice.toggle()
    context.voice.controller.capture.capture.assert_not_called()
    context.commands.busy = False


def test_ai_preferences_dont_touch_voice_or_ui(ai_ui, qapp, tmp_path):
    context, _, page = ai_ui
    page.model.setCurrentText('qwen3:4b')
    page.retain.setChecked(False)
    page.apply_settings(True)
    pump(qapp, lambda: not context.commands.busy)
    assert (tmp_path / 'ai.toml').exists()
    assert not (tmp_path / 'voice.toml').exists()
    assert not (tmp_path / 'ui.toml').exists()
    assert not context.commands.conversation.config.retain_context


def test_late_reply_after_clear_is_discarded(ai_ui, qapp):
    from jarvis.interface.context import ConversationReply
    context, mini, page = ai_ui
    cancellation = context.commands.conversation.cancelled
    context.commands.submit('efface conversation')
    context.commands.receive_result(ConversationReply('secret ancien résultat', cancellation))
    context.commands.ai_event.emit({'kind': 'progress', 'text': 'secret ancien brouillon', 'characters': 20, 'cancelled': cancellation})
    qapp.processEvents()
    assert 'secret' not in page.output.toPlainText()
    assert 'secret' not in mini.output.toPlainText()
    assert 'secret' not in page.progress.text()


@pytest.mark.parametrize('text', ['confirme action IA 1234abcd.', 'confirme scénario 1234abcd!', 'confirme disposition 1234abcd?'])
def test_punctuated_voice_confirmation_still_refused(ai_ui, text):
    context, _, _ = ai_ui
    c = context.voice.controller
    c.config = replace(c.config, enabled=True)
    c.capture = Mock(capture=Mock(return_value=b'\0\1'))
    c.stt = Mock(transcribe=Mock(return_value=Transcript(text, .99)))
    context.voice.toggle()
    c.thread.join(2)
    assert c.snapshot.state == State.ERROR
    assert c.pending is None
