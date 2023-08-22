import json
from enum import Enum
from json import JSONDecodeError
from typing import Union

from google.cloud import aiplatform
from google.oauth2.service_account import Credentials
from pydantic import BaseModel
from pylon.core.tools import log

from tools import session_project
from ...integrations.models.pd.integration import SecretField


class VertexAISettings(BaseModel):
    model_name: str = 'text-bison@001'
    temperature: float = 1.0
    max_decode_steps: int = 256
    top_p: float = 0.8
    top_k: int = 40
    tuned_model_name: str = ''


class IntegrationModel(BaseModel):
    service_account_info: Union[SecretField, str]
    project: str
    zone: str
    model_name: str = 'text-bison@001'
    temperature: float = 1.0
    max_decode_steps: int = 256
    top_p: float = 0.8
    top_k: int = 40
    tuned_model_name: str = ''

    def check_connection(self):
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
