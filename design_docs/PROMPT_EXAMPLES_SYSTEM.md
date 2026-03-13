# Prompt Examples System for Task Enrichment

## Overview

This document defines the system for loading, matching, and utilizing example prompts from the `prompt_examples/` directory to enhance prompt generation quality and consistency.

## Directory Structure

```
prompt_examples/
├── question_answering/
│   ├── basic_questions.yaml
│   ├── complex_analysis.yaml
│   └── technical_queries.yaml
├── data_analysis/
│   ├── sales_analysis.yaml
│   ├── financial_metrics.yaml
│   └── performance_review.yaml
├── report_generation/
│   ├── quarterly_reports.yaml
│   ├── executive_summaries.yaml
│   └── department_reports.yaml
├── recommendation/
│   ├── strategic_decisions.yaml
│   ├── process_improvements.yaml
│   └── resource_allocation.yaml
├── comparison/
│   ├── competitive_analysis.yaml
│   └── option_evaluation.yaml
└── general/
    ├── multi_step_tasks.yaml
    └── complex_workflows.yaml
```

## Prompt Example Format

```yaml
# From prompt_examples/data_analysis/sales_analysis.yaml - EXAMPLE
examples:
  - id: "sales_performance_quarterly"
    name: "Quarterly Sales Performance Analysis"
    description: "Comprehensive sales analysis with regional breakdown"
    tags: ["sales", "quarterly", "performance", "regional"]
    complexity: "moderate"
    user_roles: ["manager", "director", "analyst"]
    departments: ["sales", "executive"]
    
    user_input_pattern: ".*sales performance.*quarterly.*"
    
    example_prompt: |
      You are a senior sales analyst tasked with conducting a comprehensive quarterly sales performance analysis.

      **Primary Objective:** Analyze Q3 2024 sales performance and identify key trends, challenges, and opportunities

      **Analysis Framework:**
      1. **Overall Performance Metrics**
         - Total revenue vs. target and prior periods
         - Units sold and average deal size trends
         - Conversion rates across the sales funnel
         - Customer acquisition and retention metrics

      2. **Regional Performance Breakdown**
         - Revenue by region with YoY and QoQ comparisons
         - Top performing and underperforming territories
         - Regional market penetration analysis
         - Territory-specific challenges and opportunities

      3. **Product Line Analysis**
         - Revenue contribution by product category
         - Product performance trends and seasonality
         - New product adoption rates
         - Pricing strategy effectiveness

      **Data Sources Required:**
      - CRM system (Salesforce/HubSpot)
      - Financial reporting system
      - Regional sales databases
      - Customer analytics platform

      **Expected Deliverables:**
      1. Executive Summary (2-3 key findings with actionable insights)
      2. Performance Dashboard (visual KPI overview)
      3. Regional Analysis Report (detailed breakdown by territory)
      4. Trend Analysis (month-over-month and year-over-year)
      5. Strategic Recommendations (3-5 specific action items)

      **Success Criteria:**
      - Identify root causes of performance variations
      - Provide data-driven recommendations with ROI projections
      - Highlight both achievements and areas needing attention
      - Include confidence levels for all projections
      - Present findings appropriate for executive review

      **Additional Context:**
      - Focus on actionable insights rather than just reporting numbers
      - Consider market conditions and competitive landscape
      - Address any data quality issues or limitations
      - Include benchmarking against industry standards where available

    quality_indicators:
      - "clear_objective_statement"
      - "structured_analysis_framework"
      - "specific_data_sources"
      - "defined_deliverables"
      - "measurable_success_criteria"
      
    best_practices_demonstrated:
      - "executive_summary_first"
      - "visual_elements_specified"
      - "confidence_levels_included"
      - "limitations_acknowledged"
      - "actionable_recommendations"

  - id: "sales_team_performance"
    name: "Sales Team Performance Evaluation"
    description: "Individual and team performance analysis"
    tags: ["sales", "team", "performance", "individual"]
    complexity: "complex"
    user_roles: ["manager", "director"]
    departments: ["sales", "hr"]
    
    user_input_pattern: ".*sales team.*performance.*individual.*"
    
    example_prompt: |
      You are an experienced sales manager conducting a comprehensive team performance evaluation.

      **Primary Objective:** Evaluate individual and collective sales team performance to identify top performers, coaching opportunities, and team optimization strategies

      **Performance Evaluation Framework:**
      1. **Individual Performance Metrics**
         - Revenue attainment vs. quota (% of target achieved)
         - Deal velocity and pipeline management
         - Activity metrics (calls, meetings, demos)
         - Win/loss ratios and deal sizes
         - Customer satisfaction scores

      2. **Team Dynamics Assessment**
         - Collaboration effectiveness
         - Knowledge sharing patterns
         - Mentorship and peer support
         - Team morale indicators
         - Cross-selling coordination

      3. **Skill Gap Analysis**
         - Technical product knowledge
         - Sales methodology adherence
         - Communication and presentation skills
         - Objection handling capabilities
         - Territory management effectiveness

      **Data Collection Methods:**
      - CRM performance data analysis
      - Customer feedback surveys
      - Peer evaluation forms
      - Manager observation records
      - Training completion tracking

      **Expected Deliverables:**
      1. Individual Performance Scorecards
      2. Team Performance Dashboard
      3. Skill Gap Assessment Report
      4. Development Plan Recommendations
      5. Resource Allocation Suggestions

      **Success Criteria:**
      - Identify specific coaching opportunities for each team member
      - Recognize and document best practices from top performers
      - Provide actionable development plans
      - Recommend optimal team structure and resource allocation
      - Establish clear performance improvement timelines

      **Evaluation Considerations:**
      - Account for territory differences and market conditions
      - Consider tenure and experience levels
      - Factor in seasonal business variations
      - Include both quantitative metrics and qualitative assessments
      - Ensure fair and unbiased evaluation methodology

    quality_indicators:
      - "comprehensive_evaluation_framework"
      - "multiple_data_sources"
      - "individual_and_team_focus"
      - "development_oriented"
      - "fair_assessment_methodology"

    best_practices_demonstrated:
      - "balanced_scorecard_approach"
      - "coaching_opportunity_identification"
      - "best_practice_documentation"
      - "bias_mitigation"
      - "development_plan_integration"
```

