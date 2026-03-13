# AI Platform SDK Architecture Deep Dive

## Executive Summary

This document provides a comprehensive analysis of modern AI platform SDK architecture, focusing on the integration patterns between project templates, core SDK components, and the configuration-driven template system. The architecture demonstrates a sophisticated layered approach that enables rapid development of specialized LLM applications through reusable, configurable templates.

---

## 1. SDK Architecture Overview

### 1.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PROJECT TEMPLATES                    │
│  ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │      Q&A        │    │    text-to-sql             │ │
│  │   Template      │    │    Template                 │ │
│  └─────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    SDK CORE LAYER                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   API       │  │ Experiment  │  │   Generation    │ │
│  │ Components  │  │ Framework   │  │   Pipeline      │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  PLATFORM SERVICES                     │
│        FastAPI Routes → Inference Engine → Models      │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Key Integration Patterns

**Configuration-Driven Architecture:**
- YAML-based configuration templates
- Dynamic code generation from configurations
- Environment-specific parameter injection
- Modular component composition

**Template-to-Core Integration:**
- Templates consume SDK APIs through standardized interfaces
- Shared utilities and base classes
- Common patterns for data processing and model interaction
- Consistent error handling and logging

---

## 2. Project Template Architecture

### 2.1 Q&A Template Structure

The Q&A template demonstrates the full architecture pattern:

```
Q&A/
├── main_scripts/           # Orchestration layer
│   ├── init_project.py    # Project initialization
│   ├── pipeline.py        # Main processing pipeline
│   ├── experiment_prep.py # Experiment setup
│   ├── train.py          # Training orchestration
│   └── evaluate.py       # Evaluation pipeline
├── models/               # Domain-specific models
│   ├── chunking/         # Document processing
│   ├── generators/       # Content generation
│   ├── loaders/         # Data loading
│   └── project/         # Project management
├── utils/               # Shared utilities
├── yml-templates/       # Configuration templates
│   ├── project.yml      # Project configuration
│   ├── experiment.yml   # Experiment parameters
│   ├── prompts.yml      # Prompt templates
│   └── roles.yml        # Role definitions
└── cli-app.py          # Command-line interface
```

### 2.2 Configuration-Driven Template System

**YAML Configuration Schema:**
```yaml
# project.yml - Core project configuration
AI_Platform:
  api_key:
    value: <your_api_key>
    description: AI platform API key
  base_url:
    value: https://api.openai.com/v1
    description: AI platform base url
  base_url_inf:
    value: https://api.openai.com/v1
    description: AI platform base url for inference

Project:
  project_name:
    value: initial_template
  topic:
    value: topic_placeholder
    description: topic of the project

document_metadata:
  product:
    value: "Research Paper Title"
  keywords:
    value: ["LLM", "training", "evaluation"]
```

**Dynamic Code Generation:**
```python
# From sdk/lamini/project_templates/Q&A/utils/utils.py - TESTED
def generate_prompts_class_from_yml(yml_path: str, output_path: str = "prompts.py"):
    """Generate Python class from YAML prompt definitions"""
    with open(yml_path, 'r') as file:
        prompts_data = yaml.safe_load(file)
    
    class_content = "class Prompts:\n\n"
    
    for prompt_name, prompt_data in prompts_data.items():
        prompt_text = prompt_data.get('prompt', '')
        class_content += f'    {prompt_name.upper()} = """\n{prompt_text}\n    """\n\n'
    
    with open(output_path, 'w') as file:
        file.write(class_content)
```

