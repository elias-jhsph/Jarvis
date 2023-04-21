import time
import speech_recognition as sr
import os
import certifi
import numpy as np
import pyaudio
import logger_config
logger = logger_config.get_logger()

os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

# Initialize the speech recognition module and microphone
r = sr.Recognizer()
mic = sr.Microphone()


def prep_mic() -> None:
    """
    Prepare the microphone for listening by adjusting it for ambient noise.
    """
    with mic as source:
        r.adjust_for_ambient_noise(source)
        logger.info("Microphone adjusted for ambient noise.")


def listen_to_user() -> sr.AudioData:
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
    silence_threshold = 2.5
    start = time.time()

    logger.info("Listening to user...")

    while True:
        # Read a chunk of audio data from the stream
        chunk = stream.read(2048)
        audio_data += chunk

        # Calculate the volume of the audio data in the chunk
        volume = np.frombuffer(chunk, dtype=np.int16)
        volume_buffer.append(np.average(np.abs(volume)))

        # Keep track of the average volume over the last window_size chunks
        if len(volume_buffer) > window_size:
            volume_buffer.pop(0)
        avg_volume = np.average(volume_buffer)

        # Keep track of the duration of silence
        if avg_volume < r.energy_threshold and time.time() - start > 3:
            silence_duration += len(chunk) / mic.SAMPLE_RATE
        else:
            silence_duration = 0

        # Stop recording if there is enough silence
        if silence_duration > silence_threshold:
            break

    # Close the stream and terminate PyAudio
    stream.stop_stream()
    stream.close()
    p.terminate()

    logger.info("Finished listening to user.")

    # Create an AudioData object from the recorded audio data
    return sr.AudioData(audio_data, mic.SAMPLE_RATE, 2)


def convert_to_text(audio: sr.AudioData) -> str:
    """
    Convert the given audio data to text using speech recognition.

    :param audio: sr.AudioData, the audio data to recognize
    :type audio: sr.AudioData
    :return: str, the recognized text from the audio
    :rtype: str
    """
    logger.info("Converting audio to text...")
    # Use the whisper recognition model to recognize the speech in the audio data
    text = r.recognize_whisper(audio)
    logger.info("Recognized text: %s", text)
    return text
