const VertexAiIntegration = {
    delimiters: ['[[', ']]'],
    props: ['instance_name', 'display_name', 'logo_src', 'section_name'],
    emits: ['update'],
    components: {
        'vertex-ai-models-button': VertexAiModelsButton,
    },
    template: `
<div
        :id="modal_id"
        class="modal modal-small fixed-left fade shadow-sm" tabindex="-1" role="dialog"
        @dragover.prevent="modal_style = {'height': '300px', 'border': '2px dashed var(--basic)'}"
        @drop.prevent="modal_style = {'height': '100px', 'border': ''}"
>
    <ModalDialog
            v-model:name="config.name"
            v-model:is_shared="config.is_shared"
            v-model:is_default="is_default"
            @update="update"
            @create="create"
            :display_name="display_name"
            :id="id"
            :is_fetching="is_fetching"
            :is_default="is_default"
    >
        <template #body>
            <div class="form-group">
                <h9>Project</h9>
                <input type="text"
                       v-model="project"
                       class="form-control form-control-alternative"
                       placeholder="Project identifier"
                       :class="{ 'is-invalid': error.project }">
                <div class="invalid-feedback">[[ error.project ]]</div>
                <div>
                <h9>Service account</h9>
                 <SecretFieldInput
                        ref="secretField"
                        v-model="service_account_info"
                        placeholder="Service account info"
                 />
                 <label class="mb-1">
                    <span class="btn btn-secondary btn-sm mr-1 d-inline-block">Upload json</span>
                    <input type="file" accept="application/json"
                    class="form-control form-control-alternative"
                           style="display: none"
                           @change="handleInputFile"
                           :class="{ 'is-invalid': error.template }"
                    >
                </label>
                <div class="invalid-feedback">[[ error.service_account_info ]]</div>
                </div>
                <h9>Zone</h9>
                <input type="text" class="form-control form-control-alternative"
                       v-model="zone"
                       placeholder="VertexAi zone"
                       :class="{ 'is-invalid': error.zone }">
                <div class="invalid-feedback">[[ error.zone ]]</div>
            </div>
            <div>
                <span class="font-h5 font-semibold">Models:</span>
            </div>
            <div class="invalid-feedback d-block">[[ error.models ]]</div>
            <div>
                <button class="btn btn btn-painted mr-1 rounded-pill mb-1" v-for="model in models"
                    >[[ model ]]
                </button>
            </div>
            <vertex-ai-models-button
                ref="VertexAiModelsButton"
                :pluginName="pluginName"
                :error="error.check_connection"
                :body_data="body_data"
                v-model:models="models"
                @handleError="handleError"
            >
            </vertex-ai-models-button>
        </template>
        <template #footer>
            <test-connection-button
                    :apiPath="this.$root.build_api_url('integrations', 'check_settings') + '/' + pluginName"
                    :error="error.check_connection"
                    :body_data="body_data"
                    v-model:is_fetching="is_fetching"
                    @handleError="handleError"
            >
            </test-connection-button>
        </template>

    </ModalDialog>
</div>
    `,
    data() {
        return this.initialState()
    },
    mounted() {
        this.modal.on('hidden.bs.modal', e => {
            this.clear()
        })
    },
    // watch: {
    //     project(newState, oldState) {
    //         this.models = []
    //     }
    // },
    computed: {
        project_id() {
            return getSelectedProjectId()
        },
        body_data() {
            const {
                zone,
                project,
                service_account_info,
                models,
                project_id,
                config,
                is_default,
                status,
                mode
            } = this
            return {
                zone,
                project,
                service_account_info,
                models,
                project_id,
                config,
                is_default,
                status,
                mode
            }
        },
        modal() {
            return $(this.$el)
        },
        modal_id() {
            return `${this.instance_name}_integration`
        }
    },
    methods: {
        clear() {
            Object.assign(this.$data, this.initialState())
            this.$refs.VertexAiModelsButton.clear();
        },
        load(stateData) {
            Object.assign(this.$data, stateData)
        },
        handleEdit(data) {
            const {config, is_default, id, settings} = data
            this.load({...settings, config, is_default, id})
            this.modal.modal('show')
        },
        handleDelete(id) {
            this.load({id})
            this.delete()
        },
        create() {
            if (this.has_validation_error()) return;
            this.is_fetching = true
            fetch(this.api_url + this.pluginName, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(this.body_data)
            }).then(response => {
                this.is_fetching = false
                if (response.ok) {
                    this.modal.modal('hide')
                    this.$emit('update', {...this.$data, section_name: this.section_name})
                } else {
                    this.handleError(response)
                }
            })
        },
        handleError(response) {
            try {
                response.json().then(
                    errorData => {
                        errorData.forEach(item => {
                            this.error = {[item.loc[0]]: item.msg}
                        })
                    }
                )
            } catch (e) {
                alertMain.add(e, 'danger-overlay')
            }
        },
        update() {
            if (this.has_validation_error()) return;
            this.is_fetching = true
            fetch(this.api_url + this.id, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(this.body_data)
            }).then(response => {
                this.is_fetching = false
                if (response.ok) {
                    this.modal.modal('hide')
                    this.$emit('update', {...this.$data, section_name: this.section_name})
                } else {
                    this.handleError(response)
                }
            })
        },
        delete() {
            this.is_fetching = true
            fetch(this.api_url + this.$root.project_id + '/' + this.id, {
                method: 'DELETE',
            }).then(response => {
                this.is_fetching = false
                if (response.ok) {
                    delete this.$data['id']
                    this.$emit('update', {...this.$data, section_name: this.section_name})
                } else {
                    this.handleError(response)
                    alertMain.add(`
                        Deletion error.
                        <button class="btn btn-primary"
                            onclick="vueVm.registered_components.${this.instance_name}.modal.modal('show')"
                        >
                            Open modal
                        <button>
                    `)
                }
            })
        },
        is_empty_field(value) {
            return value.length === 0
        },
        has_validation_error() {
            if (this.is_empty_field(this.models)) {
                this.error.models = 'At least one model is required'
                return true
            }
        },
        handleInputFile(event) {
            const input = event.target
            if (input.files && input.files[0]) {
                this.handleFileUpload(input.files[0])
            }
        },
        handleFileUpload(file) {
            let reader = new FileReader()
            reader.onload = (evt) => {
                this.service_account_info = {
                    value: evt.target.result,
                    from_secrets: false
                }
                this.$refs['secretField'].from_secrets = false
            }
            reader.onerror = (e) => {
                this.error.service_account_info = 'error reading file'
                this.service_account_info = ''
            }
            delete this.error.service_account_info
            reader.readAsText(file)
        },

        initialState: () => ({
            modal_style: {'height': '100px', 'border': ''},
            zone: "",
            project: "",
            test_key: 0,
            service_account_info: "",
            models: [],
            is_default: false,
            is_fetching: false,
            config: {},
            error: {},
            id: null,
            pluginName: 'vertex_ai',
            api_url: V.build_api_url('integrations', 'integration', {trailing_slash: true}),
            status: integration_status.success,
            mode: V.mode
        })
    }
}

register_component('VertexAiIntegration', VertexAiIntegration)
