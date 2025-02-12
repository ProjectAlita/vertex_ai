import json
import time
from functools import reduce
from importlib import reload
from collections import deque
from typing import Any

from .models.integration_pd import IntegrationModel, MessageModel
from .models.request_body import ChatCompletionRequestBody, CompletionRequestBody

import vertexai
from vertexai.language_models import ChatModel, InputOutputTextPair, TextGenerationModel, TextGenerationResponse, ChatMessage
from google.oauth2.service_account import Credentials
import tiktoken

from pylon.core.tools import log


def init_vertex(project_id: int, settings: IntegrationModel) -> None:
    reload(vertexai.preview.initializer)
    # service_account = SecretString(settings.service_account_info)
    # service_info = json.loads(service_account.unsecret(project_id))
    # credentials = Credentials.from_service_account_info(service_info)
    service_account_json = json.loads(settings.service_account_info.unsecret(project_id))
    credentials = Credentials.from_service_account_info(service_account_json)
    vertexai.init(
        project=settings.project,
        location=settings.zone,
        credentials=credentials
    )


def num_tokens_from_text(text: str) -> int:
    """Return the number of tokens used by text.
    """
    encoding = tiktoken.get_encoding("cl100k_base")  # Using cl100k_base encoding
    return len(encoding.encode(text))


def num_tokens_from_messages(message: Any) -> int:
    """Return the number of tokens used by messages.
    """
    encoding = tiktoken.get_encoding("cl100k_base")  # Using cl100k_base encoding
    tokens_per_message = 4
    num_tokens = 0
    if isinstance(message, str):
        num_tokens = len(encoding.encode(message))
    elif isinstance(message, InputOutputTextPair):
        num_tokens += len(encoding.encode(message.input_text))
        num_tokens += len(encoding.encode(message.output_text))
    elif isinstance(message, ChatMessage):
        num_tokens += len(encoding.encode(message.author))
        num_tokens += len(encoding.encode(message.content))
    elif isinstance(message, dict):
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
    # num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    num_tokens += tokens_per_message
    return num_tokens


def prepare_conversation(prompt_struct: dict, token_input_limit: int) -> dict:
    conversation = {
        'context': '',
        'examples': [],
        'chat_history': deque(),
        'prompt': ''
    }
    tokens_left = token_input_limit

    if prompt_struct.get('context'):
        context_tokens = num_tokens_from_messages(prompt_struct['context'])
        tokens_left -= context_tokens
        if tokens_left < 0:
            return conversation, tokens_left
        conversation['context'] = prompt_struct['context']

    if prompt_struct.get('prompt'):
        input_tokens = num_tokens_from_messages(prompt_struct['prompt'])
        tokens_left -= input_tokens
        if tokens_left < 0:
            return conversation, tokens_left
        conversation['prompt'] = prompt_struct['prompt']

    if prompt_struct.get('examples'):
        for example in prompt_struct['examples']:
            example_tokens = num_tokens_from_messages(example)
            tokens_left -= example_tokens
            if tokens_left < 0:
                return conversation, tokens_left
            conversation['examples'].append(example)

    if prompt_struct.get('chat_history'):
        for message in reversed(prompt_struct['chat_history']):
            if isinstance(message, dict):
                message = MessageModel(**message).dict()
            message_tokens = num_tokens_from_messages(message)
            tokens_left -= message_tokens
            if tokens_left < 0:
                break
            conversation['chat_history'].appendleft(message)

    if len(conversation['chat_history']) % 2:
        conversation['chat_history'].popleft()

    return conversation, tokens_left


def prepare_conversation_from_request(params, input_, input_token_limit):
    prompt_struct = {
        'context': params['context'],
        'examples': params['examples'],
        'chat_history': params['message_history'],
        'prompt': input_
    }
    conversation, tokens_left = prepare_conversation(prompt_struct, input_token_limit)
    params['context'] = conversation['context']
    params['examples'] = conversation['examples']
    params['message_history'] = conversation['chat_history']
    return params, prompt_struct['prompt'], tokens_left


def predict_chat(project_id: int, settings: dict, prompt_struct: dict, stream=False) -> str:
    settings = IntegrationModel.parse_obj(settings)

    init_vertex(project_id, settings)

    chat_model = ChatModel.from_pretrained(settings.model_name)
    params = {
        "temperature": settings.temperature,
        "top_k":settings.top_k,
        "top_p":settings.top_p,
    }
    if not stream:
        params["max_output_tokens"] = settings.max_decode_steps

    input_token_limit = settings.input_token_limit
    prompt_struct, tokens_left = prepare_conversation(prompt_struct, input_token_limit)

    if prompt_struct.get('chat_history'):
        chat_history = list(map(lambda x: ChatMessage(**x), prompt_struct['chat_history']))
    else:
        chat_history = None

    chat = chat_model.start_chat(
        context=prompt_struct['context'],
        examples=list(map(
            lambda i: InputOutputTextPair(
                input_text=i['input'],
                output_text=i['output']
            ),
            prompt_struct['examples']
        )),
        message_history=chat_history,
        **params
    )
    if stream:
        responses = chat.send_message_streaming(prompt_struct['prompt'])
        result = reduce(lambda x, y: x + y.text , responses, "")
        return result
    else:
        chat_response: TextGenerationResponse = chat.send_message(prompt_struct['prompt'])
        log.info('chat_response %s', chat_response)
        return chat_response.text


