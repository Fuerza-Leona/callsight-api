#
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.
#

from datetime import datetime
from functools import reduce
from http import HTTPStatus
from itertools import chain
from json import dumps, loads
from os import linesep, environ
from pathlib import Path
from time import sleep
from typing import Dict, List, Tuple
import uuid
from . import helper
from . import rest_helper
from dotenv import load_dotenv
import os

# This should not change unless you switch to a new version of the Speech REST API.
SPEECH_TRANSCRIPTION_PATH = "/speechtotext/v3.2/transcriptions"

# These should not change unless you switch to a new version of the Cognitive Language REST API.
SENTIMENT_ANALYSIS_PATH = "/language/:analyze-text"
SENTIMENT_ANALYSIS_QUERY = "?api-version=2024-11-01"

# How long to wait while polling batch transcription status.
WAIT_SECONDS = 10

class TranscriptionPhrase(object) :
    def __init__(self, id : int, text : str, itn : str, lexical : str, speaker_number : int, offset : str, offset_in_ticks : float) :
        self.id = id
        self.text = text
        self.itn = itn
        self.lexical = lexical
        self.speaker_number = speaker_number
        self.offset = offset
        self.offset_in_ticks = offset_in_ticks

class SentimentAnalysisResult(object) :
    def __init__(self, speaker_number : int, offset_in_ticks : float, document : Dict) :
        self.speaker_number = speaker_number
        self.offset_in_ticks = offset_in_ticks
        self.document = document

def create_transcription(user_config : helper.Read_Only_Dict) -> str :
    uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}"

    # Create Transcription API JSON request sample and schema:
    # https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/CreateTranscription
    # Notes:
    # - locale and displayName are required.
    # - diarizationEnabled should only be used with mono audio input.
    content = {
        "contentUrls" : [user_config["input_audio_url"]],
        "properties" : {
            "diarizationEnabled" : not user_config["use_stereo_audio"],
            "timeToLive" : "PT30M"
        },
        "locale" : user_config["locale"],
        "displayName" : f"call_analysis_{datetime.now()}",
    }

    response = rest_helper.send_post(uri=uri, content=content, key=user_config["subscription_key"], expected_status_codes=[HTTPStatus.CREATED])
    
    # Create Transcription API JSON response sample and schema:
    # https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/CreateTranscription
    transcription_uri = response["json"]["self"]
    # The transcription ID is at the end of the transcription URI.
    transcription_id = transcription_uri.split("/")[-1]
    # Verify the transcription ID is a valid GUID.
    try :
        uuid.UUID(transcription_id)
        return transcription_id
    except ValueError:
        raise Exception(f"Unable to parse response from Create Transcription API:{linesep}{response['text']}")

def get_transcription_status(transcription_id : str, user_config : helper.Read_Only_Dict) -> bool :
    uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}/{transcription_id}"
    response = rest_helper.send_get(uri=uri, key=user_config["subscription_key"], expected_status_codes=[HTTPStatus.OK])
    if "failed" == response["json"]["status"].lower() :
        raise Exception(f"Unable to transcribe audio input. Response:{linesep}{response['text']}")
    else :
        return "succeeded" == response["json"]["status"].lower()

def wait_for_transcription(transcription_id : str, user_config : helper.Read_Only_Dict) -> None :
    done = False
    while not done :
        print(f"Waiting {WAIT_SECONDS} seconds for transcription to complete.")
        sleep(WAIT_SECONDS)
        done = get_transcription_status(transcription_id, user_config=user_config)

def get_transcription_files(transcription_id : str, user_config : helper.Read_Only_Dict) -> Dict :
    uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}/{transcription_id}/files"
    response = rest_helper.send_get(uri=uri, key=user_config["subscription_key"], expected_status_codes=[HTTPStatus.OK])
    return response["json"]

def get_transcription_uri(transcription_files : Dict, user_config : helper.Read_Only_Dict) -> str :
    # Get Transcription Files JSON response sample and schema:
    # https://westus.dev.cognitive.microsoft.com/docs/services/speech-to-text-api-v3-0/operations/GetTranscriptionFiles
    value = next(filter(lambda value: "transcription" == value["kind"].lower(), transcription_files["values"]), None)    
    if value is None :
        raise Exception (f"Unable to parse response from Get Transcription Files API:{linesep}{transcription_files['text']}")
    return value["links"]["contentUrl"]

def get_transcription(transcription_uri : str) -> Dict :
    response = rest_helper.send_get(uri=transcription_uri, key="", expected_status_codes=[HTTPStatus.OK])
    return response["json"]

