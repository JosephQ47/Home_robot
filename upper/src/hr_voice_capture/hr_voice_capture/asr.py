"""ASR behind a replaceable adapter.

No engine is frozen yet, and binding the project to one before the microphone
is even chosen would be a decision made for the wrong reason. So this module
fixes the *interface* — text plus a confidence, and a wake word gate — and
ships two adapters: a text one that reads typed lines (which makes the whole
voice chain runnable on a PC) and a Vosk one for when a microphone exists.

Confidence is not optional. hr_voice_command refuses anything below a threshold,
so an adapter that cannot report confidence must say so rather than return 1.0.

# @spec 家庭服务机器人技术方案.md#3.12.2
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Utterance:
    text: str
    confidence: float
    awake: bool = True


class AsrAdapter:
    """Interface every backend implements."""

    name = 'base'

    def poll(self):
        """Return a list of Utterance recognised since the last call."""
        raise NotImplementedError

    def close(self):
        pass


class TextAdapter(AsrAdapter):
    """Reads lines from a topic instead of a microphone.

    Lines are `text` or `text|confidence`. Used for PC runs and for replaying a
    transcript during acceptance, so the mapping and refusal rules can be
    exercised without audio hardware.
    """

    name = 'text'

    def __init__(self, default_confidence=0.95):
        self.default_confidence = default_confidence
        self.pending = []

    def submit(self, line: str):
        text, sep, raw = line.rpartition('|')
        if not sep:
            text, confidence = line, self.default_confidence
        else:
            try:
                confidence = float(raw)
            except ValueError:
                # A malformed confidence is not an excuse to assume a good one.
                text, confidence = line, 0.0
        self.pending.append(Utterance(text.strip(), confidence))

    def poll(self):
        out, self.pending = self.pending, []
        return out


class VoskAdapter(AsrAdapter):
    """Offline recognition with a Vosk model. Requires a model on disk."""

    name = 'vosk'

    def __init__(self, model_path, device=None, sample_rate=16000):
        import json
        import queue

        import sounddevice
        import vosk

        self._json = json
        self.model = vosk.Model(model_path)
        self.recognizer = vosk.KaldiRecognizer(self.model, sample_rate)
        self.recognizer.SetWords(True)
        self.queue = queue.Queue()
        self.stream = sounddevice.RawInputStream(
            samplerate=sample_rate, blocksize=8000, device=device, dtype='int16',
            channels=1, callback=lambda data, *_: self.queue.put(bytes(data)))
        self.stream.start()

    def poll(self):
        out = []
        while not self.queue.empty():
            chunk = self.queue.get()
            if self.recognizer.AcceptWaveform(chunk):
                result = self._json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                if not text:
                    continue
                words = result.get('result', [])
                # Vosk scores per word; the weakest word bounds the utterance,
                # because that is the word most likely to have been misheard.
                confidence = min((w.get('conf', 0.0) for w in words), default=0.0)
                out.append(Utterance(text, float(confidence)))
        return out

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:  # noqa: BLE001 - closing a dead stream is not an error
            pass


class WakeWordGate:
    """Opens a listening window for a while after the wake word is heard.

    Without this every stray sentence in the room becomes a command candidate.
    With an empty wake word the gate stays open, which is only appropriate for
    a bench run.
    """

    def __init__(self, wake_word: str, window_sec: float = 8.0):
        self.wake_word = (wake_word or '').strip()
        self.window_sec = window_sec
        self.open_until = float('-inf')

    def feed(self, text: str, now: float) -> bool:
        if not self.wake_word:
            return True
        if self.wake_word in text:
            self.open_until = now + self.window_sec
            return False      # the wake word itself is not a command
        return now < self.open_until

    def close_window(self):
        """Shut the window after a command is accepted, so one wake word yields
        one command rather than a burst."""
        self.open_until = float('-inf')


def make_adapter(kind, model_path='', device=None, logger=None):
    if kind == 'text':
        if logger:
            logger.warning('hr_voice_capture is using the TEXT adapter: '
                           'utterances come from /voice/text_in, not a microphone')
        return TextAdapter()
    if kind == 'vosk':
        if not model_path:
            raise ValueError('the vosk adapter needs model_path')
        return VoskAdapter(model_path, device)
    raise ValueError(f'unknown asr_adapter "{kind}"; use "text" or "vosk"')
