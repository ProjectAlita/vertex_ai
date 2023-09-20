const VertexAiModelsButton = {
    delimiters: ['[[', ']]'],
    props: ['error', 'pluginName', 'is_loading_models', 'body_data', 'models'],
    emits: ['handleError', 'update:error', 'update:models'],
    data() {
        return this.initialState()
    },
    computed: {
        test_connection_class() {
            if (400 <= this.status && this.status < 600) {
                return 'btn-warning'

            } else {
                return 'btn-secondary'
            }
        },
        show_error() {
            return (this.test_connection_class === 'btn-warning')
        },
        hasErrors() {
            return this.warnings.length > 0
        },
    },
    template: `
    <div>
        <div>
            <button type="button" class="btn btn-sm mt-3"
                    @click="loadModels"
                    :class="[{disabled: is_loading_models, updating: is_loading_models, 'is-invalid': error}, test_connection_class]"
            >
                Load models
            </button>
            <button type="button" class="btn btn-sm mt-3"
                    @click="clearModels"
                    class="btn-secondary"
            >
                Clear models
            </button>
            <div class="invalid-feedback" v-if="show_error">[[ error ]]</div>
            <div v-if="is_models_loaded" class="mr-2 cell-input" style="min-width: 250px">
                <div>
                    <multiselect-dropdown
                        placeholder="Select models"
                        maxHeight="300"
                        v-model="selected_models"
                        :list_items="allModels"
                    ></multiselect-dropdown>
                </div>
            </div>
            <p class="font-h5 font-semibold mt-3">Add model names manually:</p>
            <div class="input-group d-flex mt-1">
                <div class="custom-input flex-grow-1">
                    <input type="text" placeholder="Model name" class="form-control form-control-alternative"
                       v-model="model"
                       :class="{ 'is-invalid': hasErrors }"
                >
                </div>
                <button class="btn btn-lg btn-secondary ml-2" type="button"
                    @click="handleAdd"
                    :disabled="model === ''"
                    :class="{ 'btn-danger': hasErrors }"
                >
                    Add
                </button>
                <div class="invalid-feedback d-block" v-for="warning in warnings">[[ warning ]]</div>
            </div>
        </div>
    </div>
    `,
    watch: {
        is_loading_models(newState, oldState) {
            if (newState) {
                this.status = 0
            }
        },
        selected_models(newState, oldState) {
            console.log('selected_models', newState)
            if (newState) {
                this.$emit('update:models', newState)
            }
        },
        models(newState, oldState) {
            if (newState) {
                this.selected_models = newState
            }
        }
    },
    methods: {
        clear() {
            Object.assign(this.$data, this.initialState())
        },
        async loadModels() {
            this.is_loading_models = true
            this.loadModelsAPI(this.pluginName, this.body_data).then(res => {
                this.allModels = res.map(model => ({
                    name: model.id,
                }));
                this.selected_models = res.filter(model => this.models.includes(model.model)).map(model => model.model);
            })
        },
        clearModels() {
            this.selected_models = []
        },
        async loadModelsAPI(integration_name, settings) {
            const api_url = V.build_api_url(integration_name, 'models')
            const response = await fetch(`${api_url}/${getSelectedProjectId()}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            })
            this.status = response.status
            if (!response.ok) {
                this.is_loading_models = false
                this.$emit('handleError', response)
                return []
            } else {
                this.is_models_loaded = true
                this.is_loading_models = false
                return response.json();
            }
        },
        validateUniqueness(model) {
            return this.selected_models.find(e => e.toLowerCase() === model.toLowerCase()) === undefined
        },
        add(model) {
            if (model === '') return;
            if (!this.validateUniqueness(model)) {
                this.warnings.push(`Model ${model} is already added`)
                return;
            }
            this.selected_models = [...this.selected_models, model];
        },
        handleAdd() {
            this.warnings = []
            this.model.split(',').forEach(i => {
                this.add(i.trim().toLowerCase())
            })
            if (!this.hasErrors) {
                this.model = ''
            }
        },
        initialState: () => ({
            status: 0,
            model: 'text-bison@001',
            allModels: [],
            is_loading_models: false,
            is_models_loaded: false,
            selected_models: [],
            warnings: [],
        })
    }
}
