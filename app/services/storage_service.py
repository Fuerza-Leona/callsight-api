# app/services/storage_service.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
import uuid
from supabase import Client


async def store_conversation_data(
    supabase: Client,
    audio_id: str,
    date_time: datetime,
    duration: int,
    company_id: str,
    analysis_result: Dict[str, Any],
    participant_list: List[str],
    embeddings_results: List[Dict],
) -> str:
    """
    Stores all conversation data in the database including:
    - Main conversation record
    - Summary data
    - Topics
    - Participants
    - Transcript messages

    Returns the conversation_id of the created conversation.
    """
    # Extract data from analysis_result
    transcript = analysis_result.get("phrases", [])
    summary = analysis_result.get("summary", {})
    topics = analysis_result.get("topics", [])

    # Extract problem and solution from summary
    problem = ""
    solution = ""
    try:
        problem = summary.get("Issue task", {}).get("issue", "")
        solution = summary.get("Resolution task", {}).get("resolution", "")
    except (TypeError, AttributeError) as e:
        print(f"Warning: Could not extract problem/solution: {str(e)}")

    # Calculate start and end times
    start_time = date_time
    end_time = start_time + timedelta(seconds=duration) if duration else start_time

    conversation_id = None

    # Database operations - use transactions if possible
    try:
        # Step 1: Insert conversation record
        query = (
            supabase.table("conversations")
            .insert(
                {
                    "audio_id": audio_id,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "company_id": company_id,
                }
            )
            .execute()
        )

        if not query.data or len(query.data) == 0:
            raise Exception("Failed to insert conversation record")

        conversation_id = query.data[0].get("conversation_id")
        if not conversation_id:
            raise Exception("No conversation_id returned from database")

        # Step 2: Insert summary
        summary_query = (
            supabase.table("summaries")
            .insert(
                {
                    "conversation_id": conversation_id,
                    "problem": problem,
                    "solution": solution,
                }
            )
            .execute()
        )

        if not summary_query.data:
            print("Warning: Summary insertion may have failed")

        # Step 3: Process topics
        await process_topics(supabase, topics, conversation_id)

        # Step 4: Process participants
        if participant_list:
            await process_participants(supabase, participant_list, conversation_id)

        # Step 5: Insert transcript messages
        await process_transcripts(supabase, transcript, conversation_id)

        # Step 6.1: Add the conversation_id to the embeddings
        rows = []
        for e in embeddings_results:
            e["conversation_id"] = conversation_id

        # Step 6.2 Insert the embeddings
        embeddings_query = (
            supabase.table("conversation_chunks").insert(embeddings_results).execute()
        )

        if not embeddings_query.data:
            print("Warning: Embeddings insertion may have failed")

        return conversation_id

    except Exception as e:
        print(f"ERROR: Database operation failed: {str(e)}")
        raise e


async def process_topics(
    supabase: Client, topics: List[str], conversation_id: str
) -> None:
    """Process and insert topics with proper error handling."""
    for topic in topics:
        try:
            topic_text = topic.lower()
            # Check if topic already exists
            existing_topic = (
                supabase.table("topics").select("*").eq("topic", topic_text).execute()
            )

            if existing_topic.data and len(existing_topic.data) > 0:
                topic_id = existing_topic.data[0].get("topic_id")
                if not topic_id:
                    print(
                        f"WARNING: Retrieved topic '{topic_text}' is missing topic_id"
                    )
                    continue
            else:
                # Create new topic if it doesn't exist
                topic_query = (
                    supabase.table("topics").insert({"topic": topic_text}).execute()
                )
                if not topic_query.data or len(topic_query.data) == 0:
                    print(f"WARNING: Failed to insert new topic '{topic_text}'")
                    continue

                topic_id = topic_query.data[0].get("topic_id")
                if not topic_id:
                    print(f"WARNING: New topic '{topic_text}' is missing topic_id")
                    continue

            # Create relationship in junction table
            junction_query = (
                supabase.table("topics_conversations")
                .insert({"topic_id": topic_id, "conversation_id": conversation_id})
                .execute()
            )

            if not junction_query.data or len(junction_query.data) == 0:
                print(
                    f"WARNING: Failed to create relationship for topic '{topic_text}'"
                )

        except Exception as e:
            print(f"ERROR: Error processing topic '{topic}': {str(e)}")
            # Continue processing other topics


async def process_participants(
    supabase: Client, participants: List[str], conversation_id: str
) -> None:
    """Process and insert participants with proper validation."""
    valid_participants = []

    for participant in participants:
        try:
            # Just validate UUID format without converting to UUID object and back
            uuid.UUID(participant)  # This will raise ValueError if invalid
            valid_participants.append(
                {
                    "conversation_id": conversation_id,
                    "user_id": participant,  # Use the string directly
                }
            )
        except ValueError:
            print(f"ERROR: Invalid UUID format for participant: {participant}")

    if valid_participants:
        try:
            participant_query = (
                supabase.table("participants").insert(valid_participants).execute()
            )
            if not participant_query.data or len(participant_query.data) == 0:
                print("WARNING: Participant insertion may have failed")
        except Exception as e:
            print(f"ERROR: Failed to insert participants: {str(e)}")


async def process_transcripts(
    supabase: Client, phrases: List[Dict[str, Any]], conversation_id: str
) -> None:
    """Process and insert transcript messages with proper error handling."""
    for i, phrase in enumerate(phrases):
        try:
            transcript_query = (
                supabase.table("messages")
                .insert(
                    {
                        "conversation_id": conversation_id,
                        "text": phrase["text"],
                        "speaker": phrase["speaker"],
                        "offsetmilliseconds": phrase["offsetMilliseconds"],
                        "role": phrase.get("role"),
                        "confidence": phrase["confidence"],
                        "positive": phrase["positive"],
                        "negative": phrase["negative"],
                        "neutral": phrase["neutral"],
                    }
                )
                .execute()
            )

            if not transcript_query.data or len(transcript_query.data) == 0:
                print(f"ERROR: Failed to insert transcript {i}")
        except Exception as e:
            print(f"ERROR: Error inserting transcript {i}: {str(e)}")
