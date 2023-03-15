from google.cloud import texttospeech
from google.oauth2 import service_account
from keys import get_gcp_path

sa_creds = service_account.Credentials.from_service_account_file(get_gcp_path())
# Instantiates a client
client = texttospeech.TextToSpeechClient(credentials=sa_creds)


def text_to_speech(text):

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-US") and the ssml
    # voice gender ("neutral")
    voice = texttospeech.VoiceSelectionParams(
        {"language_code": "en-GB", "name": "en-GB-Neural2-B"}
    )

    # Select the type of audio file you want returned
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

    # The response's audio_content is binary.
    with open("output.wav", "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)
        print('Audio content written to file "output.wav"')

    return "output.wav"