def get_transcription_phrases(transcription : Dict, user_config : helper.Read_Only_Dict) -> List[TranscriptionPhrase] :
    def helper(id_and_phrase : Tuple[int, Dict]) -> TranscriptionPhrase :
        (id, phrase) = id_and_phrase
        best = phrase["nBest"][0]
        speaker_number : int
        # If the user specified stereo audio, and therefore we turned off diarization,
        # only the channel property is present.
        # Note: Channels are numbered from 0. Speakers are numbered from 1.
        if "speaker" in phrase :
            speaker_number = phrase["speaker"] - 1
        elif "channel" in phrase :
            speaker_number = phrase["channel"]
        else :
            raise Exception(f"nBest item contains neither channel nor speaker attribute.{linesep}{best}")
        return TranscriptionPhrase(id, best["display"], best["itn"], best["lexical"], speaker_number, phrase["offset"], phrase["offsetInTicks"])
    # For stereo audio, the phrases are sorted by channel number, so resort them by offset.
    return list(map(helper, enumerate(transcription["recognizedPhrases"])))

def delete_transcription(transcription_id : str, user_config : helper.Read_Only_Dict) -> None :
    uri = f"https://{user_config['speech_endpoint']}{SPEECH_TRANSCRIPTION_PATH}/{transcription_id}"
    rest_helper.send_delete(uri=uri, key=user_config["subscription_key"], expected_status_codes=[HTTPStatus.NO_CONTENT])

def get_sentiments_helper(documents : List[Dict], user_config : helper.Read_Only_Dict) -> Dict :
    uri = f"https://{user_config['language_endpoint']}{SENTIMENT_ANALYSIS_PATH}{SENTIMENT_ANALYSIS_QUERY}"
    content = {
        "kind" : "SentimentAnalysis",
        "analysisInput" : { "documents" : documents },
    }
    response = rest_helper.send_post(uri = uri, content=content, key=user_config["subscription_key"], expected_status_codes=[HTTPStatus.OK])
    return response["json"]["results"]["documents"]

def get_sentiment_analysis(phrases : List[TranscriptionPhrase], user_config : helper.Read_Only_Dict) -> List[SentimentAnalysisResult] :
    retval : List[SentimentAnalysisResult] = []
    # Create a map of phrase ID to phrase data so we can retrieve it later.
    phrase_data : Dict = {}
    # Convert each transcription phrase to a "document" as expected by the sentiment analysis REST API.
    # Include a counter to use as a document ID.
    documents : List[Dict] = []
    for phrase in phrases :
        phrase_data[phrase.id] = (phrase.speaker_number, phrase.offset_in_ticks)
        documents.append({
            "id" : phrase.id,
            "language" : user_config["language"],
            "text" : phrase.text,
        })
    # We can only analyze sentiment for 10 documents per request.
    # Get the sentiments for each chunk of documents.
    result_chunks = list(map(lambda xs : get_sentiments_helper(xs, user_config), helper.chunk (documents, 10)))
    for result_chunk in result_chunks :
        for document in result_chunk :
            retval.append(SentimentAnalysisResult(phrase_data[int(document["id"])][0], phrase_data[int(document["id"])][1], document))
    return retval

def get_sentiments_for_simple_output(sentiment_analysis_results : List[SentimentAnalysisResult]) -> List[str] :
    sorted_by_offset = sorted(sentiment_analysis_results, key=lambda x : x.offset_in_ticks)
    return list(map(lambda result : result.document["sentiment"], sorted_by_offset))

def get_sentiment_confidence_scores(sentiment_analysis_results : List[SentimentAnalysisResult]) -> List[Dict] :
    sorted_by_offset = sorted(sentiment_analysis_results, key=lambda x : x.offset_in_ticks)
    return list(map(lambda result : result.document["confidenceScores"], sorted_by_offset))

def merge_sentiment_confidence_scores_into_transcription(transcription : Dict, sentiment_confidence_scores : List[Dict]) -> Dict :
    for id, phrase in enumerate(transcription["recognizedPhrases"]) :
        for best_item in phrase["nBest"] :
            best_item["sentiment"] = sentiment_confidence_scores[id]
    return transcription

def get_simple_output(phrases : List[TranscriptionPhrase], sentiments : List[str]) -> str :
    result = ""
    for index, phrase in enumerate(phrases) :
        result += f"Phrase: {phrase.text}{linesep}"
        result += f"Speaker: {phrase.speaker_number}{linesep}"
        if index < len(sentiments) :
            result += f"Sentiment: {sentiments[index]}{linesep}"
        result += linesep
    return result

