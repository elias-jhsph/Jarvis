import time
import speech_recognition as sr
import os
import certifi
import numpy as np
import pyaudio

os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

# Set up logging
import logger_config
logger = logger_config.get_logger()

r = sr.Recognizer()
mic = sr.Microphone()


def prep_mic():
    """
    Prepare the microphone for listening by adjusting it for ambient noise.
    """
    with mic as source:
        r.adjust_for_ambient_noise(source)
        logger.info("Microphone adjusted for ambient noise.")


def listen_to_user():
    """
    Listen to the user and record their speech, stopping when there's silence.

    :return: sr.AudioData, the recorded audio data
    """
    # Initialize PyAudio and create a stream
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=mic.SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=2048)

    audio_data = b''
    window_size = 10
    volume_buffer = []
    silence_duration = 0
    silence_threshold = 1.5
    start = time.time()

    logger.info("Listening to user...")

    while True:
        chunk = stream.read(2048)
        audio_data += chunk
        volume = np.frombuffer(chunk, dtype=np.int16)
        volume_buffer.append(np.average(np.abs(volume)))

        if len(volume_buffer) > window_size:
            volume_buffer.pop(0)

        avg_volume = np.average(volume_buffer)

        if avg_volume < r.energy_threshold and time.time() - start > 3:
            silence_duration += len(chunk) / mic.SAMPLE_RATE
        else:
            silence_duration = 0

        if silence_duration > silence_threshold:
            break

    # Close the stream and terminate PyAudio
    stream.stop_stream()
    stream.close()
    p.terminate()

    logger.info("Finished listening to user.")

    # Create an AudioData object from the recorded audio data
    return sr.AudioData(audio_data, mic.SAMPLE_RATE, 2)


def convert_to_text(audio):
    """
    Convert the given audio data to text using speech recognition.

    :param audio: sr.AudioData, the audio data to recognize
    :return: str, the recognized text from the audio
    """
    logger.info("Converting audio to text...")
    text = r.recognize_whisper(audio)
    logger.info("Recognized text: %s", text)
    return text
