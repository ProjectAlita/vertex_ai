import json
from typing import List, Optional, Union

from pydantic.v1 import BaseModel, root_validator, validator
from pylon.core.tools import log

from tools import session_project, rpc_tools, VaultClient, worker_client, this, SecretString


def get_token_limits():
    vault_client = VaultClient()
    secrets = vault_client.get_all_secrets()
    return json.loads(secrets.get('vertex_ai_token_limits', ''))


class TokenLimitModel(BaseModel):
    input: int
    output: int


class CapabilitiesModel(BaseModel):
    completion: bool = True
    chat_completion: bool = True
    embeddings: bool = True


class AIModel(BaseModel):
    id: str
    name: str
    capabilities: CapabilitiesModel = CapabilitiesModel()
    token_limit: Optional[TokenLimitModel]

    @validator('token_limit', always=True, check_fields=False)
    def token_limit_validator(cls, value, values):
        if value:
            return value
        token_limits = get_token_limits()
        return token_limits.get(values.get('id').split('@')[0], TokenLimitModel(input=8192, output=1024))


class IntegrationModel(BaseModel):
    service_account_info: Union[SecretString, str]
    project: str
    zone: str
    models: List[AIModel] = []
    model_name: str = 'text-bison@001'
    temperature: float = 1.0
    max_decode_steps: int = 256
    top_p: float = 0.8
    top_k: int = 40
    tuned_model_name: str = ''

    @root_validator(pre=True)
    def prepare_model_list(cls, values):
        models = values.get('models')
        if models and isinstance(models[0], str):
            values['models'] = [AIModel(id=model, name=model).dict(by_alias=True) for model in models]
        return values

    @property
    def input_token_limit(self):
        return next((model.token_limit.input for model in self.models if model.id == self.model_name), 1024)

    def get_input_token_limit(self, model_name):
        return next((model.token_limit.input for model in self.models if model.id == model_name), 1024)

    def check_connection(self, project_id=None):
        if not project_id:
            project_id = session_project.get()
        #
        settings = self.dict()
        settings["service_account_info"] = self.service_account_info.unsecret(project_id)
        #
        return worker_client.ai_check_settings(
            integration_name=this.module_name,
            settings=settings,
        )

    def refresh_models(self, project_id):
        integration_name = 'vertex_ai'
        payload = {
            'name': integration_name,
            'settings': self.dict(),
            'project_id': project_id
        }
        return getattr(rpc_tools.RpcMixin().rpc.call, f'{integration_name}_set_models')(payload)


class VertexAISettings(BaseModel):
    model_name: str = 'text-bison@001'
    temperature: float = 1.0
    max_decode_steps: int = 256
    top_p: float = 0.8
    top_k: int = 40
    tuned_model_name: str = ''
    stream: bool = False


class MessageModel(BaseModel):
    author: str
    content: str

    class Config:
        fields = {
            'author': 'role'
        }

    @validator('author')
    def token_limit_validator(cls, value, values):
        if value == 'ai':
            return 'bot'
        return value
