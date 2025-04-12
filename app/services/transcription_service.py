from app.core.config import settings
from app.services.analysis_service import analyze_sentiment
import assemblyai as aai
from openai import OpenAI


def get_transcription(file_url: str):
    # Replace with your API key
    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

    config = aai.TranscriptionConfig(
        speaker_labels=True,
        language_code="es",
    )

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(file_url, config=config)

    # Use LLM to classify speakers
    speaker_roles = classify_speakers_with_gpt(transcript.utterances)

    output = {"confidence": transcript.confidence, "phrases": []}

    for utterance in transcript.utterances:
        score = analyze_sentiment(utterance.text)
        speaker_number = ord(utterance.speaker) - ord("A") + 1
        output["phrases"].append(
            {
                "text": utterance.text,
                "speaker": speaker_number,
                "role": speaker_roles.get(f"Speaker {utterance.speaker}", None),
                "confidence": utterance.confidence,
                "offsetMilliseconds": utterance.start,
                "positive": score["positive"],
                "negative": score["negative"],
                "neutral": score["neutral"],
            }
        )
    return output


def classify_speakers_with_gpt(utterances):
    # Get the first few utterances to analyze patterns
    sample_conversation = []
    for i, utterance in enumerate(utterances):
        sample_conversation.append(f"Speaker {utterance.speaker}: {utterance.text}")

    conversation_text = "\n".join(sample_conversation)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert in analyzing call center conversations. Identify which speaker is the agent and which is the client.",
            },
            {
                "role": "user",
                "content": f"Below is the beginning of a call center conversation in Spanish. Identify which speaker is the agent and which is the client. Return your answer as a simple JSON with speaker letters as keys and 'agent' or 'client' as values.\n\n{conversation_text}",
            },
        ],
        response_format={"type": "json_object"},
    )

    try:
        roles = eval(response.choices[0].message.content)
        return roles
    except Exception as e:
        print(f"Error parsing speaker roles: {e}")
        return {}
