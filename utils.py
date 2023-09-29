import json
from importlib import reload

from .models.integration_pd import IntegrationModel

import vertexai
from vertexai.language_models import ChatModel, InputOutputTextPair, TextGenerationModel, TextGenerationResponse
from google.oauth2.service_account import Credentials

from pylon.core.tools import log


def init_vertex(project_id: int, settings: IntegrationModel) -> None:
    reload(vertexai.preview.initializer)
    # service_account = SecretField.parse_obj(settings.service_account_info)
    # service_info = json.loads(service_account.unsecret(project_id))
    # credentials = Credentials.from_service_account_info(service_info)
    service_account_json = json.loads(settings.service_account_info.unsecret(project_id))
    credentials = Credentials.from_service_account_info(service_account_json)
    vertexai.init(
        project=settings.project,
        location=settings.zone,
        credentials=credentials
    )


def predict_chat(project_id: int, settings: dict, prompt_struct: dict) -> str:
    settings = IntegrationModel.parse_obj(settings)

    init_vertex(project_id, settings)

    chat_model = ChatModel.from_pretrained(settings.model_name)

    chat = chat_model.start_chat(
        context=prompt_struct['context'],
        examples=list(map(
            lambda i: InputOutputTextPair(
                input_text=i['input'],
                output_text=i['output']
            ),
            prompt_struct['examples']
        )),
        temperature=settings.temperature,
        max_output_tokens=settings.max_decode_steps,
        top_k=settings.top_k,
        top_p=settings.top_p,

    )
    # todo: push some context to chat history with ChatMessage class
    # chat.message_history
    chat_response: TextGenerationResponse = chat.send_message(prompt_struct['prompt'])

    log.info('chat_response %s', chat_response)

    return chat_response.text


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
