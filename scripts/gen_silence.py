import wave
import struct

def generate_silence(path='test16k.wav', duration_s=1.0, sample_rate=16000):
    n_frames = int(duration_s * sample_rate)
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        silence = struct.pack('<h', 0) * n_frames
        wf.writeframes(silence)

if __name__ == '__main__':
    generate_silence()
    print('Generated test16k.wav')
