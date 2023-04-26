import time
import os
import wave
import certifi
import audioop
from io import BytesIO
from soundfile import read
from numpy import float32
from numpy import frombuffer, int16, average
from pyaudio import PyAudio, paInt16, get_sample_size
import whisper
from torch.cuda import is_available

import logger_config

logger = logger_config.get_logger()

os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

# Initialize the speech recognition module and microphone
paudio = PyAudio()
device_info = paudio.get_default_input_device_info()
paudio.terminate()
default_sample_rate = int(device_info["defaultSampleRate"])
default_sample_width = get_sample_size(paInt16)
current_energy_threshold = 300
dynamic_energy_adjustment_damping = 0.15
dynamic_energy_ratio = 1.5


def prep_mic(duration: float = 1.0) -> None:
    """
    Prepare the microphone for listening by adjusting it for ambient noise.

    :param duration: The duration to adjust the microphone for.
    :type duration: float
    :return: None
    """
    global current_energy_threshold
    chunk = 1024
    seconds_per_buffer = (chunk + 0.0) / default_sample_rate
    elapsed_time = 0

    p = PyAudio()
    stream = p.open(format=paInt16,
                    channels=1,
                    rate=default_sample_rate,
                    input=True,
                    frames_per_buffer=chunk)

    # adjust energy threshold until a phrase starts
    while True:
        elapsed_time += seconds_per_buffer
        if elapsed_time > duration:
            break
        buffer = stream.read(chunk)
        energy = audioop.rms(buffer, default_sample_width)  # energy of the audio signal

        # dynamically adjust the energy threshold using asymmetric weighted average
        damping = dynamic_energy_adjustment_damping ** seconds_per_buffer
        # account for different chunk sizes and rates
        target_energy = energy * dynamic_energy_ratio
        current_energy_threshold = current_energy_threshold * damping + target_energy * (1 - damping)
    p.terminate()
    logger.info("Microphone adjusted for ambient noise.")


def listen_to_user() -> BytesIO:
    """
    Listen to the user and record their speech, stopping when there's silence.

    :return: The recorded audio data.
    :rtype: BytesIO
    """
    # Initialize PyAudio and create a stream
    p = PyAudio()
    stream = p.open(format=paInt16,
                    channels=1,
                    rate=default_sample_rate,
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
        volume = frombuffer(chunk, dtype=int16)
        volume_buffer.append(average(abs(volume)))

        # Keep track of the average volume over the last window_size chunks
        if len(volume_buffer) > window_size:
            volume_buffer.pop(0)
        avg_volume = average(volume_buffer)

        # Keep track of the duration of silence
        if avg_volume < current_energy_threshold and time.time() - start > 3:
            silence_duration += len(chunk) / default_sample_rate
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

    # Fix this
    sample_rate = default_sample_rate
    sample_width = default_sample_width
    convert_rate = 16000

    if sample_rate != convert_rate:
        audio_data, _ = audioop.ratecv(audio_data, sample_width, 1, sample_rate, convert_rate, None)

    wave_file_data = BytesIO()
    # generate the WAV file contents
    wav_writer = wave.open(wave_file_data, "wb")
    try:  # note that we can't use context manager, since that was only added in Python 3.4
        wav_writer.setframerate(sample_rate)
        wav_writer.setsampwidth(sample_width)
        wav_writer.setnchannels(1)
        wav_writer.writeframes(audio_data)
        wave_file_data.seek(0)
    except Exception as e:
        # make sure resources are cleaned up
        logger.error(e)
        wav_writer.close()
    return wave_file_data


def convert_to_text(audio: BytesIO) -> str:
    """
    Convert the given audio data to text using speech recognition.

    :param audio: The audio data to convert.
    :type audio: BytesIO
    :return: str, the recognized text from the audio
    :rtype: str
    """
    logger.info("Converting audio to text...")
    model = whisper.load_model("base.en", download_root="whisper_models")
    array_audio, sampling_rate = read(audio)
    array_audio = array_audio.astype(float32)
    result = model.transcribe(array_audio, fp16=is_available())
    return result["text"]


if __name__ == "__main__":
    prep_mic()
    audio_test = listen_to_user()
    text = convert_to_text(audio_test)
    print(text)