def predict_chat_from_request(project_id: int, settings: dict, request_data: dict) -> str:
    settings = IntegrationModel.parse_obj(settings)

    init_vertex(project_id, settings)

    model_name = request_data['deployment_id']
    stream = request_data['stream']
    if request_data.get('messages') and request_data['messages'][-1]['role'] == 'user':
        input_ = request_data['messages'][-1]['content']
    else:
        input_ = ''

    chat_model = ChatModel.from_pretrained(model_name)
    params = ChatCompletionRequestBody.validate(request_data).dict(exclude_unset=True)

    input_token_limit = settings.get_input_token_limit(model_name)
    params, input_, tokens_left = prepare_conversation_from_request(params, input_, input_token_limit)

    chat = chat_model.start_chat(**params)
    if stream:
        responses = chat.send_message_streaming(input_)
        result = (prepare_azure_response(
            model_name=model_name, text=resp.text, stream=True, chat=True) for resp in responses
            )
        return result
    else:
        chat_response: TextGenerationResponse = chat.send_message(input_)
        log.info('chat_response %s', chat_response)
        response_data = {
            'model_name': model_name,
            'text': chat_response.text,
            'input_token_usage': input_token_limit - tokens_left,
            'output_token_usage': num_tokens_from_text(chat_response.text)
        }
        return prepare_azure_response(**response_data, stream=False, chat=True)


def predict_from_request(project_id: int, settings: dict, request_data: dict) -> str:
    settings = IntegrationModel.parse_obj(settings)

    init_vertex(project_id, settings)

    model_name = request_data['deployment_id']
    stream = request_data['stream']
    params = CompletionRequestBody.validate(request_data).dict(exclude_unset=True)

    model = TextGenerationModel.from_pretrained(model_name)
    if settings.tuned_model_name:
        model = model.get_tuned_model(settings.tuned_model_name)

    if stream:
        responses = model.predict_streaming(**params)
        result = (prepare_azure_response(
            model_name=model_name, text=resp.text, stream=True, chat=True) for resp in responses
            )
        return result
    else:
        response: TextGenerationResponse = model.predict(**params)
        log.info('completion_response %s', response)
        response_data = {
            'model_name': model_name,
            'text': response.text,
            'input_token_usage': num_tokens_from_text(params.get('prompt', '')),
            'output_token_usage': num_tokens_from_text(response.text)
        }
        return prepare_azure_response(**response_data, stream=False, chat=False)


def _prerare_text_prompt(prompt_struct):
    example_template = '\ninput: {input}\noutput: {output}'

    for example in prompt_struct['examples']:
        prompt_struct['context'] += example_template.format(**example)
    if prompt_struct['prompt']:
        prompt_struct['context'] += example_template.format(input=prompt_struct['prompt'], output='')

    return prompt_struct['context']


def predict_text(project_id: int, settings: dict, prompt_struct: dict) -> str:
    settings = IntegrationModel.parse_obj(settings)

    init_vertex(project_id, settings)

    model = TextGenerationModel.from_pretrained(settings.model_name)
    if settings.tuned_model_name:
        model = model.get_tuned_model(settings.tuned_model_name)

    text_prompt = _prerare_text_prompt(prompt_struct)

    response = model.predict(
        text_prompt,
        temperature=settings.temperature,
        max_output_tokens=settings.max_decode_steps,
        top_k=settings.top_k,
        top_p=settings.top_p,
    )

    log.info('completion_response %s', response)
    return response.text


def prepare_result(text):
    structured_result = {'messages': []}
    structured_result['messages'].append({
        'type': 'text',
        'content': text
    })
    return structured_result


def prepare_azure_response(stream=False, chat=False, **kwargs):
    response =  {
        "object": "chat.completion" if chat else "completion",
        "created": int(time.time()),
        "model": kwargs.get('model_name'),
        "choices": [
            {
                "index": 0,
                "finish_reason": None if stream else 'stop',
            }
        ],
    }
    if stream:
        response['choices'][0]['delta'] = {
            "content": kwargs.get('text')
        }
        response['usage'] = None
    else:
        response['choices'][0]['message'] = {
            "role": "assistant",
            "content": kwargs.get('text')
        }
        response['usage'] = {
            "prompt_tokens": kwargs.get('input_token_usage'),
            "completion_tokens": kwargs.get('output_token_usage'),
            "total_tokens": kwargs.get('input_token_usage', 0) + kwargs.get('output_token_usage', 0)
        }
    return response
