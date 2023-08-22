from pylon.core.tools import log  # pylint: disable=E0611,E0401
from pylon.core.tools import web
import json

from tools import rpc_tools
from ..models.integration_pd import IntegrationModel, VertexAISettings
from pydantic import ValidationError
import vertexai
from google.oauth2.service_account import Credentials
from vertexai.preview.language_models import TextGenerationModel

from ...integrations.models.pd.integration import SecretField


class RPC:
    integration_name = 'vertex_ai'

    @web.rpc(f'{integration_name}__predict')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def predict(self, project_id, settings, text_prompt):
        """ Predict function """
        try:
            settings = IntegrationModel.parse_obj(settings)
        except ValidationError as e:
            return {"ok": False, "error": e}

        try:
            service_account = SecretField.parse_obj(settings.service_account_info)
            service_info = json.loads(service_account.unsecret(project_id))
            credentials = Credentials.from_service_account_info(service_info)
            vertexai.init(
                project=settings.project,
                location=settings.zone,
                credentials=credentials
            )
            model = TextGenerationModel.from_pretrained(settings.model_name)
            if settings.tuned_model_name:
                model = model.get_tuned_model(settings.tuned_model_name)

            response = model.predict(
                text_prompt,
                temperature=settings.temperature,
                max_output_tokens=settings.max_decode_steps,
                top_k=settings.top_k,
                top_p=settings.top_p,
            )
            result = response.text
        except Exception as e:
            log.error(str(e))
            return {"ok": False, "error": "Error in connection"}
    
        return {"ok": True, "response": result}

    
    @web.rpc(f'{integration_name}__parse_settings')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def parse_settings(self, settings):
        try:
            settings = VertexAISettings.parse_obj(settings)
        except ValidationError as e:
            return {"ok": False, "error": e}
        return {"ok": True, "item": settings}