import threading
import tkinter as tk
from io import BytesIO
from typing import Optional

from PIL import Image, ImageTk

from assistant.client.api import AssistantAPI
from assistant.client.microphone import MicrophoneRecorder
from assistant.client.speaker import Speaker
from assistant.client.webcam import WebcamClient


class AssistantGUI:
    def __init__(self, api_url: str = "http://127.0.0.1:8000") -> None:
        self.api = AssistantAPI(base_url=api_url)
        self.recorder = MicrophoneRecorder()
        self.speaker = Speaker()
        self.webcam = WebcamClient()
        self.root = tk.Tk()
        self.root.title("AI Voice Assistant")
        self.root.geometry("640x760")
        self.video_label: Optional[tk.Label] = None
        self.status_label: Optional[tk.Label] = None
        self.chat_text: Optional[tk.Text] = None
        self.start_button: Optional[tk.Button] = None
        self.stop_button: Optional[tk.Button] = None
        self.fast_forward_button: Optional[tk.Button] = None
        self._running = False
        self._playing = False
        self._thread: Optional[threading.Thread] = None
        self._create_layout()

    def _create_layout(self) -> None:
        header = tk.Label(self.root, text="AI Voice Assistant", font=("Arial", 18, "bold"))
        header.pack(pady=10)

        self.chat_text = tk.Text(self.root, state="disabled", wrap="word", height=14)
        self.chat_text.pack(fill="both", expand=False, padx=10, pady=10)

        controls = tk.Frame(self.root)
        controls.pack(pady=8)

        self.start_button = tk.Button(controls, text="Start", width=12, command=self.start)
        self.start_button.grid(row=0, column=0, padx=6)

        self.stop_button = tk.Button(controls, text="Stop", width=12, command=self.stop, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=6)

        self.fast_forward_button = tk.Button(controls, text="Fast Forward", width=12, command=self.fast_forward, state="disabled")
        self.fast_forward_button.grid(row=0, column=2, padx=6)

        self.status_label = tk.Label(self.root, text="Status: idle", anchor="w")
        self.status_label.pack(fill="x", padx=10)

        self.video_label = tk.Label(self.root)
        self.video_label.pack(padx=10, pady=10)

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._set_status("Starting assistant...")
        self._set_buttons(enabled=False)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._start_webcam_feed()

    def stop(self) -> None:
        self._running = False
        self.recorder.stop()
        self.speaker.stop()
        self._set_status("Stopped")
        self.webcam.close()
        self._set_buttons(enabled=True)

    def _set_status(self, message: str) -> None:
        if self.status_label:
            self.status_label.configure(text=f"Status: {message}")

    def _set_buttons(self, enabled: bool) -> None:
        if self.start_button:
            self.start_button.configure(state="normal" if enabled else "disabled")
        if self.stop_button:
            self.stop_button.configure(state="disabled" if enabled else "normal")
        if self.fast_forward_button:
            self.fast_forward_button.configure(state="normal" if not enabled else "disabled")

    def _append_chat(self, prefix: str, message: str) -> None:
        if self.chat_text:
            self.chat_text.configure(state="normal")
            self.chat_text.insert(tk.END, f"{prefix}: {message}\n")
            self.chat_text.see(tk.END)
            self.chat_text.configure(state="disabled")

    def _start_webcam_feed(self) -> None:
        try:
            self.webcam.open()
            self._update_webcam_frame()
        except Exception as exc:
            self._append_chat("Error", str(exc))
            self._set_status("Webcam unavailable")

    def _update_webcam_frame(self) -> None:
        if not self._running or self.webcam.capture is None:
            return

        try:
            frame_bytes = self.webcam.get_frame()
            image = Image.open(BytesIO(frame_bytes))
            photo = ImageTk.PhotoImage(image=image)
            if self.video_label:
                self.video_label.imgtk = photo
                self.video_label.configure(image=photo)
        except Exception as exc:
            self._append_chat("Error", f"Webcam frame failed: {exc}")

        self.root.after(100, self._update_webcam_frame)

    def _run_loop(self) -> None:
        try:
            while self._running:
                self._set_status("Recording audio...")
                wav_bytes = self.recorder.record()
                if not self._running:
                    break

                self._set_status("Sending audio for transcription...")
                recognized_text = self.api.speech_to_text(wav_bytes)
                if not self._running:
                    break

                if not recognized_text.strip():
                    self._append_chat("Assistant", "No speech detected, retrying...")
                    continue

                self._append_chat("User", recognized_text)
                if recognized_text.lower().strip() in {"exit", "quit", "stop"}:
                    self._append_chat("System", "Exit command received, stopping assistant.")
                    self.stop()
                    break

                self._set_status("Requesting chat response...")
                reply = self.api.chat(recognized_text)
                self._append_chat("Bot", reply)

                self._set_status("Requesting speech synthesis...")
                wav_response = self.api.text_to_speech(reply)
                self._set_status("Playing response...")
                self._playing = True
                self.speaker.play_wav(wav_response)
                self._playing = False
                if not self._running:
                    break
                self._set_status("Waiting for next input...")
        except Exception as exc:
            self._append_chat("Error", str(exc))
            self._set_status("Error occurred")
            self._running = False
        finally:
            self._set_buttons(enabled=True)

    def fast_forward(self) -> None:
        if not self._playing:
            return

        self._set_status("Fast forwarding...")
        self.speaker.stop()

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.mainloop()


if __name__ == "__main__":
    gui = AssistantGUI()
    gui.run()
