from google.cloud import texttospeech
from google.oauth2 import service_account
from keys import get_gcp_path

# Setup logging
import logger_config
logger = logger_config.get_logger()

# Load service account credentials
sa_creds = service_account.Credentials.from_service_account_file(get_gcp_path())

# Instantiate a Text-to-Speech client
client = texttospeech.TextToSpeechClient(credentials=sa_creds)


def text_to_speech(text: str) -> str:
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
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # Save the binary audio content to a file
    output_file = "output.wav"
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
        logger.info(f'Audio content written to file "{output_file}"')

    return output_file