## Prompt Example Loader and Matcher

```python
# From prompt examples system - EXAMPLE
import os
import yaml
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class PromptExample:
    """Individual prompt example with metadata"""
    id: str
    name: str
    description: str
    tags: List[str]
    complexity: str
    user_roles: List[str]
    departments: List[str]
    user_input_pattern: str
    example_prompt: str
    quality_indicators: List[str] = field(default_factory=list)
    best_practices_demonstrated: List[str] = field(default_factory=list)
    relevance_score: float = 0.0

@dataclass
class ExampleMatchResult:
    """Result of example matching with relevance scoring"""
    matched_examples: List[PromptExample]
    match_metadata: Dict[str, Any]
    total_examples_considered: int
    matching_strategy_used: str

class PromptExampleLoader:
    """Loads and manages prompt examples from the prompt_examples directory"""
    
    def __init__(self, examples_dir: str = "prompt_examples"):
        self.examples_dir = Path(examples_dir)
        self.examples_cache: Dict[str, List[PromptExample]] = {}
        self.all_examples: List[PromptExample] = []
        
    def load_all_examples(self) -> Dict[str, List[PromptExample]]:
        """Load all prompt examples from directory structure"""
        
        if not self.examples_dir.exists():
            print(f"Warning: prompt_examples directory not found at {self.examples_dir}")
            return {}
        
        examples_by_intent = {}
        
        # Walk through intent-specific directories
        for intent_dir in self.examples_dir.iterdir():
            if intent_dir.is_dir():
                intent_name = intent_dir.name
                examples_by_intent[intent_name] = []
                
                # Load all YAML files in the intent directory
                for yaml_file in intent_dir.glob("*.yaml"):
                    try:
                        examples = self._load_examples_from_file(yaml_file, intent_name)
                        examples_by_intent[intent_name].extend(examples)
                        self.all_examples.extend(examples)
                    except Exception as e:
                        print(f"Error loading examples from {yaml_file}: {e}")
        
        self.examples_cache = examples_by_intent
        return examples_by_intent
    
    def _load_examples_from_file(self, yaml_file: Path, intent_type: str) -> List[PromptExample]:
        """Load examples from a single YAML file"""
        
        with open(yaml_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        
        examples = []
        for example_data in data.get('examples', []):
            example = PromptExample(
                id=example_data.get('id', f"{intent_type}_{len(examples)}"),
                name=example_data.get('name', 'Unnamed Example'),
                description=example_data.get('description', ''),
                tags=example_data.get('tags', []),
                complexity=example_data.get('complexity', 'moderate'),
                user_roles=example_data.get('user_roles', []),
                departments=example_data.get('departments', []),
                user_input_pattern=example_data.get('user_input_pattern', ''),
                example_prompt=example_data.get('example_prompt', ''),
                quality_indicators=example_data.get('quality_indicators', []),
                best_practices_demonstrated=example_data.get('best_practices_demonstrated', [])
            )
            examples.append(example)
        
        return examples
    
    def get_examples_by_intent(self, intent_type: str) -> List[PromptExample]:
        """Get all examples for a specific intent type"""
        return self.examples_cache.get(intent_type, [])
    
    def get_all_examples(self) -> List[PromptExample]:
        """Get all loaded examples"""
        return self.all_examples

class PromptExampleMatcher:
    """Matches user requests to relevant prompt examples"""
    
    def __init__(self, examples_by_intent: Dict[str, List[PromptExample]]):
        self.examples_by_intent = examples_by_intent
        self.all_examples = []
        
        # Flatten all examples for cross-intent matching
        for examples_list in examples_by_intent.values():
            self.all_examples.extend(examples_list)
    
    def find_relevant_examples(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext',
        max_examples: int = 3
    ) -> ExampleMatchResult:
        """Find the most relevant prompt examples for the given context"""
        
        # Strategy 1: Intent-specific matching
        intent_examples = self._match_by_intent(task_analysis.intent_type.value, user_input, task_analysis, user_context)
        
        # Strategy 2: Cross-intent matching for complex cases
        cross_intent_examples = self._match_across_intents(user_input, task_analysis, user_context)
        
        # Strategy 3: Pattern-based matching
        pattern_examples = self._match_by_patterns(user_input, task_analysis, user_context)
        
        # Combine and rank all matches
        all_matches = intent_examples + cross_intent_examples + pattern_examples
        
        # Remove duplicates and rank by relevance
        unique_matches = self._deduplicate_and_rank(all_matches, user_input, task_analysis, user_context)
        
        # Select top matches
        top_matches = unique_matches[:max_examples]
        
        return ExampleMatchResult(
            matched_examples=top_matches,
            match_metadata={
                'intent_matches': len(intent_examples),
                'cross_intent_matches': len(cross_intent_examples),
                'pattern_matches': len(pattern_examples),
                'total_candidates': len(all_matches),
                'deduplication_applied': len(all_matches) - len(unique_matches)
            },
            total_examples_considered=len(self.all_examples),
            matching_strategy_used="multi_strategy_hybrid"
        )
    
    def _match_by_intent(
        self,
        intent_type: str,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[PromptExample]:
        """Match examples within the same intent type"""
        
        intent_examples = self.examples_by_intent.get(intent_type, [])
        matched_examples = []
        
        for example in intent_examples:
            relevance_score = self._calculate_relevance_score(
                example, user_input, task_analysis, user_context
            )
            
            if relevance_score > 0.3:  # Minimum relevance threshold
                example.relevance_score = relevance_score
                matched_examples.append(example)
        
        return matched_examples
    
    def _match_across_intents(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[PromptExample]:
        """Match examples across different intent types for complex requests"""
        
        # For complex tasks, look at examples from related intents
        related_intents = self._get_related_intents(task_analysis.intent_type.value, task_analysis.complexity.value)
        
        cross_matches = []
        for intent in related_intents:
            intent_examples = self.examples_by_intent.get(intent, [])
            
            for example in intent_examples:
                relevance_score = self._calculate_relevance_score(
                    example, user_input, task_analysis, user_context
                )
                
                # Lower threshold for cross-intent matching
                if relevance_score > 0.2:
                    example.relevance_score = relevance_score * 0.8  # Slight penalty for cross-intent
                    cross_matches.append(example)
        
        return cross_matches
    
    def _match_by_patterns(
        self,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[PromptExample]:
        """Match examples using regex patterns"""
        
        pattern_matches = []
        user_input_lower = user_input.lower()
        
        for example in self.all_examples:
            if example.user_input_pattern:
                try:
                    if re.search(example.user_input_pattern, user_input_lower, re.IGNORECASE):
                        relevance_score = self._calculate_relevance_score(
                            example, user_input, task_analysis, user_context
                        )
                        example.relevance_score = relevance_score
                        pattern_matches.append(example)
                except re.error:
                    # Skip invalid regex patterns
                    continue
        
        return pattern_matches
    
    def _calculate_relevance_score(
        self,
        example: PromptExample,
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> float:
        """Calculate relevance score for an example"""
        
        score = 0.0
        
        # Factor 1: Department match (30%)
        if user_context.department.lower() in [dept.lower() for dept in example.departments]:
            score += 0.3
        
        # Factor 2: User role match (20%)
        if user_context.user_role.lower() in [role.lower() for role in example.user_roles]:
            score += 0.2
        
        # Factor 3: Complexity alignment (20%)
        complexity_alignment = self._calculate_complexity_alignment(
            task_analysis.complexity.value, example.complexity
        )
        score += complexity_alignment * 0.2
        
        # Factor 4: Tag/keyword overlap (20%)
        keyword_overlap = self._calculate_keyword_overlap(user_input, example)
        score += keyword_overlap * 0.2
        
        # Factor 5: Entity mention overlap (10%)
        entity_overlap = self._calculate_entity_overlap(task_analysis.entities_mentioned, example)
        score += entity_overlap * 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_complexity_alignment(self, task_complexity: str, example_complexity: str) -> float:
        """Calculate alignment between task and example complexity"""
        
        complexity_levels = {
            'simple': 1,
            'moderate': 2,
            'complex': 3,
            'expert': 4
        }
        
        task_level = complexity_levels.get(task_complexity, 2)
        example_level = complexity_levels.get(example_complexity, 2)
        
        # Perfect match gets 1.0, adjacent levels get 0.7, etc.
        difference = abs(task_level - example_level)
        if difference == 0:
            return 1.0
        elif difference == 1:
            return 0.7
        elif difference == 2:
            return 0.4
        else:
            return 0.1
    
    def _calculate_keyword_overlap(self, user_input: str, example: PromptExample) -> float:
        """Calculate keyword overlap between user input and example"""
        
        user_words = set(user_input.lower().split())
        
        # Check overlap with tags
        tag_words = set()
        for tag in example.tags:
            tag_words.update(tag.lower().split())
        
        # Check overlap with description
        description_words = set(example.description.lower().split())
        
        # Check overlap with example name
        name_words = set(example.name.lower().split())
        
        # Combine all example-related words
        example_words = tag_words.union(description_words).union(name_words)
        
        if not user_words or not example_words:
            return 0.0
        
        overlap = len(user_words.intersection(example_words))
        return overlap / len(user_words.union(example_words))
    
    def _calculate_entity_overlap(self, task_entities: List[str], example: PromptExample) -> float:
        """Calculate overlap between task entities and example content"""
        
        if not task_entities:
            return 0.0
        
        example_text = f"{example.description} {' '.join(example.tags)} {example.example_prompt}".lower()
        
        entity_mentions = 0
        for entity in task_entities:
            if entity.lower() in example_text:
                entity_mentions += 1
        
        return entity_mentions / len(task_entities)
    
    def _get_related_intents(self, primary_intent: str, complexity: str) -> List[str]:
        """Get related intents for cross-intent matching"""
        
        intent_relationships = {
            'question_answering': ['data_analysis', 'report_generation'],
            'data_analysis': ['question_answering', 'report_generation', 'recommendation'],
            'report_generation': ['data_analysis', 'summarization', 'recommendation'],
            'recommendation': ['data_analysis', 'comparison', 'report_generation'],
            'comparison': ['recommendation', 'data_analysis'],
            'summarization': ['report_generation', 'question_answering']
        }
        
        related = intent_relationships.get(primary_intent, [])
        
        # For complex tasks, include more cross-intent options
        if complexity in ['complex', 'expert']:
            if 'general' not in related:
                related.append('general')
        
        return related
    
    def _deduplicate_and_rank(
        self,
        examples: List[PromptExample],
        user_input: str,
        task_analysis: 'TaskAnalysis',
        user_context: 'UserContext'
    ) -> List[PromptExample]:
        """Remove duplicates and rank by relevance score"""
        
        # Remove duplicates by ID
        seen_ids = set()
        unique_examples = []
        
        for example in examples:
            if example.id not in seen_ids:
                unique_examples.append(example)
                seen_ids.add(example.id)
        
        # Sort by relevance score (descending)
        unique_examples.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return unique_examples

# Enhanced PromptGenerator methods

def _load_prompt_examples(self) -> Dict[str, List[PromptExample]]:
    """Load prompt examples from the prompt_examples directory"""
    
    examples_dir = self.config.get('examples_directory', 'prompt_examples')
    loader = PromptExampleLoader(examples_dir)
    
    try:
        examples_by_intent = loader.load_all_examples()
        
        total_examples = sum(len(examples) for examples in examples_by_intent.values())
        self.logger.info(
            f"Loaded {total_examples} prompt examples from {len(examples_by_intent)} intent categories",
            operation="examples_loading",
            metadata={
                "examples_by_intent": {intent: len(examples) for intent, examples in examples_by_intent.items()},
                "total_examples": total_examples
            }
        )
        
        return examples_by_intent
        
    except Exception as e:
        self.logger.error(f"Failed to load prompt examples: {e}")
        return {}

def _prepare_template_variables(
    self,
    user_input: str,
    task_analysis: 'TaskAnalysis',
    enriched_context: Dict[str, Any],
    user_context: 'UserContext',
    rag_context: Optional['RAGRetrievalResult'] = None
) -> Dict[str, str]:
    """Enhanced template variable preparation with RAG context"""
    
    # Get base variables (existing logic)
    variables = self._get_base_template_variables(
        user_input, task_analysis, enriched_context, user_context
    )
    
    # Add RAG context if available
    if rag_context and rag_context.relevant_chunks:
        variables.update({
            'rag_context_summary': rag_context.context_summary,
            'relevant_information': self._format_rag_context_for_prompt(rag_context),
            'knowledge_base_confidence': f"{rag_context.confidence_score:.1%}",
            'sources_consulted': ', '.join(rag_context.sources_used)
        })
    else:
        variables.update({
            'rag_context_summary': 'No specific context found in knowledge base',
            'relevant_information': 'Limited context available from knowledge base',
            'knowledge_base_confidence': '0%',
            'sources_consulted': 'None'
        })
    
    return variables

async def _enhance_with_examples_and_best_practices(
    self,
    base_prompt: str,
    relevant_examples: ExampleMatchResult,
    task_analysis: 'TaskAnalysis',
    user_context: 'UserContext'
) -> str:
    """Enhanced prompt enhancement using example prompts and best practices"""
    
    if not relevant_examples.matched_examples:
        # Fall back to basic best practices enhancement
        return await self._enhance_with_best_practices_only(base_prompt, task_analysis, user_context)
    
    # Prepare example context for enhancement
    example_context = self._prepare_example_context(relevant_examples)
    
    enhancement_prompt = f"""
    Enhance the following prompt by incorporating insights from these high-quality example prompts.
    Apply the demonstrated best practices while maintaining the original intent and context.

    **Original Prompt to Enhance:**
    {base_prompt}

    **Reference Examples:**
    {example_context}

    **Enhancement Guidelines:**
    1. **Structure**: Adopt the clear sectioning and organization from examples
    2. **Specificity**: Include specific deliverables and success criteria like the examples
    3. **Context**: Add relevant business context and constraints
    4. **Best Practices**: Apply the quality indicators demonstrated in examples:
       {self._format_quality_indicators(relevant_examples)}
    5. **Consistency**: Maintain consistency with proven patterns from examples

    **Task Context:**
    - Intent: {task_analysis.intent_type.value}
    - Complexity: {task_analysis.complexity.value}
    - User Role: {user_context.user_role}
    - Department: {user_context.department}

    Provide the enhanced prompt that incorporates these improvements while preserving the original objective.
    """
    
    try:
        response = await self.client.chat.completions.create(
            model=self.config.get('enhancement_model', 'meta-llama/Llama-3.1-70B-Instruct'),
            messages=[
                {"role": "system", "content": "You are an expert at enhancing prompts using proven examples and best practices. Create clear, actionable prompts that maximize AI agent success."},
                {"role": "user", "content": enhancement_prompt}
            ],
            temperature=0.3,
            max_tokens=2500
        )
        
        enhanced = response.choices[0].message.content.strip()
        
        # Validate enhancement
        if len(enhanced) > len(base_prompt) * 0.8 and len(enhanced) < len(base_prompt) * 3:
            return enhanced
        else:
            return await self._enhance_with_best_practices_only(base_prompt, task_analysis, user_context)
            
    except Exception as e:
        self.logger.warning(f"Example-based enhancement failed: {e}")
        return await self._enhance_with_best_practices_only(base_prompt, task_analysis, user_context)

def _prepare_example_context(self, relevant_examples: ExampleMatchResult) -> str:
    """Prepare example context for enhancement prompt"""
    
    example_texts = []
    
    for i, example in enumerate(relevant_examples.matched_examples, 1):
        example_text = f"""
        **Example {i}: {example.name}** (Relevance: {example.relevance_score:.1%})
        Description: {example.description}
        Complexity: {example.complexity}
        
        Key Structure Elements:
        {self._extract_structure_elements(example.example_prompt)}
        
        Best Practices Demonstrated:
        - {chr(10).join([f"  • {practice.replace('_', ' ').title()}" for practice in example.best_practices_demonstrated])}
        """
        example_texts.append(example_text)
    
    return "\n".join(example_texts)

def _extract_structure_elements(self, example_prompt: str) -> str:
    """Extract key structural elements from example prompt"""
    
    # Look for common structural patterns
    structure_elements = []
    
    # Find section headers (lines with **text** or ###)
    lines = example_prompt.split('\n')
    for line in lines:
        stripped = line.strip()
        if (stripped.startswith('**') and stripped.endswith('**')) or stripped.startswith('###'):
            structure_elements.append(f"  • {stripped}")
        elif stripped.startswith('- ') or stripped.startswith('1. ') or stripped.startswith('2. '):
            # Don't include all list items, just note that lists are used
            if "Lists used for organization" not in structure_elements:
                structure_elements.append("  • Lists used for organization")
    
    return '\n'.join(structure_elements[:5])  # Limit to top 5 elements

def _format_quality_indicators(self, relevant_examples: ExampleMatchResult) -> str:
    """Format quality indicators from examples"""
    
    all_indicators = set()
    for example in relevant_examples.matched_examples:
        all_indicators.update(example.quality_indicators)
        all_indicators.update(example.best_practices_demonstrated)
    
    formatted_indicators = [f"  • {indicator.replace('_', ' ').title()}" for indicator in sorted(all_indicators)]
    return '\n'.join(formatted_indicators[:8])  # Limit to top 8 indicators
```

## Example Directory Setup Script

```python
# From example directory setup - EXAMPLE
import os
import yaml
from pathlib import Path

def create_example_directory_structure():
    """Create the prompt_examples directory structure with sample files"""
    
    base_dir = Path("prompt_examples")
    
    # Define directory structure
    directories = [
        "question_answering",
        "data_analysis", 
        "report_generation",
        "recommendation",
        "comparison",
        "general"
    ]
    
    # Create directories
    for directory in directories:
        (base_dir / directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {base_dir / directory}")
    
    # Create sample files
    sample_files = {
        "data_analysis/sales_analysis.yaml": create_sales_analysis_sample(),
        "question_answering/basic_questions.yaml": create_basic_questions_sample(),
        "report_generation/quarterly_reports.yaml": create_quarterly_reports_sample()
    }
    
    for file_path, content in sample_files.items():
        full_path = base_dir / file_path
        with open(full_path, 'w', encoding='utf-8') as f:
            yaml.dump(content, f, default_flow_style=False, indent=2, allow_unicode=True)
        print(f"Created sample file: {full_path}")

def create_sales_analysis_sample():
    """Create sample sales analysis examples"""
    return {
        "examples": [
            {
                "id": "sales_performance_quarterly",
                "name": "Quarterly Sales Performance Analysis",
                "description": "Comprehensive sales analysis with regional breakdown",
                "tags": ["sales", "quarterly", "performance", "regional"],
                "complexity": "moderate",
                "user_roles": ["manager", "director", "analyst"],
                "departments": ["sales", "executive"],
                "user_input_pattern": ".*sales performance.*quarterly.*",
                "example_prompt": """You are a senior sales analyst tasked with conducting a comprehensive quarterly sales performance analysis.

**Primary Objective:** Analyze Q3 2024 sales performance and identify key trends, challenges, and opportunities

**Analysis Framework:**
1. **Overall Performance Metrics**
   - Total revenue vs. target and prior periods
   - Units sold and average deal size trends
   - Conversion rates across the sales funnel
   - Customer acquisition and retention metrics

2. **Regional Performance Breakdown**
   - Revenue by region with YoY and QoQ comparisons
   - Top performing and underperforming territories
   - Regional market penetration analysis
   - Territory-specific challenges and opportunities

**Expected Deliverables:**
1. Executive Summary (2-3 key findings with actionable insights)
2. Performance Dashboard (visual KPI overview)
3. Regional Analysis Report (detailed breakdown by territory)
4. Strategic Recommendations (3-5 specific action items)

**Success Criteria:**
- Identify root causes of performance variations
- Provide data-driven recommendations with ROI projections
- Include confidence levels for all projections
- Present findings appropriate for executive review""",
                "quality_indicators": [
                    "clear_objective_statement",
                    "structured_analysis_framework", 
                    "specific_deliverables",
                    "measurable_success_criteria"
                ],
                "best_practices_demonstrated": [
                    "executive_summary_first",
                    "visual_elements_specified",
                    "confidence_levels_included",
                    "actionable_recommendations"
                ]
            }
        ]
    }

if __name__ == "__main__":
    create_example_directory_structure()
    print("\nPrompt examples directory structure created successfully!")
    print("Add your own example prompts to the YAML files in each intent directory.")
```

This comprehensive prompt examples system provides:

1. **Structured Example Storage**: Organized by intent type with rich metadata
2. **Intelligent Matching**: Multi-strategy matching based on intent, patterns, roles, and departments
3. **Quality Enhancement**: Uses proven examples to improve prompt generation
4. **Best Practice Integration**: Automatically applies demonstrated best practices
5. **Scalable Architecture**: Easy to add new examples and categories
6. **Performance Tracking**: Relevance scoring and match analytics

The system ensures that your enrichment process leverages proven, high-quality prompt patterns while maintaining flexibility for new use cases.