def print_simple_output(phrases : List[TranscriptionPhrase], sentiment_analysis_results : List[SentimentAnalysisResult]) -> None :
    sentiments = get_sentiments_for_simple_output(sentiment_analysis_results)
    print(get_simple_output(phrases, sentiments))

def print_full_output(output_file_path : str, transcription : Dict, sentiment_confidence_scores : List[Dict]) -> None :
    result = {
        "transcription" : merge_sentiment_confidence_scores_into_transcription(transcription, sentiment_confidence_scores)
    }
    with open(output_file_path, mode = "w", newline = "") as f :
        f.write(dumps(result, indent=2))
    return result

def run(params={}) -> Dict:
    # Try to load from .env file first for backward compatibility
    load_dotenv(override=True)
    
    # Default values
    defaults = {
        "input_audio_url": None,
        "language": "en",
        "locale": "en-US",
        "use_stereo_audio": False,
        "output_file": False,
        "testing": False
    }
    
    ai_key = environ.get("AZURE_AI_KEY")
    if not ai_key:
        raise Exception("Missing Azure AI key. Please provide your Azure AI key in the AZURE_AI_KEY environment variable.")
    
    speech_endpoint = environ.get("AZURE_AI_SPEECH_ENDPOINT")
    if not speech_endpoint:
        raise Exception("Missing Azure Speech endpoint. Please provide your Azure Speech endpoint in the AZURE_AI_SPEECH_ENDPOINT environment variable.")
    else:
        speech_endpoint = speech_endpoint.replace("https://", "")
    
    language_endpoint = environ.get("AZURE_AI_LANGUAGE_ENDPOINT")
    if not language_endpoint:
        raise Exception("Missing Azure Language endpoint. Please provide your Azure Language endpoint in the AZURE_AI_LANGUAGE_ENDPOINT environment variable.")
    else:
        language_endpoint = language_endpoint.replace("https://", "")
    
    env_vars = {
        "subscription_key": ai_key,
        "speech_endpoint": speech_endpoint,
        "language_endpoint": language_endpoint,
        "language": environ.get("LANGUAGE", defaults["language"]),
        "locale": environ.get("LOCALE", defaults["locale"]),
        "use_stereo_audio": environ.get("USE_STEREO_AUDIO", defaults["use_stereo_audio"]),
        "output_file": environ.get("OUTPUT_FILE", defaults["output_file"]),
        "testing": defaults["testing"]
    }
    
    # Update with params (params take highest precedence)
    config = {**env_vars, **params}
    
    # Convert to Read_Only_Dict for compatibility with existing code
    user_config = helper.Read_Only_Dict(config)

    transcription : Dict
    transcription_id : str

    if user_config["testing"] and os.path.exists("transcription.json"):
        print("Loading transcription from existing file...")
        with open("transcription.json", "r") as file:
            transcription = loads(file.read())
    elif user_config["input_audio_url"] is not None:
        # How to use batch transcription:
        # https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/cognitive-services/Speech-Service/batch-transcription.md
        transcription_id = create_transcription(user_config)
        wait_for_transcription(transcription_id, user_config)
        print(f"Transcription ID: {transcription_id}")
        transcription_files = get_transcription_files(transcription_id, user_config)
        transcription_uri = get_transcription_uri(transcription_files, user_config)
        print(f"Transcription URI: {transcription_uri}")
        transcription = get_transcription(transcription_uri)
        if user_config["testing"]:
            with open("transcription.json", "w") as file:
                file.write(dumps(transcription, indent=2))
    else:
        transcription = None
        
    if transcription:
        # For stereo audio, the phrases are sorted by channel number, so resort them by offset.
        transcription["recognizedPhrases"] = sorted(transcription["recognizedPhrases"], key=lambda phrase : phrase["offsetInTicks"])
        phrases = get_transcription_phrases(transcription, user_config)
        sentiment_analysis_results = get_sentiment_analysis(phrases, user_config)
        sentiment_confidence_scores = get_sentiment_confidence_scores(sentiment_analysis_results)
        
        # Prepare result to return
        result = {
            "transcription": merge_sentiment_confidence_scores_into_transcription(transcription.copy(), sentiment_confidence_scores)
        }
        
        # Save full output to file if requested
        if user_config["output_file"]:
            # Create directory if it doesn't exist
            output_path = Path("output.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, mode="w", newline="") as f:
                f.write(dumps(result, indent=2))
        
        return result
    else:
        raise Exception(f"Missing input audio URL.")

if "__main__" == __name__ :
    run(params={
        "input_audio_url": "https://callsightstorage.blob.core.windows.net/audio-files/Call6_mono_16k_az_apply_loan.wav",
        "testing": True,
    })