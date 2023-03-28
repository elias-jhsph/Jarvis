import spacy
import time
import io
import queue
import threading
import numpy as np
from text_speech import text_to_speech
import pyaudio
import wave

nlp = spacy.load("en_core_web_sm", disable=["tagger", "parser", "ner"])
nlp.add_pipe("sentencizer")

CHUNK = 8196
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000


class SpeechStreamer:
    def __init__(self):
        self.queue = queue.Queue()
        self.playing = False
        self.thread = threading.Thread(target=self._play_audio)
        self.thread.daemon = True
        self.thread.start()
        self.stream = None
        self.py_audio = pyaudio.PyAudio()
        self.stop_event = threading.Event()
        self.audio_count = 0
        self.lock = threading.Lock()
        self.done = False

    def _play_audio(self):
        while True:
            generator, sample_rate = self.queue.get()
            if generator is None:
                next

            if not self.playing:
                self.playing = True
                if self.stream is None:
                    self.stream = self.py_audio.open(format=pyaudio.paInt16,
                                                     channels=CHANNELS,
                                                     rate=sample_rate,
                                                     output=True)
            chunk_played = False
            for chunk in generator:
                self.stream.write(chunk)
                chunk_played = True

            self.playing = False

            if chunk_played:
                with self.lock:
                    self.audio_count -= 1
                    print(f"Audio count: {self.audio_count}")
                    if self.audio_count == 0 and self.done:
                        self.stop_event.set()
                        print("Set stop_event")
            else:
                print("No chunks played")

    def queue_text(self, text, delay=0):
        with self.lock:
            self.audio_count += 1
        print(f"Queued text: {text}, audio count: {self.audio_count}")
        tts_thread = threading.Thread(target=self._process_text_to_speech, args=(text, delay,))
        tts_thread.daemon = True
        tts_thread.start()

    def stop(self):
        self.done = True
        self.stop_event.wait()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.py_audio.terminate()

    def _process_text_to_speech(self, text, delay):
        byte_data = text_to_speech(text, stream=True)
        time.sleep(delay)
        wav_io = io.BytesIO(byte_data)
        with wave.open(wav_io, 'rb') as wav_file:
            n_channels, sample_width, frame_rate, n_frames = wav_file.getparams()[:4]
            audio_data = wav_file.readframes(n_frames)

        # Convert audio data to numpy array
        np_audio_data = np.frombuffer(audio_data, dtype=np.int16)

        print(f"Generated audio for text: {text}, np_audio_data length: {len(np_audio_data)}")

        def generator():
            for i in range(0, len(np_audio_data), CHUNK):
                yield np_audio_data[i:i + CHUNK].tobytes()

        self.queue.put((generator(), frame_rate))


def stream_audio_response(streaming_text, stop_audio_event=None):
    if stop_audio_event is not None:
        stop_audio_event.set()
    speech_stream = SpeechStreamer()
    buffer = ""
    output = ""
    resp = None
    delay = 0.4
    for resp in streaming_text:
        if "choices" in resp:
            if "content" in resp["choices"][0]["delta"]:
                text = resp["choices"][0]["delta"]["content"]
                buffer += text
                output += text
                doc = nlp(buffer)
                sentences = list(doc.sents)

                if len(sentences) > 1:
                    for sentence in sentences[:-1]:
                        speech_stream.queue_text(sentence.text.strip(), delay=delay)
                        delay = 0

                    # Keep the last part (which may be an incomplete sentence) in the buffer
                    buffer = sentences[-1].text
    if resp:
        reason = resp["choices"][0]["finish_reason"]
    else:
        reason = "null"
    if reason != "stop":
        if reason == "length":
            buffer += "... I'm sorry, I have been going on and on haven't I?"
            output += "... I'm sorry, I have been going on and on haven't I?"
        if reason == "null":
            buffer += "I'm so sorry I got overwhelmed, can you put that more simply?"
            output += "I'm so sorry I got overwhelmed, can you put that more simply?"
        if reason == "content_filter":
            buffer += "I am so sorry, but if I responded to that I would have been forced to say something naughty."
            output += "I am so sorry, but if I responded to that I would have been forced to say something naughty."
    speech_stream.queue_text(buffer)
    speech_stream.stop()
    return output, reason
