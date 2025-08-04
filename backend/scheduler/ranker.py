# backend/scheduler/ranker.py
import json
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The Ollama API endpoint. Assumes Ollama is running on the host machine.
# 'host.docker.internal' resolves to the host's IP from within a Docker container.
OLLAMA_API_URL = "http://host.docker.internal:11434/api/generate"


def rank_slots_with_llm(
    feasible_slots,
    reason_for_visit,
    vet_specialties=None,
    room_features=None,
    patient_history=None,
):
    """Rank feasible appointment slots using a local LLM.

    Args:
        feasible_slots (list): List of dictionaries representing slots.
        reason_for_visit (str): Reason provided by the client.
        vet_specialties (dict, optional): Mapping of ``vet_id`` to specialty.
        room_features (dict, optional): Mapping of ``room_id`` to features.
        patient_history (dict, optional): Relevant medical history for the pet.

    Returns:
        list: Ranked list of slots. Falls back to the original list if ranking
              fails.
    """
    if not feasible_slots:
        return []

    context = {
        "reason_for_visit": reason_for_visit,
        "patient_history": patient_history or {},
        "vet_specialties": vet_specialties or {},
        "room_features": room_features or {},
        "available_slots": [
            {
                "slot_index": i + 1,
                "vet_id": slot["vet_id"],
                "vet_name": slot["vet_name"],
                "room_id": slot["room_id"],
                "room_name": slot["room_name"],
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
            }
            for i, slot in enumerate(feasible_slots)
        ],
    }

    prompt = (
        "You are an expert veterinary clinic scheduler. Use the provided context "
        "to select the three best appointment times.\n\nContext:\n"
        f"{json.dumps(context, indent=2)}\n\n"
        "Return a JSON object with a single key 'top_3_indices' containing the "
        "list of slot_index values from best to worst."
    )

    payload = {
        "model": "qwen:7b",
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }

    logger.info(f"Sending request to Ollama at {OLLAMA_API_URL}...")
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        response.raise_for_status()

        response_text = response.json().get("response", "{}")
        logger.info(f"Ollama raw response: {response_text}")

        ranked_data = json.loads(response_text)
        top_indices = ranked_data.get("top_3_indices")

        if not top_indices or not isinstance(top_indices, list):
            logger.warning("LLM did not return valid indices. Returning original slot order.")
            return feasible_slots

        ranked_slots = [
            feasible_slots[i - 1]
            for i in top_indices
            if 0 < i <= len(feasible_slots)
        ]
        return ranked_slots

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Ollama API: {e}")
        return feasible_slots
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error parsing LLM response: {e}")
        return feasible_slots

