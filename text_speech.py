from google.api_core.exceptions import InvalidArgument
from google.cloud import texttospeech
from google.oauth2 import service_account
from connections import get_gcp_data
from gtts import gTTS
from pydub import AudioSegment
import uuid
import io
import re

# Setup logging
import logger_config
logger = logger_config.get_logger()

# Load service account credentials and instantiate a Text-to-Speech client
try:
    sa_creds = service_account.Credentials.from_service_account_info(get_gcp_data())
    client = texttospeech.TextToSpeechClient(credentials=sa_creds)
    gcp_available = True
except Exception as e:
    logger.warning("Failed to get GCP credentials, using free text-to-speech alternative")
    gcp_available = False


class TextToSpeechError(Exception):
    def __init__(self, sentence):
        self.sentence = sentence
        super().__init__(f"The following sentence was too long to turn into voice '{self.sentence}'.")


def text_to_speech(text: str, stream=False, model="gpt-4"):
    """
    Convert the given text to speech and save the result as an audio file.

    :param text: str, The text to be converted to speech.
    :param stream: bool, Whether to return the audio content as a stream or save it to a file.
    :param model: str, The model used to generate the text.
    :return: str, The file path of the generated audio file.
    """
    text = simplify_urls(re.sub("`", "", text))

    # If GCP is not available, use the free text-to-speech alternative
    if not gcp_available:
        return free_text_to_speech(text, stream=stream, model=model)

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-GB") and the voice
    # name ("en-GB-Neural2-B")
    if model.find("gpt-4") >= 0:
        voice = texttospeech.VoiceSelectionParams(
            {"language_code": "en-GB", "name": "en-GB-Neural2-B"}
        )
    else:
        voice = texttospeech.VoiceSelectionParams(
            {"language_code": "en-US", "name": "en-US-Neural2-D"}
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
            raise TextToSpeechError(text)

    if stream:
        return response.audio_content

    # Save the binary audio content to a file
    output_file = "audio_output/"+str(uuid.uuid4())+".wav"
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
        logger.info(f'Audio content written to file "{output_file}"')

    return output_file


def simplify_urls(text):
    """
    Simplify URLs in the given text by removing the protocol and "www." and anything after the domain name.
    :param text:
    :return:
    """
    # Regular expression to match URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    # Find all URLs in the text
    urls = re.findall(url_pattern, text)

    # Function to extract and simplify the domain name from a URL
    def get_simplified_domain(url):
        domain = re.sub(r'(http[s]?://|www\.)', '', url)  # Remove the protocol and "www."
        domain = re.sub(r'(/.*)', '', domain)            # Remove anything after the domain
        return domain

    # Replace each URL with its simplified domain name
    for url in urls:
        simplified_domain = get_simplified_domain(url)
        text = text.replace(url, simplified_domain)

    return text


def find_longest_sentence(text):
    """
    Find the longest sentence in the given text.
    :param text:
    :return:
    """
    # Split the text into sentences using regex
    sentences = re.split(r' *[\.\?!][\'"\)\]]* *', text)

    # Find the longest sentence
    longest_sentence = max(sentences, key=len)

    return longest_sentence


def split_longest_sentence(text, max_length=200):
    """
    Split the longest sentence in the given text into smaller sentences.
    :param text:
    :param max_length:
    :return:
    """
    # Find the longest sentence
    longest_sentence = find_longest_sentence(text)

    # Split the longest sentence into chunks
    chunks = split_sentence(longest_sentence, max_length)

    # Replace the longest sentence in the text with the smaller sentences
    new_longest_sentence = '. '.join(chunks)
    modified_text = text.replace(longest_sentence, new_longest_sentence)

    return modified_text


def split_sentence(sentence, max_length=200):
    """
    Split the given sentence into smaller sentences.
    :param sentence:
    :param max_length:
    :return:
    """
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


def free_text_to_speech(text: str, model="gpt-4", stream=False):
    slow_flag = False if not model.find("gpt-4") >= 0 else True
    tts = gTTS(text, lang='en', slow=slow_flag)

    if stream:
        mp3_buffer = io.BytesIO()
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        mp3_segment = AudioSegment.from_file(mp3_buffer, format="mp3")
        wav_buffer = io.BytesIO()
        mp3_segment.export(wav_buffer, format="wav")
        wav_buffer.seek(0)
        audio_content = wav_buffer.read()
        return audio_content
    else:
        output_file = str(uuid.uuid4()) + ".wav"
        mp3_output = io.BytesIO()
        tts.write_to_fp(mp3_output)
        mp3_output.seek(0)
        mp3_segment = AudioSegment.from_file(mp3_output, format="mp3")
        mp3_segment.export(output_file, format="wav")
        logger.info(f'Audio content written to file "{output_file}" using free text-to-speech alternative')
        return output_file