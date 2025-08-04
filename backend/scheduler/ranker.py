# backend/scheduler/ranker.py
import json
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The Ollama API endpoint. Assumes Ollama is running on the host machine.
# 'host.docker.internal' is a special DNS name that resolves to the host's IP from within a Docker container.
# FIX: The URL was previously formatted as a Markdown link, which is invalid.
OLLAMA_API_URL = "http://host.docker.internal:11434/api/generate"

def rank_slots_with_llm(feasible_slots, reason_for_visit):
    """
    Ranks a list of feasible appointment slots using a local LLM.

    Args:
        feasible_slots (list): A list of dictionaries, each representing a slot.
        reason_for_visit (str): The user-provided reason for the visit.

    Returns:
        list: A sorted list of the top-ranked slots. Returns the original
              list if the LLM call fails.
    """
    if not feasible_slots:
        return []

    # Create a simplified list of slots for the prompt
    prompt_slots = [
        f"Slot {i+1}: Time {slot['start_time']}"
        for i, slot in enumerate(feasible_slots)
    ]
    
    prompt = f"""
You are an expert veterinary clinic scheduler. Your task is to select the three best appointment times from a list of available slots based on the patient's reason for visit.

**Reason for Visit:** "{reason_for_visit}"

**Available Slots:**
{json.dumps(prompt_slots, indent=2)}

**Instructions:**
1.  Analyze the "Reason for Visit". Consider urgency, potential need for a quiet environment, or if it's a routine check-up.
    - Urgent-sounding requests (e.g., "not eating", "limping", "sick") should be prioritized for earlier slots.
    - Routine visits (e.g., "annual checkup", "vaccinations") can be scheduled later.
    - Anxious pets (e.g., "anxious cat", "scared of other dogs") might benefit from the very first slot of the day or the first slot after lunch when the clinic is quieter.
2.  Based on your analysis, choose the top 3 most suitable slots from the list.
3.  Return your response as a JSON object containing a single key "top_3_indices" with a list of the integer indices (1-based from the list above) of your chosen slots, from best to worst.

**Example Response Format:**
{{
  "top_3_indices": [5, 2, 10]
}}

Now, provide the JSON for the given reason and slots.
"""

    payload = {
        "model": "qwen:7b",
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    logger.info(f"Sending request to Ollama at {OLLAMA_API_URL}...")
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60) # Increased timeout
        response.raise_for_status()

        response_text = response.json().get('response', '{}')
        logger.info(f"Ollama raw response: {response_text}")

        # The response from Ollama is a string containing JSON, so we parse it.
        ranked_data = json.loads(response_text)
        
        top_indices = ranked_data.get("top_3_indices")

        if not top_indices or not isinstance(top_indices, list):
            logger.warning("LLM did not return valid indices. Returning original slot order.")
            return feasible_slots

        # Convert 1-based indices from LLM to 0-based list indices
        ranked_slots = [feasible_slots[i-1] for i in top_indices if 0 < i <= len(feasible_slots)]
        return ranked_slots

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Ollama API: {e}")
        # Fallback: return the original list if the LLM is unavailable
        return feasible_slots
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error parsing LLM response: {e}")
        # Fallback: return the original list on malformed response
        return feasible_slots
