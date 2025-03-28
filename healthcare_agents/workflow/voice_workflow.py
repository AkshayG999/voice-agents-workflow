import json
from collections.abc import AsyncIterator
from typing import Callable, Awaitable
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from agents import Runner, TResponseInputItem
from agents.voice import VoiceWorkflowBase, VoiceWorkflowHelper
from healthcare_agents.healthcare.agents import main_agent

load_dotenv()

# Initialize OpenAI client for other services (like completion)
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)


class HealthcareVoiceWorkflow(VoiceWorkflowBase):
    def __init__(
        self,
        secret_word: str,
        on_start: Callable[[str], Awaitable[None]],
        on_response: Callable[[str], Awaitable[None]] = None,
    ):
        """
        Args:
            secret_word: The secret word to guess.
            on_start: A coroutine that is called when the workflow starts.
            on_response: A coroutine that is called with the agent's complete response text.
            speech_service: Speech-to-text service to use (Azure, AWS, or OpenAI)
        """
        self._input_history: list[TResponseInputItem] = []
        self._current_agent = main_agent
        self._secret_word = secret_word.lower()
        self._on_start = on_start
        self._on_response = on_response

    async def correct_transcription(self, transcription: str) -> dict:
        """
        Returns corrected transcription as JSON with validation
        Format:
        {
            "corrected_text": string,
            "confidence_score": float (0-1),
            "language_detected": string (ISO 639-1),
            "needs_human_review": boolean
        }
        """
        try:
            # Safely build the conversation history context, handling empty history
            history_context = ""
            if self._input_history:
                try:
                    history_context = "\n".join(
                        [
                            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                            for msg in self._input_history
                        ]
                    )
                except Exception as e:
                    print(f"Error building history context: {str(e)}")
                    history_context = "No valid conversation history available."

            correction_prompt = f"""Analyze and correct this transcription. Return JSON format:
    {{
        "corrected_text": "string (English translation/correction)",
        "confidence_score": float (0.0-1.0),
        "language_detected": "string (original language code)",
        "needs_human_review": boolean
    }}

    Rules:
    1. Maintain medical terminology accuracy
    2. Preserve numbers and measurements
    3. If non-English, translate to English
    4. Confidence score based on transcription quality

    Conversation History:
    {history_context}

    Raw Input:
    {transcription}

    Example Response:
    {{
        "corrected_text": "Patient reports 500mg ibuprofen taken twice daily",
        "confidence_score": 0.92,
        "language_detected": "es",
        "needs_human_review": false
    }}"""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": correction_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            # Parse JSON with validation
            correction_data = json.loads(response.choices[0].message.content)

            # Validate required fields
            if not all(
                key in correction_data
                for key in [
                    "corrected_text",
                    "confidence_score",
                    "language_detected",
                    "needs_human_review",
                ]
            ):
                raise ValueError("Missing required fields in correction response")

            # Set defaults for missing optional values
            return {
                "corrected_text": correction_data.get(
                    "corrected_text", transcription
                ).strip(),
                "confidence_score": min(
                    max(correction_data.get("confidence_score", 0.5), 0.0), 1.0
                ),
                "language_detected": correction_data.get("language_detected", "unk"),
                "needs_human_review": correction_data.get("needs_human_review", False),
                "original_text": transcription,  # Keep original for reference
            }

        except Exception as e:
            print(f"Correction error: {str(e)}")
            return {
                "corrected_text": transcription,
                "confidence_score": 0.4,
                "language_detected": "unk",
                "needs_human_review": True,
                "error": str(e),
            }

    async def run(self, transcription: str) -> AsyncIterator[str]:

        print(f"Raw transcription: '{transcription}'")

        if len(transcription.strip()) < 2:
            print(f"Skipping too short transcription: '{transcription}'")
            return

        try:
            correction = await self.correct_transcription(transcription)
            print(f"Correction data: {json.dumps(correction, indent=2)}")

            # Use corrected text or fallback
            processed_text = (
                correction["corrected_text"]
                if correction["confidence_score"] > 0.5
                else transcription
            )

            await self._on_start(processed_text)

            # Store corrected text in history - ensure required fields are present
            self._input_history.append(
                {
                    "role": "user",
                    "content": processed_text,
                }
            )

            # Rest of the original processing flow
            try:
                result = Runner.run_streamed(self._current_agent, self._input_history)
                full_response = []
                async for chunk in VoiceWorkflowHelper.stream_text_from(result):
                    full_response.append(chunk)
                    yield chunk

                complete_response = "".join(full_response)
                if self._on_response:
                    await self._on_response(complete_response)

                # Safely update input history
                try:
                    new_history = result.to_input_list()
                    if new_history and isinstance(new_history, list):
                        # Validate each item has required fields
                        valid_history = []
                        for item in new_history:
                            if (
                                isinstance(item, dict)
                                and "role" in item
                                and "content" in item
                            ):
                                valid_history.append(item)
                            else:
                                print(f"Skipping invalid history item: {item}")

                        if valid_history:
                            self._input_history = valid_history
                    else:
                        print("Invalid or empty input history returned from agent")
                        # Add agent response to existing history
                        self._input_history.append(
                            {"role": "assistant", "content": complete_response}
                        )
                except Exception as e:
                    print(f"Error processing input history: {str(e)}")
                    # Fallback to adding just the response
                    self._input_history.append(
                        {"role": "assistant", "content": complete_response}
                    )

                self._current_agent = result.last_agent

            except Exception as e:
                error_msg = f"I'm sorry, I encountered a technical issue. Please try again in a moment. Error: {str(e)}"
                print(f"Agent execution error: {str(e)}")
                yield error_msg
                if self._on_response:
                    await self._on_response(error_msg)
                # Add error response to history
                self._input_history.append({"role": "assistant", "content": error_msg})

        except Exception as e:
            print(f"Error in voice workflow execution: {str(e)}")
            error_response = "I'm sorry, I'm having trouble processing your request. Please try again."
            yield error_response
            if self._on_response:
                await self._on_response(error_response)