**Enhanced Template Configuration Manager:**
```python
# From sdk/lamini/project_templates/common/config_manager.py - EXAMPLE
import yaml
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class TemplateConfigManager:
    """Enhanced configuration manager with validation and error handling"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.config_cache: Dict[str, Any] = {}
        self.schema_validators = {}
    
    def load_config_with_validation(self, config_type: str) -> Dict[str, Any]:
        """Load configuration with comprehensive validation"""
        config_path = self.project_path / "ymls" / f"{config_type}.yml"
        
        try:
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            # Validate configuration
            validation_result = self._validate_config(config, config_type)
            if not validation_result.is_valid:
                raise ValueError(f"Invalid configuration: {', '.join(validation_result.errors)}")
            
            # Log warnings if any
            for warning in validation_result.warnings:
                logger.warning(f"Configuration warning: {warning}")
            
            # Cache the configuration
            self.config_cache[config_type] = config
            logger.info(f"Successfully loaded {config_type} configuration")
            
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load {config_type} configuration: {e}")
            raise
    
    def _validate_config(self, config: Dict[str, Any], config_type: str) -> ValidationResult:
        """Validate configuration against schema"""
        errors = []
        warnings = []
        
        try:
            # Required fields validation
            required_fields = self._get_required_fields(config_type)
            for field_path in required_fields:
                if not self._has_nested_field(config, field_path):
                    errors.append(f"Missing required field: {field_path}")
            
            # Type validation
            type_errors = self._validate_field_types(config, config_type)
            errors.extend(type_errors)
            
            # Environment variable validation
            env_warnings = self._validate_environment_variables(config)
            warnings.extend(env_warnings)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(is_valid=False, errors=[str(e)], warnings=[])
    
    def _get_required_fields(self, config_type: str) -> List[str]:
        """Get required fields for configuration type"""
        required_fields_map = {
            'project': [
                'AI_Platform.api_key.value',
                'AI_Platform.base_url.value',
                'Project.project_name.value'
            ],
            'experiment': [
                'Experiment.batch_size.value',
                'Experiment.model.value'
            ],
            'prompts': [
                'question_generation.prompt',
                'answer_generation.prompt'
            ]
        }
        return required_fields_map.get(config_type, [])
    
    def _has_nested_field(self, config: Dict, field_path: str) -> bool:
        """Check if nested field exists in configuration"""
        keys = field_path.split('.')
        current = config
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        
        return current is not None
    
    def update_config_safely(self, config_type: str, updates: Dict[str, Any]) -> bool:
        """Update configuration with backup and validation"""
        config_path = self.project_path / "ymls" / f"{config_type}.yml"
        backup_path = config_path.with_suffix('.yml.backup')
        
        try:
            # Create backup
            if config_path.exists():
                import shutil
                shutil.copy2(config_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Load current config
            current_config = self.load_config_with_validation(config_type)
            
            # Apply updates
            updated_config = self._deep_merge_configs(current_config, updates)
            
            # Validate updated config
            validation_result = self._validate_config(updated_config, config_type)
            if not validation_result.is_valid:
                raise ValueError(f"Updated configuration is invalid: {', '.join(validation_result.errors)}")
            
            # Save updated config
            with open(config_path, 'w', encoding='utf-8') as file:
                yaml.dump(updated_config, file, default_flow_style=False, indent=2)
            
            # Update cache
            self.config_cache[config_type] = updated_config
            logger.info(f"Successfully updated {config_type} configuration")
            
            # Remove backup on success
            if backup_path.exists():
                backup_path.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            
            # Restore from backup if it exists
            if backup_path.exists():
                import shutil
                shutil.copy2(backup_path, config_path)
                logger.info("Restored configuration from backup")
                backup_path.unlink()
            
            raise
    
    def _deep_merge_configs(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
```

### 2.3 Template Lifecycle Management

**Project Initialization Workflow:**
```python
# From sdk/lamini/project_templates/Q&A/main_scripts/init_project.py - TESTED
def main():
    # 1. Create project directory structure
    project_dir = create_project_directory(project_name)
    
    # 2. Copy and customize YAML templates
    yml_files = copy_yml_templates(project_dir, project_name, topic)
    
    # 3. Initialize project database
    check_and_create_projects_table()
    
    # 4. Register project in database
    add_project_to_db(project_name, yml_files)
    
    # 5. Generate dynamic code from templates
    generate_prompts_class_from_yml()
```

---

## 3. SDK Core Layer Integration

### 3.1 API Components (`sdk/lamini/api/`)

**Core SDK Classes:**

```python
# Main SDK Entry Point
class AIPlatform:
    """Main interface for AI platform functionality"""
    def __init__(self, model_name, api_key=None, api_url=None):
        self.completion = Completion(api_key, api_url)
        self.trainer = Train(api_key, api_url)
        self.model_downloader = ModelDownloader(api_key, api_url)
    
    def generate(self, prompt, model_name=None, output_type=None):
        """Core generation method"""
        return self.completion.generate(...)

# OpenAI-Compatible Client
class BaseOpenAIClient:
    """Simplified OpenAI client for template integration"""
    def __init__(self, api_key, api_url):
        self.client = openai.OpenAI(
            api_key=api_key, 
            base_url=f"{api_url}/inf"
        )
    
    async def execute_completion(self, model, prompt, response_schema):
        """Structured completion with schema validation"""
```

**Template Integration Pattern:**
```python
# From Q&A pipeline.py - How templates use SDK
from lamini.api.openai_client import BaseOpenAIClient

# Templates instantiate SDK components with config
client = BaseOpenAIClient(
    api_key=config['AI_Platform']['api_key']['value'],
    api_base_url=config['AI_Platform']['base_url_inf']['value']
)

# Use SDK for document processing
semantic_chunker = PDFSemanticChunker(
    api_key=os.getenv('OPENAI_API_KEY'),
    api_base_url=config['AI_Platform']['base_url_inf']['value'],
    embedding_model="text-embedding-3-small"
)
```

### 3.2 Experiment Framework (`sdk/lamini/experiment/`)

**Pipeline Architecture:**
```python
# Base Experiment Framework
class BaseAgenticPipeline:
    """Pipeline for processing experiment objects through generators/validators"""
    
    def __init__(self, generators, validators, order=None):
        self.generators = generators  # Dict of BaseGenerator instances
        self.validators = validators  # Dict of BaseValidator instances
        self.order = self._build_pipeline_order(order)
    
    def __call__(self, prompt_obj):
        """Execute pipeline with validation and recording"""
        # 1. Pipeline Logic Validation
        # 2. Pipeline Spotcheck  
        # 3. Full Dataset Processing

class BaseGenerator:
    """Base class for content generation steps"""
    def __init__(self, model, role, output_type, instruction):
        self.model = model
        self.role = role
        self.output_type = output_type
        self.instruction = instruction
```

**Template-Experiment Integration:**
```python
# From Q&A experiment_prep.py
def build_experiment_pipeline(ExperimentDefinition):
    # Load project configuration
    with open(f"{project_dir}/ymls/project.yml") as file:
        project_file = yaml.safe_load(file)
    
    # Generate roles and prompts dynamically
    roles = generate_role_descriptions(project_file["Project"]["topic"])
    
    # Create pipeline components using SDK
    question_generator = BaseGenerator(
        model="meta-llama/Llama-3.1-8B-Instruct",
        name="question_generator",
        role=roles["question_generator"],
        output_type={"question": "str"},
        instruction=Prompts.QUESTION,
    )
    
    # Build complete pipeline
    pipeline = BaseAgenticPipeline(
        generators={"question_generator": question_generator, ...},
        validators={"validator": validator}
    )
    
    return {
        "pipeline": pipeline,
        "experiment": experiment,
        "question_generator": question_generator,
        ...
    }
```

### 3.3 Generation Pipeline (`sdk/lamini/generation/`)

**Core Generation Components:**
```python
# Base classes for prompt-based operations
class PromptObject:
    """Container for prompt-response pairs with metadata"""
    def __init__(self, prompt="", response=None, data=None):
        self.prompt = prompt
        self.response = response
        self.data = data or {}

class GenerationNode:
    """Individual processing node in generation pipeline"""
    
class GenerationPipeline:
    """Orchestrates multiple generation nodes"""
```

---

## 4. Configuration-Driven Template Pattern

### 4.1 Template Instantiation Process

**1. Template Discovery & Selection:**
```bash
# CLI-driven template selection
./lamini init-project --template Q&A --project_name my_project --topic "Financial Analysis"
```

**2. Configuration Template Processing:**
```python
# Template customization workflow
def copy_yml_templates(project_dir, project_name, topic):
    template_dir = "yml-templates/"
    target_dir = f"{project_dir}/ymls/"
    
    # Copy and customize each template
    for yml_file in ["project.yml", "experiment.yml", "prompts.yml", "roles.yml"]:
        customize_template(
            src=f"{template_dir}/{yml_file}",
            dest=f"{target_dir}/{yml_file}",
            substitutions={
                "project_name": project_name,
                "topic": topic,
                "timestamp": datetime.now().isoformat()
            }
        )
```

