import os
import sys
import queue
import threading
import time
import wave
import io
import warnings
from queue import Queue
from numpy import frombuffer, int16
from pyaudio import PyAudio, paInt16
import en_core_web_sm
from typing import Iterator, Dict, Tuple, Optional
from text_speech import text_to_speech, TextToSpeechError

warnings.filterwarnings("ignore", category=UserWarning, module="spacy.pipeline.lemmatizer", lineno=211)

nlp = en_core_web_sm.load(disable=["tagger", "parser", "ner"])
nlp.add_pipe("sentencizer")

CHUNK = 8196
FORMAT = paInt16
CHANNELS = 1
RATE = 16000

rt_text_queue_global = None


class SpeechStreamer:
    """
    A class for streaming text-to-speech audio.

    :param stop_other_audio: A threading.Event() to stop any currently playing audio.
    :type stop_other_audio: threading.Event(), optional
    :param skip: A threading.Event() to skip the current audio stream.
    :type skip: threading.Event(), optional
    :param rt_queue: A queue to send real-time transcription data.
    :type rt_queue: queue.Queue(), optional
    """

    def __init__(self, stop_other_audio: threading.Event = None,
                 skip: threading.Event = None, rt_queue: queue.Queue = None) -> None:
        """
        Initializes the SpeechStreamer class with default values.

        The class instance is created with a queue for handling the text-to-speech
        audio, and the corresponding thread is started to play the audio. The PyAudio
        module is also used to initialize the class instance with parameters to control
        the audio format and output.

        :param stop_other_audio: A threading.Event() to stop any currently playing audio.
        :type stop_other_audio: threading.Event(), optional
        :param skip: A threading.Event() to skip the current audio stream.
        :type skip: threading.Event(), optional
        :param rt_queue: A queue to send real-time transcription data.
        :type rt_queue: queue.Queue(), optional
        """
        self.queue = queue.Queue()
        self.rt_queue = rt_queue
        self.playing = False
        self.thread = threading.Thread(target=self._play_audio, args=(stop_other_audio, skip))
        self.thread.daemon = True
        self.thread.start()
        self.stream = None
        self.py_audio = PyAudio()
        self.stop_event = threading.Event()
        self.skip = skip
        self.audio_count = 0
        self.lock = threading.Lock()
        self.done = False

    def _play_audio(self, stop_other_audio: threading.Event = None,
                    skip: threading.Event = None) -> None:
        """
        Plays the audio stream generated from the text-to-speech data.

        The audio stream is played by iterating over the audio buffer chunk by chunk,
        and writing each chunk to the PyAudio instance. The class instance is also
        initialized with a threading.Lock() to prevent conflicts when accessing
        the audio_count variable.

        :param stop_other_audio: A threading.Event() to stop any currently playing audio.
        :type stop_other_audio: threading.Event(), optional
        :param skip: A threading.Event() to skip the current audio stream.
        :type skip: threading.Event(), optional
        """
        while True:
            generator, sample_rate = self.queue.get()
            if generator is None:
                next
            else:
                if stop_other_audio:
                    stop_other_audio.set()

            if not self.playing:
                self.playing = True
                if self.stream is None:
                    self.stream = self.py_audio.open(format=paInt16,
                                                     channels=CHANNELS,
                                                     rate=sample_rate,
                                                     output=True,
                                                     frames_per_buffer=CHUNK)
            chunk_played = False
            for chunk in generator:
                if skip:
                    if skip.is_set():
                        self.stop()
                        return
                self.stream.write(chunk)
                chunk_played = True

            self.playing = False

            if chunk_played:
                with self.lock:
                    self.audio_count -= 1
                    if self.audio_count == 0 and self.done:
                        self.stop_event.set()

    def queue_text(self, text: str, delay: float = 0, model: str = "gpt-4") -> None:
        """
        Queues the text data for text-to-speech processing.

        The text data is queued and passed to the _process_text_to_speech() function to be
        converted to audio. A threading.Lock() is used to prevent conflicts when accessing
        the audio_count variable.

        :param text: The text data to be converted to speech.
        :type text: str
        :param delay: The delay time in seconds before playing the audio.
        :type delay: float, optional
        :param model: The text-to-speech model to be used for conversion.
        :type model: str, optional
        """
        with self.lock:
            self.audio_count += 1
        tts_thread = threading.Thread(target=self._process_text_to_speech, args=(text, delay, model, self.rt_queue))
        tts_thread.daemon = True
        tts_thread.start()

    def stop(self) -> None:
        """
        Stops the audio stream and PyAudio instance.

        The function stops the audio stream and PyAudio instance by closing the audio
        stream and terminating the PyAudio instance. A threading.Event() is used to
        ensure that the audio stream is stopped before closing the stream.

        """
        self.done = True
        if self.skip is None:
            self.stop_event.wait()
        else:
            while self.stop_event.is_set() is False and self.skip.is_set() is False:
                self.skip.wait(timeout=1)
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.py_audio.terminate()

    def _process_text_to_speech(self, text: str, delay: float, model: str, rt_text: queue.Queue) -> None:
        """
        Processes the text data into audio format.

        The text data is passed to the text_to_speech() function for processing
        and conversion into audio format. The audio data is then converted to a numpy array
        and passed to the queue to be played as audio. The real-time transcription data
        is also added to the queue.

        :param text: The text data to be converted to speech.
        :type text: str
        :param delay: The delay time in seconds before playing the audio.
        :type delay: float
        :param model: The text-to-speech model to be used for conversion.
        :type model: str
        :param rt_text: A queue to send real-time transcription data.
        :type rt_text: queue.Queue()
        """
        try:
            byte_data = text_to_speech(text, stream=True, model=model)
        except TextToSpeechError as e:
            return
        time.sleep(delay)
        wav_io = io.BytesIO(byte_data)
        with wave.open(wav_io, 'rb') as wav_file:
            n_channels, sample_width, frame_rate, n_frames = wav_file.getparams()[:4]
            audio_data = wav_file.readframes(n_frames)

        # Convert audio data to numpy array
        np_audio_data = frombuffer(audio_data, dtype=int16)

        def generator():
            for i in range(0, len(np_audio_data), CHUNK):
                yield np_audio_data[i:i + CHUNK].tobytes()
        rt_text.put({"role": "assistant", "content": text, "model": model})
        self.queue.put((generator(), frame_rate))


def stream_audio_response(streaming_text: Iterator[Dict], stop_audio_event: Optional[threading.Event] = None,
                          skip: Optional[threading.Event] = None) -> Tuple[str, str]:
    """
    Streams the audio response.

    The function receives a streaming_text object containing the text data
    that needs to be converted to speech. The text data is processed and converted
    to speech using the SpeechStreamer class. The real-time transcription data is
    passed to the global rt_text_queue_global variable.

    :param streaming_text: An iterator containing the streaming text data.
    :type streaming_text: Iterator[Dict]
    :param stop_audio_event: An event object to stop the audio stream, defaults to None.
    :type stop_audio_event: threading.Event, optional
    :param skip: An event object to skip the audio stream, defaults to None.
    :type skip: threading.Event, optional
    :return: A tuple containing the output text and the finish reason.
    :rtype: Tuple[str, str]
    """
    global rt_text_queue_global
    speech_stream = SpeechStreamer(stop_other_audio=stop_audio_event, skip=skip, rt_queue=rt_text_queue_global)
    buffer = ""
    output = ""
    resp = None
    delay = 0.5
    model = None
    for resp in streaming_text:
        if skip:
            if skip.is_set():
                break
        if "choices" in resp:
            if model is None:
                model = resp['model']
            if "content" in resp["choices"][0]["delta"]:
                text = resp["choices"][0]["delta"]["content"]
                buffer += text
                output += text
                doc = nlp(buffer)
                sentences = list(doc.sents)

                if len(sentences) > 1:
                    merged_sentences = []
                    i = 0
                    while i < len(sentences) - 1:
                        current_sentence = sentences[i].text.strip()
                        next_sentence = sentences[i + 1].text.strip()

                        if len(current_sentence) < 50:
                            current_sentence += " " + next_sentence
                            i += 2
                        else:
                            i += 1
                        merged_sentences.append(current_sentence)

                    if i == len(sentences) - 1:
                        merged_sentences.append(sentences[-1].text.strip())

                    for sentence in merged_sentences[:-1]:
                        speech_stream.queue_text(sentence, delay=delay, model=model)
                        delay = 0

                    # Keep the last part (which may be an incomplete sentence) in the buffer
                    buffer = merged_sentences[-1]
    if skip:
        if skip.is_set():
            return "Sorry.", "null"
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


def set_rt_text_queue(rt_text_queue: Queue) -> None:
    """
    Set the global rt_text_queue_global variable to the given rt_text_queue.

    :param rt_text_queue: A queue containing the real-time text data.
    :type rt_text_queue: Queue
    """
    global rt_text_queue_global
    rt_text_queue_global = rt_text_queue
