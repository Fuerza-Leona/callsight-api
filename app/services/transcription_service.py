from app.core.config import settings
from app.services.analysis_service import analyze_sentiment
import assemblyai as aai
from openai import OpenAI
import tiktoken
import os

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 1000))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 1000))


def convert_to_chunks(transcript) -> list[str]:
    """Turn utterances into labeled lines for chunks"""
    lines = [f"Speaker {u.speaker}: {u.text}" for u in transcript.utterances]
    joined = "\n".join(lines)
    return split_strings_from_transcript(joined, MAX_TOKENS, GPT_MODEL)


def tokenize(text: str, model: str = GPT_MODEL) -> int:
    """Return the number of tokens in a string."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def halved_by_delimiter(text: str, delimiter: str = "\n") -> list[str]:
    """Split a text in two, on a delimiter, trying to balance tokens on each side."""
    parts = text.split(delimiter)
    if len(parts) == 1:
        return [text, ""]  # no delimiter found
    else:
        total_tokens = tokenize(text)
        halfway = total_tokens // 2
        best_idx = None
        best_diff = halfway
        for i in range(1, len(parts)):
            left = delimiter.join(parts[:i])
            left_tokens = tokenize(left)
            diff = abs(halfway - left_tokens)
            if diff < best_diff:
                best_diff = diff
                best_idx = i

        left = delimiter.join(parts[:best_idx])
        right = delimiter.join(parts[best_idx:])
        return [left, right]


def truncated_string(
    string: str,
    model: str,
    max_tokens: int,
    print_warning: bool = True,
) -> str:
    """Truncate a string to a maximum number of tokens."""
    encoding = tiktoken.encoding_for_model(model)
    encoded_string = encoding.encode(string)
    truncated_string = encoding.decode(encoded_string[:max_tokens])
    if print_warning and len(encoded_string) > max_tokens:
        print(
            f"Warning: Truncated string from {len(encoded_string)} tokens to {max_tokens} tokens."
        )
    return truncated_string


def split_strings_from_transcript(
    text: str,
    max_tokens: int = MAX_TOKENS,
    model: str = GPT_MODEL,
    max_recursion: int = 5,
) -> list[str]:
    """
    Recursively split a block of text into smaller chunks, each under `max_tokens`.

    The function tries to preserve semantic structure by first splitting on paragraph breaks,
    then line breaks, then sentence boundaries, and finally spaces—only breaking inside
    utterances when absolutely necessary.

    Returns a list of strings, each safe to embed or send to a model constrained by `max_tokens`.
    """

    # if length is fine, return text
    if tokenize(text, model) <= max_tokens:
        return [text]
    # if recursion hasn't found a split after X iterations, just truncate
    elif max_recursion == 0:
        return [truncated_string(text, model=model, max_tokens=max_tokens)]
    # otherwise, split in half and recurse
    else:
        for delimiter in ["\n\n", "\n", ". "]:
            left, right = halved_by_delimiter(text, delimiter=delimiter)
            if left.strip() and right.strip():
                # recurse on each half
                results = []
                for half in [left, right]:
                    half_strings = split_strings_from_transcript(
                        half,
                        max_tokens=max_tokens,
                        model=model,
                        max_recursion=max_recursion - 1,
                    )
                    results.extend(half_strings)
                return results
    # otherwise no split was found, so just truncate (should be very rare)
    # fallback
    return [truncated_string(text, model=model, max_tokens=max_tokens)]


def get_transcription(file_url: str):
    # Replace with your API key
    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    config = aai.TranscriptionConfig(
        speaker_labels=True,
        language_code="es",
    )

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(file_url, config=config)

    # For the embeddings, convert the transcript into separate chunks
    chunks = convert_to_chunks(transcript)
    """ for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---\n{chunk}") """

    embeddings = []
    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch_end = batch_start + BATCH_SIZE
        batch = chunks[batch_start:batch_end]
        """ print(f"Batch {batch_start} to {batch_end-1}") """
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        for i, e in enumerate(response.data):
            assert i == e.index
            global_index = batch_start + i
            embeddings.append(
                {
                    "chunk_index": global_index,
                    "content": batch[i],
                    "vector": e.embedding,
                }
            )
        """ for i, be in enumerate(response.data):
            assert i == be.index  # double check embeddings are in same order as input
        batch_embeddings = [e.embedding for e in response.data]
        embeddings.extend(batch_embeddings) """

    """ df = pd.DataFrame({"text": chunks, "embedding": embeddings}) """
    # return embeddings works already here
    """ for embedding in embeddings:
        print(embedding) """

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
    return output, embeddings


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
