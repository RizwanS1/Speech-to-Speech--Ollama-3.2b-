import os
import tempfile
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


class MicrophoneRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        max_duration: float = 20.0,
        silence_threshold: int = 500,
        silence_duration: float = 1.2,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_duration = max_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def record(self) -> bytes:
        self._stop_event.clear()
        block_size = 1024
        frames = []
        heard_voice = False
        silence_frames = 0
        max_blocks = int(self.max_duration * self.sample_rate / block_size)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=block_size,
        ) as stream:
            start_time = time.time()
            while not self._stop_event.is_set():
                data, _ = stream.read(block_size)
                if data is None:
                    continue

                amplitude = int(np.max(np.abs(data)))
                if not heard_voice:
                    if amplitude >= self.silence_threshold:
                        heard_voice = True
                        frames.append(data.copy())
                        silence_frames = 0
                    else:
                        continue
                else:
                    frames.append(data.copy())
                    if amplitude < self.silence_threshold:
                        silence_frames += 1
                        if silence_frames * block_size / self.sample_rate >= self.silence_duration:
                            break
                    else:
                        silence_frames = 0

                if len(frames) >= max_blocks:
                    break

                if time.time() - start_time >= self.max_duration:
                    break

        if not frames:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_path = temp_file.name
            with sf.SoundFile(temp_path, mode="w", samplerate=self.sample_rate, channels=self.channels, subtype="PCM_16") as f:
                f.write(np.zeros((0, self.channels), dtype="int16"))
            with open(temp_path, "rb") as handle:
                wav_bytes = handle.read()
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return wav_bytes

        audio = np.concatenate(frames, axis=0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
            sf.write(temp_path, audio, self.sample_rate, format="WAV")

        with open(temp_path, "rb") as handle:
            wav_bytes = handle.read()

        try:
            os.remove(temp_path)
        except OSError:
            pass

        return wav_bytes
