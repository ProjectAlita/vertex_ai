import json
from json import JSONDecodeError
from typing import List, Optional, Union

from google.oauth2.service_account import Credentials
from pydantic import BaseModel, root_validator, validator
from pylon.core.tools import log

from tools import session_project, rpc_tools, VaultClient
from ...integrations.models.pd.integration import SecretField


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
    service_account_info: Union[SecretField, str]
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

    def check_connection(self):
        from google.cloud import aiplatform
        try:
            service_info = json.loads(
                self.service_account_info.unsecret(session_project.get()))
            credentials = Credentials.from_service_account_info(service_info)
            aiplatform.init(project=self.project, location=self.zone, credentials=credentials)
            aiplatform.Model.list()
        except JSONDecodeError:
            return "Failed to decode service account info"
        except Exception as exc:
            log.error(exc)
            return str(exc)
        return True

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
