import subprocess
import sys
import os
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
    """
    Exception raised when the text to speech conversion fails.
    """
    def __init__(self, sentence):
        """
        Initialise the exception.

        :param sentence: str, The sentence that failed to be converted to speech.
        :type sentence: str
        """
        self.sentence = sentence
        super().__init__(f"The following sentence was too long to turn into voice '{self.sentence}'.")


def text_to_speech(text: str, stream=False, model="gpt-4"):
    """
    Convert the given text to speech and save the result as an audio file.

    :param text: str, The text to be converted to speech.
    :type text: str
    :param stream: bool, Whether to return the audio content as a stream or save it to a file.
    :type stream: bool
    :param model: str, The model used to generate the text.
    :type model: str
    :return: The file path of the generated audio file or the audio content as a stream.
    :rtype: str or bytes
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

    audio_folder = "audio_output/"
    if getattr(sys, 'frozen', False):
        audio_folder = os.path.join(sys._MEIPASS, audio_folder)

    # Save the binary audio content to a file
    output_file = audio_folder+str(uuid.uuid4())+".wav"
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
        logger.info(f'Audio content written to file "{output_file}"')

    return output_file


def simplify_urls(text):
    """
    Simplify URLs in the given text by removing the protocol and "www." and anything after the domain name.
    :param text: The text to simplify URLs in.
    :type text: str
    :return: The modified text.
    :rtype: str
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
    :param text: The text to find the longest sentence in.
    :type text: str
    :return: The longest sentence.
    :rtype: str
    """
    # Split the text into sentences using regex
    sentences = re.split(r' *[\.\?!][\'"\)\]]* *', text)

    # Find the longest sentence
    longest_sentence = max(sentences, key=len)

    return longest_sentence


def split_longest_sentence(text):
    """
    Split the longest sentence in the given text into smaller sentences.
    :param text: The text to split the longest sentence in.
    :type text: str
    :return: The modified text.
    :rtype: str
    """
    # Find the longest sentence
    longest_sentence = find_longest_sentence(text)

    # Split the longest sentence into chunks
    chunks = split_sentence(longest_sentence)

    # Replace the longest sentence in the text with the smaller sentences
    new_longest_sentence = '. '.join(chunks)
    modified_text = text.replace(longest_sentence, new_longest_sentence)

    return modified_text


def capitalize_first_letter(sentence: str) -> str:
    """
    Capitalize the first letter of the given sentence.

    :param sentence: The sentence to capitalize the first letter.
    :type sentence: str
    :return: The sentence with the first letter capitalized.
    :rtype: str
    """
    if len(sentence) > 0:
        return sentence[0].upper() + sentence[1:]
    return sentence


def remove_trailing_comma(sentence: str) -> str:
    """
    Remove trailing comma from the given sentence.

    :param sentence: The sentence to remove the trailing comma.
    :type sentence: str
    :return: The sentence without the trailing comma.
    :rtype: str
    """
    return sentence.rstrip(',')


def find_best_split(sentence: str) -> int:
    """
    Find the best split index for a given sentence, considering commas, colons, and semicolons.

    :param sentence: The input sentence to find the best split index.
    :return: The best split index or None if there are no delimiters.
    :rtype: int or None
    """
    # Find the indices of all delimiters
    delimiter_indices = [m.start() for m in re.finditer(r'[:,;]', sentence)]

    if not delimiter_indices:
        return None

    # Calculate the lengths of the two halves for each delimiter
    half_lengths = [(abs(len(sentence[:i]) - len(sentence[i+1:])), i) for i in delimiter_indices]

    # Find the delimiter that results in the most evenly-sized halves
    best_split_index = min(half_lengths, key=lambda x: x[0])[1]

    return best_split_index


def split_sentence(sentence: str) -> list:
    """
    Split the input sentence into two parts at the best delimiter.

    :param sentence: The input sentence to split.
    :type sentence: str
    :return: A list of two sentences after splitting.
    :rtype: list
    """
    best_split_index = find_best_split(sentence)

    if best_split_index is None:
        return [sentence]

    first_half = sentence[:best_split_index].strip()
    second_half = sentence[best_split_index + 1:].strip()

    # Capitalize the first letter and remove trailing commas
    first_half = capitalize_first_letter(remove_trailing_comma(first_half))
    second_half = capitalize_first_letter(remove_trailing_comma(second_half))

    return [first_half, second_half]


def free_text_to_speech(text: str, model="gpt-4", stream=False):
    """
    Convert the given text to speech using the specified model.

    :param text: The text to convert to speech.
    :type text: str
    :param model: The model to use for text-to-speech.
    :type model: str
    :param stream: Whether to return the audio content as a stream.
    :type stream: bool
    :return: The path to the audio file or the audio content as a stream.
    :rtype: str or bytes
    """
    audio_folder = "audio_output/"
    if getattr(sys, 'frozen', False):
        audio_folder = os.path.join(sys._MEIPASS, audio_folder)
    slow_flag = True
    if model.find("gpt-4") >= 0:
        slow_flag = False
    if sys.platform == 'darwin':
        out = subprocess.run(['say', '-v', '?'], capture_output=True)
        vflag = []
        if out.stdout.decode("utf-8").find("Samantha") >= 0:
            vflag = ['-v', 'Samantha']
        if out.stdout.decode("utf-8").find("Tom") >= 0:
            vflag = ['-v', 'Tom']
        fixed_text = text.replace('"', r'\"')
        pitch = "44"
        if slow_flag:
            pitch = "40"
        text_cmd = f'[[pbas {pitch}]] "{fixed_text}"'

        output_file = audio_folder + str(uuid.uuid4()) + ".wav"
        subprocess.run(['say']+vflag+[text_cmd, "-o", output_file, '--data-format=LEI16@22050'])
        if not stream:
            return output_file
        with open(output_file, 'rb') as file:
            file.seek(0)
            byte_data = file.read()
        os.remove(output_file)
        return byte_data
    else:
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
            output_file = audio_folder + str(uuid.uuid4()) + ".wav"
            mp3_output = io.BytesIO()
            tts.write_to_fp(mp3_output)
            mp3_output.seek(0)
            mp3_segment = AudioSegment.from_file(mp3_output, format="mp3")
            mp3_segment.export(output_file, format="wav")
            logger.info(f'Audio content written to file "{output_file}" using free text-to-speech alternative')
            return output_file
