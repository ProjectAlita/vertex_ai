from importlib import reload
from traceback import format_exc

from pylon.core.tools import web, log
import json

from tools import rpc_tools
from pydantic import ValidationError

from google.oauth2.service_account import Credentials
from google.cloud import aiplatform

from ..models.integration_pd import VertexAISettings
from ..utils import predict_chat, predict_text
from ...integrations.models.pd.integration import SecretField


class RPC:
    integration_name = 'vertex_ai'

    @web.rpc(f'{integration_name}__predict')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def predict(self, project_id: int, settings: dict, prompt_struct: dict):
        """ Predict function """
        try:
            if settings['model_name'].startswith('chat'):
                log.info('Using chat prediction for model: %s', settings['model_name'])
                result = predict_chat(project_id, settings, prompt_struct)
            else:
                log.info('Using completion(text) prediction for model: %s', settings['model_name'])
                result = predict_text(project_id, settings, prompt_struct)
        except Exception as e:
            log.error(format_exc())
            return {"ok": False, "error": f"{type(e)}: {str(e)}"}

        return {"ok": True, "response": result}

    @web.rpc(f'{integration_name}__parse_settings')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def parse_settings(self, settings):
        try:
            settings = VertexAISettings.parse_obj(settings)
        except ValidationError as e:
            return {"ok": False, "error": e}
        return {"ok": True, "item": settings}

    @web.rpc(f'{integration_name}_set_models', 'set_models')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def set_models(self, payload: dict):
        reload(aiplatform.initializer)
        try:
            service_account = SecretField.parse_obj(payload['settings'].get('api_token', {}))
            service_info = json.loads(service_account.unsecret(payload.get('project_id')))
            credentials = Credentials.from_service_account_info(service_info)
            aiplatform.init(project=self.project, location=self.zone, credentials=credentials)
            models = aiplatform.Model.list()
        except Exception as e:
            log.error(str(e))
            models = []
        if models:
            models = [{
                'id': m.resource_name,
                'name': m.name,
                'display_name': m.display_name,
                'description': m.description,
                'created_at': m.create_time,
                'updated_at': m.update_time,
                'version_id': m.version_id,
            } for m in models]
        return models
