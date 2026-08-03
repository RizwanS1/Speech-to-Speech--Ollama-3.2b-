import io

import sounddevice as sd
import soundfile as sf


class Speaker:
    def play_wav(self, wav_bytes: bytes) -> None:
        with io.BytesIO(wav_bytes) as audio_buffer:
            data, sample_rate = sf.read(audio_buffer, dtype="int16")
            sd.play(data, samplerate=sample_rate)
            sd.wait()

    def stop(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass
