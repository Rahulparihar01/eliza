# Feature Definition JSON Schema

This document details the standardized Feature Definition JSON structure that serves as the input contract for the multi-agent development platform.

---

## Complete Schema Overview

```mermaid
flowchart TB
    subgraph FeatureDefinition["📄 FEATURE DEFINITION JSON"]
        Root["FeatureDefinition"]
        
        subgraph MetadataSection["📋 metadata"]
            M1["feature_id: string (uuid)"]
            M2["feature_name: string"]
            M3["description: string"]
            M4["version: string (semver)"]
            M5["priority: 'critical' | 'high' | 'medium' | 'low'"]
            M6["owner: string (email)"]
            M7["tags: string[]"]
            M8["created_at: datetime"]
            M9["target_release: string"]
        end

        subgraph DataSection["💾 data_layer"]
            subgraph SQLDef["sql_definitions"]
                SQL1["tables: TableDefinition[]"]
                SQL2["migrations: MigrationConfig"]
                SQL3["indexes: IndexDefinition[]"]
                SQL4["seeds: SeedData[]"]
            end
            
            subgraph GraphDef["graph_definitions"]
                Graph1["nodes: NodeDefinition[]"]
                Graph2["relationships: RelationshipDefinition[]"]
                Graph3["constraints: ConstraintDefinition[]"]
                Graph4["queries: QueryTemplate[]"]
            end
        end

        subgraph ValidationSection["✅ validation_layer"]
            V1["models: PydanticModelDefinition[]"]
            V2["validators: CustomValidatorDefinition[]"]
            V3["enums: EnumDefinition[]"]
            V4["type_aliases: TypeAliasDefinition[]"]
        end

        subgraph APISection["🔌 api_layer"]
            subgraph RestAPI["rest_api"]
                API1["endpoints: EndpointDefinition[]"]
                API2["middleware: MiddlewareConfig[]"]
                API3["error_handlers: ErrorHandlerDefinition[]"]
            end
            
            subgraph MCPDef["mcp_definitions"]
                MCP1["tools: ToolDefinition[]"]
                MCP2["resources: ResourceDefinition[]"]
                MCP3["prompts: PromptDefinition[]"]
            end
        end

        subgraph UISection["🎨 ui_layer"]
            subgraph Pages["pages"]
                UI1["route: string"]
                UI2["components: ComponentReference[]"]
                UI3["layout: LayoutConfig"]
            end
            
            subgraph Components["components"]
                UI4["name: string"]
                UI5["props: PropDefinition[]"]
                UI6["state: StateDefinition"]
                UI7["events: EventDefinition[]"]
            end
            
            subgraph Brand["brand_config"]
                UI8["theme: ThemeReference"]
                UI9["variants: VariantConfig[]"]
                UI10["accessibility: A11yRequirements"]
            end
        end

        subgraph TestSection["🧪 test_layer"]
            T1["unit_tests: UnitTestDefinition[]"]
            T2["integration_tests: IntegrationTestDefinition[]"]
            T3["e2e_tests: E2ETestDefinition[]"]
            T4["coverage_requirements: CoverageConfig"]
            T5["fixtures: FixtureDefinition[]"]
        end

        subgraph DepsSection["🔗 dependencies"]
            D1["features: string[] (feature_ids)"]
            D2["services: ServiceDependency[]"]
            D3["packages: PackageDependency[]"]
        end
    end

    Root --> MetadataSection
    Root --> DataSection
    Root --> ValidationSection
    Root --> APISection
    Root --> UISection
    Root --> TestSection
    Root --> DepsSection

    classDef root fill:#1565C0,stroke:#0D47A1,stroke-width:3px,color:#fff
    classDef section fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef subsection fill:#FAFAFA,stroke:#9E9E9E,stroke-width:1px

    class Root root
    class MetadataSection,DataSection,ValidationSection,APISection,UISection,TestSection,DepsSection section
    class SQLDef,GraphDef,RestAPI,MCPDef,Pages,Components,Brand subsection
```

---

## Detailed Section Schemas

### 1. Metadata Section

```mermaid
flowchart LR
    subgraph Metadata["📋 metadata"]
        direction TB
        
        subgraph Required["Required Fields"]
            R1["feature_id<br/>━━━━━━━━━━━━━━━<br/>type: string (uuid)<br/>example: 'feat-user-prefs-001'"]
            R2["feature_name<br/>━━━━━━━━━━━━━━━<br/>type: string<br/>example: 'User Preferences'"]
            R3["description<br/>━━━━━━━━━━━━━━━<br/>type: string<br/>example: 'Allow users to<br/>save and manage preferences'"]
            R4["version<br/>━━━━━━━━━━━━━━━<br/>type: string (semver)<br/>example: '1.0.0'"]
            R5["priority<br/>━━━━━━━━━━━━━━━<br/>type: enum<br/>values: critical | high |<br/>medium | low"]
        end

        subgraph Optional["Optional Fields"]
            O1["owner<br/>━━━━━━━━━━━━━━━<br/>type: string (email)<br/>example: 'dev@company.com'"]
            O2["tags<br/>━━━━━━━━━━━━━━━<br/>type: string[]<br/>example: ['settings', 'user']"]
            O3["created_at<br/>━━━━━━━━━━━━━━━<br/>type: datetime (ISO8601)<br/>auto-generated"]
            O4["target_release<br/>━━━━━━━━━━━━━━━<br/>type: string<br/>example: 'v2.5.0'"]
            O5["jira_ticket<br/>━━━━━━━━━━━━━━━<br/>type: string<br/>example: 'PROJ-1234'"]
        end
    end

    classDef required fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    classDef optional fill:#FFF9C4,stroke:#F9A825,stroke-width:2px

    class R1,R2,R3,R4,R5 required
    class O1,O2,O3,O4,O5 optional
```

---

### 2. Data Layer Section

```mermaid
flowchart TB
    subgraph DataLayer["💾 data_layer"]
        direction TB

        subgraph SQLDefinitions["sql_definitions"]
            subgraph TableDef["TableDefinition"]
                T1["name: string<br/>schema: string (optional)<br/>description: string"]
                
                subgraph Columns["columns: ColumnDefinition[]"]
                    C1["name: string"]
                    C2["type: SQLType"]
                    C3["nullable: boolean"]
                    C4["default: any"]
                    C5["primary_key: boolean"]
                    C6["unique: boolean"]
                    C7["references: ForeignKeyRef"]
                end
            end

            subgraph IndexDef["IndexDefinition"]
                I1["name: string"]
                I2["columns: string[]"]
                I3["unique: boolean"]
                I4["type: 'btree' | 'hash' | 'gin'"]
            end

            subgraph MigrationDef["MigrationConfig"]
                MG1["auto_generate: boolean"]
                MG2["down_revision: string"]
                MG3["message: string"]
            end
        end

        subgraph GraphDefinitions["graph_definitions"]
            subgraph NodeDef["NodeDefinition"]
                N1["label: string"]
                N2["properties: PropertyDef[]"]
                N3["constraints: string[]"]
            end

            subgraph RelDef["RelationshipDefinition"]
                R1["type: string"]
                R2["from_node: string"]
                R3["to_node: string"]
                R4["properties: PropertyDef[]"]
                R5["cardinality: '1:1' | '1:N' | 'N:M'"]
            end

            subgraph QueryDef["QueryTemplate"]
                Q1["name: string"]
                Q2["cypher: string"]
                Q3["parameters: ParamDef[]"]
                Q4["returns: ReturnType"]
            end
        end
    end

    classDef sql fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef graph fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef detail fill:#FAFAFA,stroke:#9E9E9E,stroke-width:1px

    class SQLDefinitions sql
    class GraphDefinitions graph
    class TableDef,IndexDef,MigrationDef,NodeDef,RelDef,QueryDef,Columns detail
```

---

### 3. Validation Layer Section

```mermaid
flowchart TB
    subgraph ValidationLayer["✅ validation_layer"]
        direction TB

        subgraph ModelDef["PydanticModelDefinition"]
            M1["name: string<br/>description: string<br/>base_class: string"]
            
            subgraph Fields["fields: FieldDefinition[]"]
                F1["name: string"]
                F2["type: PythonType"]
                F3["required: boolean"]
                F4["default: any"]
                F5["description: string"]
                F6["constraints: ConstraintDef"]
            end

            subgraph Constraints["ConstraintDef"]
                CN1["min_length: int"]
                CN2["max_length: int"]
                CN3["pattern: string (regex)"]
                CN4["ge: number (>=)"]
                CN5["le: number (<=)"]
                CN6["enum_values: any[]"]
            end
        end

        subgraph ValidatorDef["CustomValidatorDefinition"]
            V1["name: string"]
            V2["target_field: string"]
            V3["validation_type: 'field' | 'model'"]
            V4["logic_description: string"]
            V5["error_message: string"]
        end

        subgraph EnumDef["EnumDefinition"]
            E1["name: string"]
            E2["values: EnumValue[]"]
            E3["description: string"]
            
            subgraph EnumVal["EnumValue"]
                EV1["key: string"]
                EV2["value: string | int"]
                EV3["description: string"]
            end
        end

        subgraph TypeAlias["TypeAliasDefinition"]
            TA1["name: string"]
            TA2["base_type: string"]
            TA3["description: string"]
        end
    end

    classDef model fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    classDef detail fill:#FAFAFA,stroke:#9E9E9E,stroke-width:1px

    class ModelDef,ValidatorDef,EnumDef,TypeAlias model
    class Fields,Constraints,EnumVal detail
```

---

### 4. API Layer Section

```mermaid
flowchart TB
    subgraph APILayer["🔌 api_layer"]
        direction TB

        subgraph RestAPI["rest_api"]
            subgraph EndpointDef["EndpointDefinition"]
                E1["path: string<br/>method: 'GET'|'POST'|'PUT'|'DELETE'|'PATCH'<br/>summary: string<br/>description: string"]
                
                subgraph Request["request"]
                    RQ1["body_model: string (ref)"]
                    RQ2["query_params: ParamDef[]"]
                    RQ3["path_params: ParamDef[]"]
                    RQ4["headers: HeaderDef[]"]
                end

                subgraph Response["responses"]
                    RS1["status_code: int"]
                    RS2["model: string (ref)"]
                    RS3["description: string"]
                end

                subgraph Auth["auth"]
                    A1["required: boolean"]
                    A2["permissions: string[]"]
                    A3["scopes: string[]"]
                end
            end

            subgraph Middleware["MiddlewareConfig"]
                MW1["name: string"]
                MW2["order: int"]
                MW3["config: object"]
            end
        end

        subgraph MCPDefinitions["mcp_definitions"]
            subgraph ToolDef["ToolDefinition"]
                TD1["name: string"]
                TD2["description: string"]
                
                subgraph ToolInput["input_schema"]
                    TI1["type: 'object'"]
                    TI2["properties: PropDef[]"]
                    TI3["required: string[]"]
                end

                subgraph ToolOutput["output_schema"]
                    TO1["type: string"]
                    TO2["properties: PropDef[]"]
                end
            end

            subgraph ResourceDef["ResourceDefinition"]
                RD1["uri_template: string"]
                RD2["name: string"]
                RD3["description: string"]
                RD4["mime_type: string"]
            end

            subgraph PromptDef["PromptDefinition"]
                PD1["name: string"]
                PD2["description: string"]
                PD3["arguments: ArgDef[]"]
                PD4["template: string"]
            end
        end
    end

    classDef rest fill:#E1F5FE,stroke:#0288D1,stroke-width:2px
    classDef mcp fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef detail fill:#FAFAFA,stroke:#9E9E9E,stroke-width:1px

    class RestAPI rest
    class MCPDefinitions mcp
    class EndpointDef,Middleware,ToolDef,ResourceDef,PromptDef,Request,Response,Auth,ToolInput,ToolOutput detail
```

---

### 5. UI Layer Section

```mermaid
flowchart TB
    subgraph UILayer["🎨 ui_layer"]
        direction TB

        subgraph PageDef["PageDefinition"]
            P1["route: string<br/>name: string<br/>title: string"]
            
            subgraph Layout["layout"]
                L1["type: 'single' | 'sidebar' | 'dashboard'"]
                L2["header: boolean"]
                L3["footer: boolean"]
                L4["navigation: NavConfig"]
            end

            subgraph PageComps["components: ComponentRef[]"]
                PC1["component_id: string"]
                PC2["position: 'main' | 'sidebar' | 'header'"]
                PC3["props_override: object"]
            end
        end

        subgraph ComponentDef["ComponentDefinition"]
            CD1["id: string<br/>name: string<br/>description: string<br/>category: 'form' | 'display' | 'layout' | 'navigation'"]
            
            subgraph Props["props: PropDefinition[]"]
                PR1["name: string"]
                PR2["type: TypeScriptType"]
                PR3["required: boolean"]
                PR4["default: any"]
                PR5["description: string"]
            end

            subgraph State["state: StateDefinition"]
                ST1["local_state: StateDef[]"]
                ST2["global_state: string[] (store keys)"]
                ST3["derived_state: DerivedDef[]"]
            end

            subgraph Events["events: EventDefinition[]"]
                EV1["name: string"]
                EV2["trigger: string"]
                EV3["handler_description: string"]
                EV4["api_call: string (endpoint ref)"]
            end
        end

        subgraph BrandConfig["brand_config"]
            subgraph Theme["theme"]
                TH1["base: 'light' | 'dark' | 'system'"]
                TH2["primary_color: string"]
                TH3["font_family: string"]
            end

            subgraph Variants["variants: VariantConfig[]"]
                VR1["name: string"]
                VR2["conditions: string"]
                VR3["styles: StyleOverride"]
            end

            subgraph A11y["accessibility"]
                AC1["aria_labels: boolean"]
                AC2["keyboard_nav: boolean"]
                AC3["screen_reader: boolean"]
                AC4["color_contrast: 'AA' | 'AAA'"]
            end
        end
    end

    classDef page fill:#FCE4EC,stroke:#C2185B,stroke-width:2px
    classDef component fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    classDef brand fill:#FFF8E1,stroke:#FF8F00,stroke-width:2px
    classDef detail fill:#FAFAFA,stroke:#9E9E9E,stroke-width:1px

    class PageDef page
    class ComponentDef component
    class BrandConfig brand
    class Layout,PageComps,Props,State,Events,Theme,Variants,A11y detail
```

---

### 6. Test Layer Section

```mermaid
flowchart TB
    subgraph TestLayer["🧪 test_layer"]
        direction TB

        subgraph UnitTest["UnitTestDefinition"]
            UT1["target: string (function/class ref)<br/>target_type: 'function' | 'class' | 'method'"]
            
            subgraph Scenarios["scenarios: TestScenario[]"]
                SC1["name: string"]
                SC2["description: string"]
                SC3["inputs: object"]
                SC4["expected_output: any"]
                SC5["expected_exception: string"]
                SC6["mocks: MockDef[]"]
            end
        end

        subgraph IntegrationTest["IntegrationTestDefinition"]
            IT1["name: string<br/>description: string"]
            
            subgraph Flow["flow: FlowStep[]"]
                FL1["step: int"]
                FL2["action: string"]
                FL3["endpoint: string"]
                FL4["payload: object"]
                FL5["assertions: AssertionDef[]"]
            end

            subgraph Setup["setup"]
                SU1["fixtures: string[]"]
                SU2["database_state: object"]
                SU3["mock_services: string[]"]
            end
        end

        subgraph E2ETest["E2ETestDefinition"]
            E2E1["name: string<br/>description: string<br/>browser: 'chromium' | 'firefox' | 'webkit'"]
            
            subgraph UserFlow["user_flow: UserAction[]"]
                UF1["action: 'navigate' | 'click' | 'type' | 'wait'"]
                UF2["selector: string"]
                UF3["value: string"]
                UF4["assertion: string"]
            end
        end

        subgraph Coverage["coverage_requirements"]
            CV1["minimum_percentage: int"]
            CV2["exclude_patterns: string[]"]
            CV3["branch_coverage: boolean"]
            CV4["fail_under: int"]
        end

        subgraph Fixtures["FixtureDefinition"]
            FX1["name: string"]
            FX2["scope: 'function' | 'class' | 'module' | 'session'"]
            FX3["data: object"]
            FX4["factory: string (function ref)"]
        end
    end

    classDef unit fill:#FBE9E7,stroke:#D84315,stroke-width:2px
    classDef integration fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef e2e fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef config fill:#F5F5F5,stroke:#616161,stroke-width:2px
    classDef detail fill:#FAFAFA,stroke:#9E9E9E,stroke-width:1px

    class UnitTest unit
    class IntegrationTest integration
    class E2ETest e2e
    class Coverage,Fixtures config
    class Scenarios,Flow,Setup,UserFlow detail
```