**3. Dynamic Code Generation:**
```python
# Runtime code generation from configuration
def generate_prompts_class_from_yml(yml_path, output_path):
    """Convert YAML prompt definitions to Python class"""
    prompts = yaml.safe_load(open(yml_path))
    
    class_code = "class Prompts:\n\n"
    for name, config in prompts.items():
        class_code += f'    {name.upper()} = """\n{config["prompt"]}\n    """\n\n'
    
    with open(output_path, 'w') as f:
        f.write(class_code)

def generate_role_descriptions(topic, api_key):
    """Generate role definitions using LLM"""
    client = Lamini(model_name="meta-llama/Llama-3.1-8B-Instruct")
    
    roles = {}
    for role_type in ["question_generator", "answer_generator", "validator"]:
        prompt = f"Generate a role description for {role_type} in {topic} domain"
        roles[role_type] = client.generate(prompt)
    
    return roles
```

### 4.2 Configuration Schema Patterns

**Hierarchical Configuration Structure:**
```yaml
# Multi-level configuration with inheritance
Global:
  lamini_config: &lamini_defaults
    api_key: ${LAMINI_API_KEY}
    base_url: ${LAMINI_BASE_URL:-http://localhost:5001}
    
Project:
  <<: *lamini_defaults  # YAML inheritance
  specific_config:
    chunk_strategy: "semantic"
    window_size: 3
    
Experiment:
  <<: *lamini_defaults
  parameters:
    batch_size: 32
    similarity_threshold: 0.85
```

**Environment-Specific Overrides:**
```python
# Configuration resolution with environment precedence
def resolve_config(base_config, environment="development"):
    # 1. Load base template configuration
    config = load_yaml(f"yml-templates/project.yml")
    
    # 2. Apply environment-specific overrides
    env_overrides = load_yaml(f"environments/{environment}.yml")
    config = merge_configs(config, env_overrides)
    
    # 3. Apply runtime environment variables
    config = substitute_env_vars(config)
    
    # 4. Validate configuration schema
    validate_config_schema(config)
    
    return config
```

### 4.3 Template Extension Patterns

**Template Inheritance:**
```python
# Base template class
class BaseProjectTemplate:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.sdk_client = self.initialize_sdk()
    
    def initialize_sdk(self):
        return Lamini(
            model_name=self.config['model']['default'],
            api_key=self.config['Lamini']['api_key']['value'],
            api_url=self.config['Lamini']['base_url']['value']
        )
    
    def run_pipeline(self):
        raise NotImplementedError("Subclasses must implement run_pipeline")

# Specialized template implementation
class QAProjectTemplate(BaseProjectTemplate):
    def run_pipeline(self):
        # Q&A-specific pipeline implementation
        chunks = self.process_documents()
        questions = self.generate_questions(chunks)
        answers = self.generate_answers(questions, chunks)
        validated = self.validate_qa_pairs(questions, answers)
        return validated
```

**Plugin Architecture:**
```python
# Extensible component system
class ComponentRegistry:
    def __init__(self):
        self.components = {}
    
    def register(self, component_type, implementation):
        self.components[component_type] = implementation
    
    def create(self, component_type, config):
        component_class = self.components[component_type]
        return component_class(**config)

# Template registration
registry = ComponentRegistry()
registry.register("chunker", PDFSemanticChunker)
registry.register("generator", BaseGenerator)
registry.register("validator", FactualityValidator)

# Dynamic component instantiation
chunker = registry.create("chunker", config['chunking'])
```

---

## 5. CLI and Project Management System

### 5.1 CLI Architecture (`cmd/`)

**Bashly-Based CLI Generation:**
```yaml
# cmd/bashly.yml - CLI command definitions
name: lamini
help: Lamini Platform CLI
version: 0.1.0

commands:
  - name: init-project
    help: Initialize a new project from template
    args:
      - name: template
        help: Template name (Q&A, text-to-sql)
      - name: project-name
        help: Name for the new project
    flags:
      - long: --topic
        help: Project topic/domain
        arg: topic
      - long: --config
        help: Custom configuration file
        arg: config
```

**Command Implementation Pattern:**
```bash
# Generated command script structure
#!/bin/bash

# Command: lamini init-project
template=${args[template]}
project_name=${args[project-name]}
topic=${args[--topic]}

# Validate inputs
if [[ -z "$template" || -z "$project_name" ]]; then
    echo "Error: Template and project name are required"
    exit 1
fi

# Execute Python template initialization
cd sdk/lamini/project_templates/$template
python main_scripts/init_project.py \
    --project_name "$project_name" \
    --topic "$topic"
```

