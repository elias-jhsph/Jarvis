from google.api_core.exceptions import InvalidArgument
from google.cloud import texttospeech
from google.oauth2 import service_account
from connections import get_gcp_data
import uuid
import re

# Setup logging
import logger_config
logger = logger_config.get_logger()

# Load service account credentials
sa_creds = service_account.Credentials.from_service_account_info(get_gcp_data())

# Instantiate a Text-to-Speech client
client = texttospeech.TextToSpeechClient(credentials=sa_creds)


def text_to_speech(text: str, stream=False):
    text = re.sub("`", "", text)
    """
    Convert the given text to speech and save the result as an audio file.

    :param text: str, The text to be converted to speech.
    :return: str, The file path of the generated audio file.
    """

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-GB") and the voice
    # name ("en-GB-Neural2-B")
    voice = texttospeech.VoiceSelectionParams(
        {"language_code": "en-GB", "name": "en-GB-Neural2-B"}
    )

    # Configure the audio output settings
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=1.1,
        pitch=-5.5
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    try:
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
    except InvalidArgument as e:
        logger.warning(f'Sentence is too long to TTS: "{text}"')
        new = split_longest_sentence(text)
        if new != text:
            return text_to_speech(new)
        else:
            raise Exception("Can not shrink long sentence enough to turn to text")

    if stream:
        return response.audio_content

    # Save the binary audio content to a file
    output_file = str(uuid.uuid4())+".wav"
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
        logger.info(f'Audio content written to file "{output_file}"')

    return output_file


import re


def find_longest_sentence(text):
    # Split the text into sentences using regex
    sentences = re.split(r' *[\.\?!][\'"\)\]]* *', text)

    # Find the longest sentence
    longest_sentence = max(sentences, key=len)

    return longest_sentence


def split_longest_sentence(text, max_length=200):
    # Find the longest sentence
    longest_sentence = find_longest_sentence(text)

    # Split the longest sentence into chunks
    chunks = split_sentence(longest_sentence, max_length)

    # Replace the longest sentence in the text with the smaller sentences
    new_longest_sentence = '. '.join(chunks)
    modified_text = text.replace(longest_sentence, new_longest_sentence)

    return modified_text


def split_sentence(sentence, max_length=200):
    if len(sentence) <= max_length:
        return [sentence]

    words = sentence.split()
    chunks = []
    current_chunk = []

    for word in words:
        if len(" ".join(current_chunk) + " " + word) <= max_length:
            current_chunk.append(word)
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks