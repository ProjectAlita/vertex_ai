#!/usr/bin/python3
# coding=utf-8

#   Copyright 2021 getcarrier.io
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

""" Module """
import json
from functools import partial

from pylon.core.tools import log  # pylint: disable=E0611,E0401
from pylon.core.tools import module  # pylint: disable=E0611,E0401

from tools import VaultClient, worker_client  # pylint: disable=E0611,E0401

from .models.integration_pd import IntegrationModel


TOKEN_LIMITS = {
    'text-bison': {
        'input': 8192,
        'output': 1024,
    },
    'chat-bison': {
        'input': 8192,
        'output': 1024,
    },
    'code-bison': {
        'input': 6144,
        'output': 1024,
    },
    'codechat-bison': {
        'input': 6144,
        'output': 1024,
    },
    'code-gecko': {
        'input': 2048,
        'output': 64,
    },
    'text-bison-32k': {
        'input': 32000,
        'output': 8192,
    },
    'chat-bison-32k': {
        'input': 32000,
        'output': 8192,
    },
    'code-bison-32k': {
        'input': 32000,
        'output': 8192,
    },
    'codechat-bison-32k': {
        'input': 32000,
        'output': 8192,
    },
}


class Module(module.ModuleModel):
    """ Task module """

    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

    def init(self):
        """ Init module """
        log.info("Initializing module Vertex AI Integration")
        SECTION_NAME = 'ai'
        #
        self.descriptor.init_all()
        #
        # Register template slot callback
        self.context.rpc_manager.call.integrations_register_section(
            name=SECTION_NAME,
            integration_description='Manage ai integrations',
        )
        self.context.rpc_manager.call.integrations_register(
            name=self.descriptor.name,
            section=SECTION_NAME,
            settings_model=IntegrationModel,
        )
        #
        vault_client = VaultClient()
        secrets = vault_client.get_all_secrets()
        if 'vertex_ai_token_limits' not in secrets:
            secrets['vertex_ai_token_limits'] = json.dumps(TOKEN_LIMITS)
            vault_client.set_secrets(secrets)
        #
        worker_client.register_integration(
            integration_name=self.descriptor.name,
            #
            ai_check_settings_callback=self.ai_check_settings,
            ai_get_models_callback=self.ai_get_models,
            ai_count_tokens_callback=self.count_tokens,
            #
            llm_invoke_callback=self.llm_invoke,
            llm_stream_callback=self.llm_stream,
            #
            chat_model_invoke_callback=self.chat_model_invoke,
            chat_model_stream_callback=self.chat_model_stream,
            #
            embed_documents_callback=self.embed_documents,
            embed_query_callback=self.embed_query,
            #
            indexer_config_callback=self.indexer_config,
        )

    def deinit(self):  # pylint: disable=R0201
        """ De-init module """
        log.info("De-initializing GCP Integration")
        #
        self.descriptor.deinit_all()