### 5.2 Project Lifecycle Management

**Project Database Schema:**
```sql
-- Project registry and versioning
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    template_type VARCHAR(100) NOT NULL,
    topic VARCHAR(255),
    config_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active'
);

CREATE TABLE project_configs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    config_type VARCHAR(100) NOT NULL, -- 'project', 'experiment', 'prompts'
    config_content JSONB NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Project Management Operations:**
```python
class ProjectDB:
    """Project lifecycle management"""
    
    def create_project(self, name, template_type, topic, config_files):
        """Create new project with initial configuration"""
        project_id = self.insert_project(name, template_type, topic)
        
        for config_type, config_path in config_files.items():
            config_content = yaml.safe_load(open(config_path))
            self.insert_config(project_id, config_type, config_content, version=1)
        
        return project_id
    
    def update_project(self, project_name):
        """Version and update existing project"""
        current_version = self.get_latest_version(project_name)
        new_version = current_version + 1
        
        # Update configurations with new version
        self.version_configs(project_name, new_version)
        
        return new_version
    
    def get_project_config(self, project_name, config_type, version=None):
        """Retrieve project configuration by version"""
        if version is None:
            version = self.get_latest_version(project_name)
        
        return self.fetch_config(project_name, config_type, version)
```

---

## 6. Integration Flow Examples

### 6.1 Complete Q&A Project Flow

**1. Project Initialization:**
```bash
# CLI command
./lamini init-project Q&A financial_analysis --topic "Financial Statement Analysis"
```

**2. Configuration Processing:**
```python
# Template instantiation (init_project.py)
def create_financial_analysis_project():
    # 1. Create directory structure
    project_dir = "projects/financial_analysis/"
    
    # 2. Customize YAML templates
    configs = {
        "project.yml": customize_project_config(
            topic="Financial Statement Analysis",
            models=["meta-llama/Llama-3.1-8B-Instruct"],
            chunking_strategy="semantic"
        ),
        "experiment.yml": customize_experiment_config(
            batch_size=32,
            evaluation_metrics=["accuracy", "factuality"]
        )
    }
    
    # 3. Generate dynamic code
    generate_prompts_class_from_yml(
        yml_path="projects/financial_analysis/ymls/prompts.yml",
        output_path="models/project/prompts.py"
    )
    
    # 4. Register in project database
    ProjectDB().create_project("financial_analysis", "Q&A", configs)
