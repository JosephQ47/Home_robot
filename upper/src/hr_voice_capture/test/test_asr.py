"""V-1 and V-3 at the capture end: the wake gate and honest confidence."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hr_voice_capture.asr import (TextAdapter, Utterance, WakeWordGate,  # noqa: E402
                                  make_adapter)


def test_text_adapter_uses_the_default_confidence():
    a = TextAdapter(default_confidence=0.9)
    a.submit('去客厅')
    assert a.poll() == [Utterance('去客厅', 0.9)]


def test_text_adapter_parses_an_explicit_confidence():
    a = TextAdapter()
    a.submit('去客厅|0.42')
    assert a.poll()[0].confidence == pytest.approx(0.42)


def test_malformed_confidence_becomes_zero_not_one():
    """A parse failure must not be rounded up into a confident command."""
    a = TextAdapter()
    a.submit('去客厅|很确定')
    assert a.poll()[0].confidence == 0.0


def test_poll_drains_the_queue():
    a = TextAdapter()
    a.submit('停止')
    assert len(a.poll()) == 1
    assert a.poll() == []


def test_gate_is_shut_until_the_wake_word():
    g = WakeWordGate('小家', window_sec=5.0)
    assert g.feed('去客厅', 0.0) is False


def test_wake_word_itself_is_not_a_command():
    g = WakeWordGate('小家', window_sec=5.0)
    assert g.feed('小家', 0.0) is False
    assert g.feed('去客厅', 1.0) is True


def test_window_expires():
    g = WakeWordGate('小家', window_sec=5.0)
    g.feed('小家', 0.0)
    assert g.feed('去客厅', 4.99) is True
    g2 = WakeWordGate('小家', window_sec=5.0)
    g2.feed('小家', 0.0)
    assert g2.feed('去客厅', 5.01) is False


def test_one_wake_word_yields_one_command():
    g = WakeWordGate('小家', window_sec=5.0)
    g.feed('小家', 0.0)
    assert g.feed('去客厅', 1.0) is True
    g.close_window()
    assert g.feed('去厨房', 2.0) is False


def test_empty_wake_word_leaves_the_gate_open():
    assert WakeWordGate('').feed('去客厅', 0.0) is True


def test_unknown_adapter_is_refused():
    with pytest.raises(ValueError, match='unknown asr_adapter'):
        make_adapter('whisper-magic')


def test_vosk_adapter_requires_a_model():
    with pytest.raises(ValueError, match='model_path'):
        make_adapter('vosk')


def test_text_adapter_is_constructible_by_name():
    assert make_adapter('text').name == 'text'
