import json
from typing import List, Optional, Union

from vertexai.language_models import InputOutputTextPair, ChatMessage
from pydantic import BaseModel, root_validator, validator
from pylon.core.tools import log


class ChatCompletionRequestBody(BaseModel):
    context: str | None = None,
    examples: List[InputOutputTextPair] | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_k: int | None = None
    top_p: float | None = None
    message_history: List[ChatMessage] | None = None
    stop_sequences: List[str] | None = None

    @root_validator(pre=True)
    def prepare_data(cls, values: dict) -> dict:
        examples = []
        message_history = []
        if values.get('messages'):
            for idx, message in enumerate(values['messages']):
                if message['role'] == 'system' and not message.get('name'):
                    values['context'] = message['content']
                if message.get("name") == "example_user":
                    for j in range(idx + 1, len(values['messages'])):
                        if values['messages'][j].get("name") == "example_assistant":
                            example = {
                                "input_text": message["content"],
                                "output_text": values['messages'][j]["content"]
                            }
                            examples.append(example)
                            break
                if message['role'] == 'user' and idx != len(values['messages']) - 1:
                    message_history.append({
                        'author': 'user',
                        'content': message["content"]
                    })
                if message['role'] == 'assistant':
                    message_history.append({
                        'author': 'bot',
                        'content': message["content"]
                    })
        values['examples'] = list(map(lambda x: InputOutputTextPair(**x), examples))
        values['message_history'] = list(map(lambda x: ChatMessage(**x), message_history))
        if not values.get('max_output_tokens'):
            values['max_output_tokens'] = values.get('max_tokens')

        return values


class CompletionRequestBody(BaseModel):
    prompt: str
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_k: int | None = None
    top_p: float | None = None
    stop_sequences: List[str] | None = None

    @root_validator(pre=True)
    def prepare_data(cls, values: dict) -> dict:
        if not values.get('max_output_tokens'):
            values['max_output_tokens'] = values.get('max_tokens')
        return values