---

### 7. Dependencies Section

```mermaid
flowchart TB
    subgraph Dependencies["🔗 dependencies"]
        direction TB

        subgraph FeatureDeps["feature_dependencies"]
            FD1["feature_ids: string[]<br/>━━━━━━━━━━━━━━━<br/>Other features this<br/>feature depends on"]
            FD2["dependency_type:<br/>'hard' | 'soft'<br/>━━━━━━━━━━━━━━━<br/>hard = must exist<br/>soft = optional"]
        end

        subgraph ServiceDeps["service_dependencies"]
            SD1["name: string"]
            SD2["type: 'database' | 'cache' | 'queue' | 'external_api'"]
            SD3["required: boolean"]
            SD4["config_key: string"]
            SD5["health_check: string (endpoint)"]
        end

        subgraph PackageDeps["package_dependencies"]
            subgraph Python["python"]
                PY1["package: string"]
                PY2["version: string (semver)"]
                PY3["dev_only: boolean"]
            end

            subgraph Node["node"]
                ND1["package: string"]
                ND2["version: string"]
                ND3["dev_only: boolean"]
            end
        end
    end

    classDef feature fill:#E8EAF6,stroke:#3F51B5,stroke-width:2px
    classDef service fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef package fill:#E0F2F1,stroke:#00897B,stroke-width:2px

    class FeatureDeps feature
    class ServiceDeps service
    class PackageDeps,Python,Node package
```

---

## Complete JSON Example

```mermaid
flowchart TB
    subgraph Example["📋 EXAMPLE: User Preferences Feature"]
        direction TB

        subgraph JSON["feature_definition.json"]
            Code["
{
  'metadata': {
    'feature_id': 'feat-user-prefs-001',
    'feature_name': 'User Preferences',
    'description': 'Allow users to save preferences',
    'version': '1.0.0',
    'priority': 'high',
    'owner': 'team@company.com',
    'tags': ['settings', 'user', 'personalization']
  },
  
  'data_layer': {
    'sql_definitions': {
      'tables': [{
        'name': 'user_preferences',
        'columns': [
          {'name': 'id', 'type': 'SERIAL', 'primary_key': true},
          {'name': 'user_id', 'type': 'INTEGER', 'references': 'users.id'},
          {'name': 'key', 'type': 'VARCHAR(100)', 'nullable': false},
          {'name': 'value', 'type': 'JSONB'},
          {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'NOW()'}
        ]
      }]
    },
    'graph_definitions': {
      'nodes': [{'label': 'Preference', 'properties': ['key', 'value']}],
      'relationships': [{'type': 'HAS_PREFERENCE', 'from': 'User', 'to': 'Preference'}]
    }
  },
  
  'validation_layer': {
    'models': [{
      'name': 'UserPreference',
      'fields': [
        {'name': 'user_id', 'type': 'int', 'required': true},
        {'name': 'key', 'type': 'str', 'constraints': {'max_length': 100}},
        {'name': 'value', 'type': 'dict', 'required': true}
      ]
    }]
  },
  
  'api_layer': {
    'rest_api': {
      'endpoints': [
        {'path': '/preferences', 'method': 'GET', 'auth': {'required': true}},
        {'path': '/preferences/{key}', 'method': 'PUT', 'auth': {'required': true}},
        {'path': '/preferences/{key}', 'method': 'DELETE', 'auth': {'required': true}}
      ]
    },
    'mcp_definitions': {
      'tools': [
        {'name': 'get_user_preferences', 'description': 'Get all preferences'},
        {'name': 'update_preference', 'description': 'Update a preference'}
      ]
    }
  },
  
  'ui_layer': {
    'pages': [{
      'route': '/settings/preferences',
      'name': 'PreferencesPage',
      'components': ['PreferencesList', 'PreferenceEditor']
    }],
    'components': [
      {'id': 'PreferencesList', 'category': 'display'},
      {'id': 'PreferenceEditor', 'category': 'form'}
    ]
  },
  
  'test_layer': {
    'coverage_requirements': {'minimum_percentage': 85},
    'unit_tests': [
      {'target': 'PreferenceService', 'scenarios': ['get', 'update', 'delete']}
    ]
  },
  
  'dependencies': {
    'features': ['feat-auth-001'],
    'services': [{'name': 'postgres', 'type': 'database', 'required': true}]
  }
}
            "]
        end

        subgraph AgentUsage["How Agents Use This"]
            A1["🗄️ SQL Agent reads:<br/>data_layer.sql_definitions"]
            A2["🔗 Graph Agent reads:<br/>data_layer.graph_definitions"]
            A3["📋 Pydantic Agent reads:<br/>validation_layer.models"]
            A4["⚡ API Agent reads:<br/>api_layer.rest_api"]
            A5["🛠️ MCP Agent reads:<br/>api_layer.mcp_definitions"]
            A6["💻 Frontend Agent reads:<br/>ui_layer.pages, components"]
            A7["🎯 Brand Agent reads:<br/>ui_layer.brand_config"]
            A8["📝 Test Builder reads:<br/>test_layer.*"]
        end
    end

    JSON --> AgentUsage
```