```

**3. Pipeline Execution:**
```python
# Main pipeline execution (pipeline.py)
def run_financial_analysis_pipeline():
    # Load project configuration
    config = yaml.safe_load(open("projects/financial_analysis/ymls/project.yml"))
    
    # Initialize SDK components
    client = BaseOpenAIClient(
        api_key=config['Lamini']['api_key']['value'],
        api_base_url=config['Lamini']['base_url_inf']['value']
    )
    
    # Document processing with SDK
    chunker = PDFSemanticChunker(
        api_key=config['Lamini']['api_key']['value'],
        api_base_url=config['Lamini']['base_url_inf']['value'],
        embedding_model="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # Process documents
    documents = load_financial_documents()
    chunks = chunker.chunk_documents(documents)
    
    # Build experiment pipeline
    pipeline_components = build_experiment_pipeline(config)
    pipeline = pipeline_components["pipeline"]
    
    # Execute Q&A generation
    results = pipeline(chunks)
    
    return results
```

### 6.2 Cross-Layer Integration Patterns

**Configuration → SDK → Platform:**
```python
# Configuration drives SDK instantiation
config = load_project_config("financial_analysis")

# SDK components configured from YAML
sdk_client = Lamini(
    model_name=config['model']['default'],
    api_key=config['Lamini']['api_key']['value'],
    api_url=config['Lamini']['base_url']['value']
)

# SDK calls platform APIs
response = sdk_client.generate(
    prompt=config['prompts']['question_generation'],
    output_type={"question": "str"}
)

# Platform processes through inference engine
# FastAPI → Load Balancer → Inference Engine → Model
```

**Template → Experiment → Generation:**
```python
# Template defines experiment structure
experiment_config = {
    "generators": ["question_generator", "answer_generator"],
    "validators": ["factuality_validator"],
    "pipeline_order": ["generate_questions", "generate_answers", "validate"]
}

# Experiment framework orchestrates components
pipeline = BaseAgenticPipeline(
    generators=create_generators(experiment_config),
    validators=create_validators(experiment_config),
    order=experiment_config['pipeline_order']
)

# Generation pipeline executes with SDK
results = pipeline.execute(input_data)
```

---

## 7. Template Development Best Practices

### 7.1 Configuration Design Patterns

**Hierarchical Configuration:**
```yaml
# Base configuration with inheritance
defaults: &defaults
  model: "meta-llama/Llama-3.1-8B-Instruct"
  max_tokens: 2048
  temperature: 0.1

question_generation:
  <<: *defaults
  specific_config:
    output_type: {"question": "str"}
    
answer_generation:
  <<: *defaults
  specific_config:
    output_type: {"answer": "str"}
```

**Environment Parameterization:**
```yaml
# Environment-aware configuration
lamini:
  base_url: ${LAMINI_BASE_URL:-http://localhost:5001}
  api_key: ${LAMINI_API_KEY:?API key required}
  
model_config:
  default_model: ${DEFAULT_MODEL:-meta-llama/Llama-3.1-8B-Instruct}
  embedding_model: ${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}
```

### 7.2 Template Extension Guidelines

**1. Maintain Configuration Schema Compatibility:**
```python
# Version-aware configuration loading
def load_config_with_migration(config_path, target_version):
    config = yaml.safe_load(open(config_path))
    current_version = config.get('schema_version', 1)
    
    if current_version < target_version:
        config = migrate_config(config, current_version, target_version)
    
    return config
```

**2. Implement Template Validation:**
```python
# Template validation framework
class TemplateValidator:
    def validate_template(self, template_path):
        errors = []
        
        # Check required files
        required_files = [
            "yml-templates/project.yml",
            "yml-templates/experiment.yml", 
            "main_scripts/pipeline.py",
            "main_scripts/init_project.py"
        ]
        
        for file_path in required_files:
            if not os.path.exists(f"{template_path}/{file_path}"):
                errors.append(f"Missing required file: {file_path}")
        
        # Validate YAML schemas
        self.validate_yaml_schemas(template_path, errors)
        
        # Check Python imports
        self.validate_python_imports(template_path, errors)
        
        return errors
```

**3. Standardize SDK Integration:**
```python
# Base template class with standard SDK integration
class BaseTemplate:
    def __init__(self, config_path):
        self.config = self.load_and_validate_config(config_path)
        self.sdk_client = self.create_sdk_client()
        self.experiment_framework = self.setup_experiment_framework()
    
    def create_sdk_client(self):
        """Standard SDK client creation"""
        return Lamini(
            model_name=self.config.get('model', {}).get('default'),
            api_key=self.config['Lamini']['api_key']['value'],
            api_url=self.config['Lamini']['base_url']['value']
        )
    
    def setup_experiment_framework(self):
        """Standard experiment framework setup"""
        return BaseAgenticPipeline(
            generators=self.create_generators(),
            validators=self.create_validators(),
            record_dir=self.config.get('output_dir', './results')
        )
```

---

## 8. Conclusion

The AI Platform SDK architecture demonstrates a sophisticated multi-layered approach that enables rapid development of specialized LLM applications through:

### 8.1 Key Architectural Strengths

**1. Configuration-Driven Development:**
- YAML-based templates enable non-technical customization
- Dynamic code generation reduces boilerplate
- Environment-specific parameter injection
- Schema validation and migration support

**2. Modular Component Architecture:**
- Clear separation between templates, SDK, and platform
- Reusable components across different templates
- Plugin-based extension system
- Standardized integration patterns

**3. Template Lifecycle Management:**
- CLI-driven project initialization
- Version control for configurations
- Project registry and metadata tracking
- Automated setup and validation

### 8.2 Integration Benefits

**Developer Experience:**
- Rapid prototyping with pre-built templates
- Consistent patterns across different domains
- Comprehensive error handling and logging
- Extensive customization without code changes

**Operational Excellence:**
- Environment-aware configuration management
- Automated deployment and scaling
- Comprehensive monitoring and observability
- Version control and rollback capabilities

**Extensibility:**
- Template inheritance and composition
- Plugin architecture for custom components
- SDK extension points for specialized functionality
- Community contribution framework

This architecture provides a robust foundation for building enterprise-grade LLM applications while maintaining the flexibility needed for diverse use cases and rapid iteration.