---

## Schema Validation Rules

| Section | Required | Validated By |
|---------|----------|--------------|
| `metadata` | ✅ Yes | Orchestrator Agent |
| `metadata.feature_id` | ✅ Yes | Must be unique UUID |
| `metadata.feature_name` | ✅ Yes | Non-empty string |
| `metadata.version` | ✅ Yes | Valid semver |
| `data_layer` | ⚠️ Conditional | Required if feature has data |
| `validation_layer` | ⚠️ Conditional | Required if API layer exists |
| `api_layer` | ⚠️ Conditional | Required if feature has API |
| `ui_layer` | ⚠️ Conditional | Required if feature has UI |
| `test_layer` | ✅ Yes | Always required |
| `dependencies` | ⚠️ Optional | Validated against existing features |

---

## Agent-to-Schema Mapping

```mermaid
flowchart LR
    subgraph Schema["Feature Definition Sections"]
        S1["metadata"]
        S2["data_layer.sql_definitions"]
        S3["data_layer.graph_definitions"]
        S4["validation_layer"]
        S5["api_layer.rest_api"]
        S6["api_layer.mcp_definitions"]
        S7["ui_layer.pages"]
        S8["ui_layer.components"]
        S9["ui_layer.brand_config"]
        S10["test_layer"]
        S11["dependencies"]
    end

    subgraph Agents["Consuming Agents"]
        A0["🎯 Orchestrator"]
        A1["🗄️ SQL DB Architect"]
        A2["🔗 Graph DB Architect"]
        A3["📋 Pydantic Validation"]
        A4["⚡ API Agent"]
        A5["🛠️ MCP Builder"]
        A6["💻 Frontend Agent"]
        A7["🎯 Brand Compliance"]
        A8["📝 Test Builder"]
        A9["▶️ Test Runner"]
    end

    S1 --> A0
    S2 --> A1
    S3 --> A2
    S4 --> A3
    S5 --> A4
    S6 --> A5
    S7 --> A6
    S8 --> A6
    S9 --> A7
    S10 --> A8
    S10 --> A9
    S11 --> A0

    classDef schema fill:#E3F2FD,stroke:#1565C0,stroke-width:1px
    classDef agent fill:#E8F5E9,stroke:#2E7D32,stroke-width:1px

    class S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11 schema
    class A0,A1,A2,A3,A4,A5,A6,A7,A8,A9 agent
```




