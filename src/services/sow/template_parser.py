"""
SOW Template Parser

Handles parsing and generation of SOW documents from templates.
Supports BOTH template formats:
1. Original sow-eliza format: [[question]]{{TAG}} and {{TAG}} placeholders
2. Eliza SOW format: green/yellow highlighting
"""
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from copy import deepcopy
import re
import logging
import tempfile

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt, Inches

from .mermaid_renderer import MermaidRenderer

logger = logging.getLogger(__name__)

# Patterns for original sow-eliza format
QUESTION_TAG_PATTERN = re.compile(r"\[\[([^\]]+)\]\]\s*\{\{([A-Z0-9_]+)\}\}")
TAG_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


@dataclass
class TemplateField:
    """A field in the SOW template."""
    tag: str  # Unique identifier derived from instruction
    instruction: str  # The green instruction text
    sample_answer: str  # The yellow sample text
    instruction_para_idx: int  # Paragraph with green instruction
    sample_para_indices: List[int]  # Paragraphs with yellow samples
    is_table: bool = False  # Whether this field is a table
    table_index: Optional[int] = None  # Index of the table in doc.tables
    table_structure: Optional[Dict[str, Any]] = None  # Table headers and sample rows
    is_diagram: bool = False  # Whether this field is a diagram (mermaid)
    
    @property
    def question(self) -> str:
        """Return the instruction as a question for extraction."""
        return self.instruction
    
    @property
    def paragraph_indices(self) -> List[int]:
        return [self.instruction_para_idx] + self.sample_para_indices


class TemplateParser:
    """Parser for SOW templates."""
    
    # Mapping from instruction keywords to field tags
    INSTRUCTION_TO_TAG = {
        "executive summary": "EXECUTIVE_SUMMARY",
        "problem statement": "EXECUTIVE_SUMMARY",
        "goals/outcomes": "BUSINESS_OUTCOMES",
        "business outcomes": "BUSINESS_OUTCOMES",
        "success criteria": "SUCCESS_CRITERIA",
        "technical project plan": "PROJECT_PLAN",
        "project plan": "PROJECT_PLAN",
        "scope of work": "SCOPE_OF_WORK",
        "detailed scope": "DETAILED_SCOPE",
        "assumptions": "ASSUMPTIONS",
        "risks": "RISKS",
        "timeline": "TIMELINE",
        "pricing": "PRICING",
        "team": "TEAM",
        "deliverables": "DELIVERABLES",
        "total number of hours": "TOTAL_HOURS",
        "table with the following columns: role": "PRICING_TABLE",
        "role, hourly rate": "PRICING_TABLE",
        "architecture diagram": "ARCHITECTURE_DIAGRAM",
        "technical diagram": "ARCHITECTURE_DIAGRAM",
        "system diagram": "ARCHITECTURE_DIAGRAM",
        "solution architecture": "ARCHITECTURE_DIAGRAM",
    }
    
    def __init__(self):
        self.mermaid_renderer = MermaidRenderer()
        self.template_format = None  # 'tag_based' or 'highlight_based'
    
    def parse_template(self, template_path: Path) -> Tuple[Document, List[TemplateField]]:
        """
        Parse the SOW template format.
        
        Supports BOTH formats:
        1. Tag-based: [[question]]{{TAG}} and {{TAG}} (original sow-eliza)
        2. Highlight-based: green instructions, yellow samples
        
        Returns:
            (Document, List[TemplateField]) - The document and parsed fields
        """
        doc = Document(template_path)
        
        # Detect which format the template uses
        full_text = self._get_full_document_text(doc)
        has_tag_format = bool(TAG_PATTERN.search(full_text))
        has_highlight_format = self._has_highlight_format(doc)
        
        if has_tag_format:
            self.template_format = 'tag_based'
            logger.info("Detected tag-based template format ({{TAG}})")
            return doc, self._parse_tag_based_template(doc)
        elif has_highlight_format:
            self.template_format = 'highlight_based'
            logger.info("Detected highlight-based template format (green/yellow)")
            return doc, self._parse_highlight_based_template(doc)
        else:
            logger.warning("No recognized template format found, trying tag-based")
            self.template_format = 'tag_based'
            return doc, self._parse_tag_based_template(doc)
    
    def _get_full_document_text(self, doc: Document) -> str:
        """Get all text from the document."""
        text_parts = []
        for para in doc.paragraphs:
            text_parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        text_parts.append(para.text)
        return "\n".join(text_parts)
    
    def _has_highlight_format(self, doc: Document) -> bool:
        """Check if document uses highlight-based format."""
        for para in doc.paragraphs:
            for run in para.runs:
                if run.font.highlight_color == WD_COLOR_INDEX.BRIGHT_GREEN:
                    return True
        return False
    
    def _parse_tag_based_template(self, doc: Document) -> List[TemplateField]:
        """Parse template using {{TAG}} format (original sow-eliza style)."""
        found: Dict[str, TemplateField] = {}
        next_id = 0
        
        def process_text(text: str, para_idx: int) -> None:
            nonlocal next_id
            
            # Find [[question]]{{TAG}} patterns
            for question, tag in QUESTION_TAG_PATTERN.findall(text):
                if tag not in found:
                    is_diagram = self._is_diagram_instruction(question) or tag == "ARCHITECTURE_DIAGRAM"
                    is_table = self._is_table_instruction(question) or tag.endswith("_TABLE")
                    
                    found[tag] = TemplateField(
                        tag=tag,
                        instruction=question.strip(),
                        sample_answer="",
                        instruction_para_idx=para_idx,
                        sample_para_indices=[],
                        is_table=is_table,
                        is_diagram=is_diagram,
                    )
                    next_id += 1
            
            # Find standalone {{TAG}} patterns
            for tag in TAG_PATTERN.findall(text):
                if tag not in found:
                    question = self._infer_question(tag)
                    is_diagram = tag == "ARCHITECTURE_DIAGRAM"
                    is_table = tag.endswith("_TABLE") or tag == "PROJECT_PLAN"
                    
                    found[tag] = TemplateField(
                        tag=tag,
                        instruction=question,
                        sample_answer="",
                        instruction_para_idx=para_idx,
                        sample_para_indices=[],
                        is_table=is_table,
                        is_diagram=is_diagram,
                    )
                    next_id += 1
        
        # Process paragraphs
        for i, para in enumerate(doc.paragraphs):
            if para.text:
                process_text(para.text, i)
        
        # Process tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if para.text:
                            process_text(para.text, 0)
        
        logger.info(f"Found {len(found)} fields in tag-based template")
        return list(found.values())
    
    def _infer_question(self, tag: str) -> str:
        """Infer a question from a tag name."""
        # Check predefined mappings first
        tag_upper = tag.upper()
        for key, mapped_tag in self.INSTRUCTION_TO_TAG.items():
            if mapped_tag == tag_upper:
                return f"What is the {key}?"
        
        # Fallback: convert tag to readable question
        words = tag.lower().replace("_", " ")
        return f"What is the {words}?"
    
    def _parse_highlight_based_template(self, doc: Document) -> List[TemplateField]:
        """Parse template using green/yellow highlight format."""
        fields = []
        assigned_tables = set()
        
        i = 0
        while i < len(doc.paragraphs):
            para = doc.paragraphs[i]
            
            # Check if this paragraph has green highlighted text (instruction)
            green_text = ""
            has_green = False
            for run in para.runs:
                if run.font.highlight_color == WD_COLOR_INDEX.BRIGHT_GREEN:
                    green_text += run.text
                    has_green = True
            
            if has_green and green_text.strip().startswith('['):
                # Found an instruction - extract it
                instruction = green_text.strip().strip('[]')
                tag = self._get_tag_from_instruction(instruction)
                
                # Check if this is a table instruction
                if self._is_table_instruction(instruction):
                    # Find the next table
                    table_idx = self._find_next_table(doc, i, assigned_tables)
                    if table_idx is not None:
                        assigned_tables.add(table_idx)
                        table_structure = self._parse_table_structure(doc.tables[table_idx])
                        
                        field = TemplateField(
                            tag=tag,
                            instruction=instruction,
                            sample_answer="",
                            instruction_para_idx=i,
                            sample_para_indices=[],
                            is_table=True,
                            table_index=table_idx,
                            table_structure=table_structure,
                        )
                        fields.append(field)
                        logger.info(f"Found table field: {tag}")
                    i += 1
                    continue
                
                # Check if this is a diagram instruction
                if self._is_diagram_instruction(instruction):
                    field = TemplateField(
                        tag=tag,
                        instruction=instruction,
                        sample_answer="",
                        instruction_para_idx=i,
                        sample_para_indices=[],
                        is_diagram=True,
                    )
                    fields.append(field)
                    logger.info(f"Found diagram field: {tag}")
                    i += 1
                    continue
                
                # Look for yellow sample text in following paragraphs
                sample_paragraphs = []
                sample_text_parts = []
                j = i + 1
                
                while j < len(doc.paragraphs):
                    next_para = doc.paragraphs[j]
                    has_yellow = False
                    
                    for run in next_para.runs:
                        if run.font.highlight_color == WD_COLOR_INDEX.YELLOW:
                            has_yellow = True
                            break
                    
                    if has_yellow:
                        sample_paragraphs.append(j)
                        sample_text_parts.append(next_para.text.strip())
                        j += 1
                    else:
                        # Check if next para is another green instruction
                        next_green = False
                        for run in next_para.runs:
                            if run.font.highlight_color == WD_COLOR_INDEX.BRIGHT_GREEN:
                                next_green = True
                                break
                        if next_green or (next_para.text.strip() and not has_yellow):
                            break
                        j += 1
                
                field = TemplateField(
                    tag=tag,
                    instruction=instruction,
                    sample_answer="\n".join(sample_text_parts),
                    instruction_para_idx=i,
                    sample_para_indices=sample_paragraphs,
                )
                fields.append(field)
                logger.info(f"Found field: {tag}")
                
                i = j
            else:
                i += 1
        
        return fields
    
    def _get_tag_from_instruction(self, instruction: str) -> str:
        """Generate a tag from the instruction text."""
        instruction_lower = instruction.lower()
        for key, tag in self.INSTRUCTION_TO_TAG.items():
            if key in instruction_lower:
                return tag
        # Fallback: generate from first few words
        words = re.findall(r'\w+', instruction_lower)[:3]
        return "_".join(words).upper()
    
    def _is_table_instruction(self, instruction: str) -> bool:
        """Check if the instruction is for a table field."""
        instruction_lower = instruction.lower()
        return "table" in instruction_lower and ("column" in instruction_lower or "row" in instruction_lower)
    
    def _is_diagram_instruction(self, instruction: str) -> bool:
        """Check if the instruction is for a diagram field."""
        instruction_lower = instruction.lower()
        diagram_keywords = ["architecture diagram", "technical diagram", "system diagram", "solution architecture"]
        return any(kw in instruction_lower for kw in diagram_keywords)
    
    def _format_value_for_document(self, tag: str, value: Any) -> str:
        """Format a value for document output - convert structured data to readable text."""
        if value is None:
            return ""
        
        if isinstance(value, str):
            return value
        
        # Handle PROJECT_PLAN specifically
        if tag == "PROJECT_PLAN" and isinstance(value, dict):
            parts = []
            
            # Technical approach
            if value.get("technical_approach"):
                parts.append(f"Technical Approach: {value['technical_approach']}")
                parts.append("")
            
            # Phases
            phases = value.get("phases", [])
            if phases:
                for i, phase in enumerate(phases, 1):
                    name = phase.get("name", f"Phase {i}")
                    desc = phase.get("description", "")
                    duration = phase.get("duration", "")
                    deliverables = phase.get("deliverables", [])
                    
                    parts.append(f"{name}")
                    if desc:
                        parts.append(f"  {desc}")
                    if duration:
                        parts.append(f"  Duration: {duration}")
                    if deliverables:
                        parts.append(f"  Deliverables: {', '.join(deliverables)}")
                    parts.append("")
            
            # Summary
            if value.get("summary"):
                parts.append(f"Summary: {value['summary']}")
            
            return "\n".join(parts)
        
        # Handle lists (e.g., bullet points, table data)
        if isinstance(value, list):
            if not value:
                return ""
            
            # List of dicts (table-like data)
            if isinstance(value[0], dict):
                parts = []
                for item in value:
                    # Format each dict as a line
                    item_parts = [f"{k}: {v}" for k, v in item.items() if v]
                    parts.append(" | ".join(item_parts))
                return "\n".join(parts)
            else:
                # Simple list - format as bullet points
                return "\n".join(f"• {item}" for item in value)
        
        # Handle dicts
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                if v:
                    parts.append(f"{k}: {v}")
            return "\n".join(parts)
        
        return str(value)
    
    def _add_formatted_text(self, para, text: str):
        """Add text to a paragraph, handling HEADING: prefixes for bold formatting.
        
        For multi-line text with HEADING: prefix, creates multiple paragraphs
        with appropriate formatting (bold for headings).
        """
        if not text:
            return
        
        lines = text.split('\n')
        first_line = True
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines between sections
            if not line:
                continue
            
            # Determine if this line is a heading
            is_heading = line.startswith('HEADING:')
            if is_heading:
                line = line[8:]  # Remove "HEADING:" prefix
            
            if first_line:
                # Use the current paragraph for the first line
                run = para.add_run(line)
                if is_heading:
                    run.font.bold = True
                run.font.highlight_color = None
                first_line = False
            else:
                # For subsequent lines, we add them with a line break
                # (python-docx doesn't easily support adding paragraphs inline)
                run = para.add_run('\n' + line)
                if is_heading:
                    run.font.bold = True
                run.font.highlight_color = None
    
    def _find_next_table(self, doc: Document, start_para_idx: int, assigned: set) -> Optional[int]:
        """Find the index of the next unassigned table after a paragraph."""
        para_element = doc.paragraphs[start_para_idx]._element
        
        for sibling in para_element.itersiblings():
            if sibling.tag.endswith('tbl'):
                for idx, table in enumerate(doc.tables):
                    if table._tbl is sibling and idx not in assigned:
                        return idx
                break
        return None
    
    def _parse_table_structure(self, table) -> Dict[str, Any]:
        """Parse a table's structure including headers and sample data."""
        if not table.rows:
            return {"headers": [], "sample_rows": [], "row_count": 0}
        
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        sample_rows = []
        
        for row_idx, row in enumerate(table.rows[1:], start=1):
            row_data = {}
            for col_idx, cell in enumerate(row.cells):
                header = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                row_data[header] = cell.text.strip()
            sample_rows.append(row_data)
        
        return {
            "headers": headers,
            "sample_rows": sample_rows,
            "row_count": len(table.rows) - 1,
        }
    
    def generate_document(
        self,
        template_path: Path,
        answers: Dict[str, Any],
        output_path: Path,
    ) -> Path:
        """
        Generate a SOW document by filling in the template with answers.
        
        Supports both tag-based ({{TAG}}) and highlight-based formats.
        
        Args:
            template_path: Path to the template document
            answers: Dict mapping field tags to answer values
            output_path: Where to save the generated document
        """
        doc, fields = self.parse_template(template_path)
        
        logger.info(f"Generating SOW document with {len(answers)} answers (format: {self.template_format})")
        
        # Use appropriate generation method based on template format
        if self.template_format == 'tag_based':
            return self._generate_tag_based_document(doc, answers, output_path)
        else:
            return self._generate_highlight_based_document(doc, fields, answers, output_path)
    
    def _generate_tag_based_document(
        self,
        doc: Document,
        answers: Dict[str, Any],
        output_path: Path,
    ) -> Path:
        """Generate document using {{TAG}} replacement (original sow-eliza style)."""
        
        # Build replacements dict
        replacements: Dict[str, str] = {}
        for tag, answer in answers.items():
            # Prefer value_rendered which is pre-formatted by SowService
            if hasattr(answer, 'value_rendered') and answer.value_rendered:
                replacements[tag] = answer.value_rendered
            elif hasattr(answer, 'value') and answer.value:
                val = answer.value
                # Fallback: format structured data for documents
                replacements[tag] = self._format_value_for_document(tag, val)
            elif isinstance(answer, str):
                replacements[tag] = answer
        
        def replace_text(text: str) -> str:
            """Replace [[question]] and {{TAG}} patterns."""
            # Remove [[question]] patterns
            text = re.sub(r"\[\[[^\]]+\]\]", "", text)
            # Replace {{TAG}} with values
            for tag, value in replacements.items():
                text = text.replace(f"{{{{{tag}}}}}", value)
            return text
        
        def process_paragraph(para) -> None:
            if not para.runs:
                para.text = replace_text(para.text)
                return
            
            combined = "".join(run.text for run in para.runs)
            updated = replace_text(combined)
            
            if updated == combined:
                return
            
            para.runs[0].text = updated
            for run in para.runs[1:]:
                run.text = ""
        
        # Process all paragraphs
        for para in doc.paragraphs:
            process_paragraph(para)
        
        # Process tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        process_paragraph(para)
        
        # Handle architecture diagram - insert after PROJECT_PLAN if possible
        arch_answer = answers.get("ARCHITECTURE_DIAGRAM")
        if arch_answer:
            mermaid_code = arch_answer.value if hasattr(arch_answer, 'value') else str(arch_answer)
            if mermaid_code and mermaid_code.strip():
                # Find the paragraph that had PROJECT_PLAN content
                project_plan_value = replacements.get("PROJECT_PLAN", "")
                insert_idx = None
                if project_plan_value:
                    # Look for the paragraph with PROJECT_PLAN content (check first line)
                    first_line = project_plan_value.split('\n')[0][:50] if project_plan_value else ""
                    for i, para in enumerate(doc.paragraphs):
                        if first_line and first_line in para.text:
                            insert_idx = i
                            break
                
                if insert_idx is not None:
                    self._insert_diagram_after_paragraph(doc, insert_idx, mermaid_code, output_path)
                else:
                    # Fallback: append at end
                    self._append_diagram_section(doc, mermaid_code, output_path)
        
        # Save document
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        logger.info(f"Saved SOW document (tag-based) to: {output_path}")
        
        return output_path
    
    def _generate_highlight_based_document(
        self,
        doc: Document,
        fields: List[TemplateField],
        answers: Dict[str, Any],
        output_path: Path,
    ) -> Path:
        """Generate document using highlight-based format."""
        
        logger.info(f"Generating SOW document with {len(answers)} answers")
        
        # Build a map of field tag to answer for quick lookup
        answer_map = {}
        for field in fields:
            answer = answers.get(field.tag)
            if answer:
                # Prefer value_rendered which is pre-formatted by SowService
                if hasattr(answer, 'value_rendered') and answer.value_rendered:
                    answer_map[field.tag] = answer.value_rendered
                elif hasattr(answer, 'value') and answer.value:
                    val = answer.value
                    # Fallback: format structured data for documents
                    answer_map[field.tag] = self._format_value_for_document(field.tag, val)
                elif isinstance(answer, str):
                    answer_map[field.tag] = answer
        
        # Process paragraphs - clear green instructions, replace yellow samples
        for para in doc.paragraphs:
            has_green = False
            has_yellow = False
            green_text = ""
            
            for run in para.runs:
                if run.font.highlight_color == WD_COLOR_INDEX.BRIGHT_GREEN:
                    has_green = True
                    green_text += run.text
                elif run.font.highlight_color == WD_COLOR_INDEX.YELLOW:
                    has_yellow = True
            
            if has_green:
                # This is an instruction paragraph - clear it
                for run in para.runs:
                    run.text = ""
                # Check if we have an answer for this field
                instruction = green_text.strip().strip('[]')
                tag = self._get_tag_from_instruction(instruction)
                if tag in answer_map and not has_yellow:
                    # Add the answer if no yellow sample follows
                    answer_text = answer_map[tag]
                    # Handle multi-line text with HEADING: prefixes
                    self._add_formatted_text(para, answer_text)
            elif has_yellow:
                # This is a sample paragraph - try to find the associated field and replace
                # For now, just clear the yellow highlighting
                for run in para.runs:
                    if run.font.highlight_color == WD_COLOR_INDEX.YELLOW:
                        run.font.highlight_color = None
        
        # Handle table fields
        for field in fields:
            if field.is_table and field.table_index is not None:
                answer = answers.get(field.tag)
                if answer:
                    table_data = answer.value if hasattr(answer, 'value') else answer
                    if table_data and isinstance(table_data, list) and len(table_data) > 0:
                        try:
                            self._fill_table(doc.tables[field.table_index], table_data)
                            logger.info(f"Filled table for {field.tag}")
                        except Exception as e:
                            logger.warning(f"Failed to fill table {field.tag}: {e}")
        
        # Handle architecture diagram - insert after PROJECT_PLAN field
        arch_answer = answers.get("ARCHITECTURE_DIAGRAM")
        if arch_answer:
            mermaid_code = arch_answer.value if hasattr(arch_answer, 'value') else str(arch_answer)
            if mermaid_code and mermaid_code.strip():
                # Find PROJECT_PLAN field to insert diagram after it
                project_plan_field = next((f for f in fields if f.tag == "PROJECT_PLAN"), None)
                if project_plan_field and project_plan_field.sample_para_indices:
                    # Insert after the last PROJECT_PLAN paragraph
                    insert_after_idx = max(project_plan_field.sample_para_indices)
                    self._insert_diagram_after_paragraph(doc, insert_after_idx, mermaid_code, output_path)
                else:
                    # Fallback: append at end
                    self._append_diagram_section(doc, mermaid_code, output_path)
        
        # Final cleanup - remove any remaining highlighted text
        self._cleanup_document(doc)
        
        # Save document
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        logger.info(f"Saved SOW document to: {output_path}")
        
        return output_path
    
    def _clear_paragraph(self, para):
        """Clear all text from a paragraph."""
        for run in para.runs:
            run.text = ""
    
    def _insert_diagram(self, doc: Document, para_idx: int, mermaid_code: str, output_path: Path):
        """Insert a rendered mermaid diagram into the document."""
        if not mermaid_code or not mermaid_code.strip():
            return
        
        try:
            # Render the diagram
            diagram_dir = output_path.parent / "diagrams"
            diagram_dir.mkdir(parents=True, exist_ok=True)
            diagram_path = diagram_dir / f"architecture_{output_path.stem}.png"
            
            rendered_path = self.mermaid_renderer.render_to_png(mermaid_code, diagram_path, width=800)
            
            if rendered_path and rendered_path.exists():
                para = doc.paragraphs[para_idx]
                para.clear()
                run = para.add_run()
                run.add_picture(str(rendered_path), width=Inches(6))
                logger.info(f"Inserted architecture diagram from: {rendered_path}")
            else:
                logger.error("Mermaid rendering failed - diagram was pre-validated but failed here")
                doc.paragraphs[para_idx].clear()
                
        except Exception as e:
            logger.error(f"Failed to insert diagram: {e}")
            try:
                doc.paragraphs[para_idx].clear()
            except:
                pass
    
    def _insert_diagram_after_paragraph(self, doc: Document, para_idx: int, mermaid_code: str, output_path: Path):
        """Insert architecture diagram section after a specific paragraph (after PROJECT_PLAN)."""
        if not mermaid_code or not mermaid_code.strip():
            return
        
        try:
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            
            # Render the diagram
            diagram_dir = output_path.parent / "diagrams"
            diagram_dir.mkdir(parents=True, exist_ok=True)
            diagram_path = diagram_dir / f"architecture_{output_path.stem}.png"
            
            rendered_path = self.mermaid_renderer.render_to_png(mermaid_code, diagram_path, width=800)
            
            if rendered_path and rendered_path.exists():
                # Get the reference paragraph
                ref_para = doc.paragraphs[para_idx]
                
                # Create heading paragraph element
                heading_p = OxmlElement('w:p')
                heading_r = OxmlElement('w:r')
                heading_rPr = OxmlElement('w:rPr')
                heading_b = OxmlElement('w:b')
                heading_rPr.append(heading_b)
                heading_r.append(heading_rPr)
                heading_t = OxmlElement('w:t')
                heading_t.text = "Solution Architecture"
                heading_r.append(heading_t)
                heading_p.append(heading_r)
                
                # Insert heading after reference paragraph
                ref_para._element.addnext(heading_p)
                
                # Create a new paragraph for the diagram
                diagram_para = doc.add_paragraph()
                run = diagram_para.add_run()
                run.add_picture(str(rendered_path), width=Inches(6))
                
                # Move the diagram paragraph to after the heading
                diagram_p_element = diagram_para._element
                body = doc.element.body
                body.remove(diagram_p_element)
                heading_p.addnext(diagram_p_element)
                
                logger.info(f"Inserted architecture diagram after PROJECT_PLAN from: {rendered_path}")
            else:
                logger.error("Mermaid rendering failed for diagram insertion")
                
        except Exception as e:
            logger.error(f"Failed to insert diagram after paragraph: {e}")
            # Fallback to append at end
            self._append_diagram_section(doc, mermaid_code, output_path)
    
    def _append_diagram_section(self, doc: Document, mermaid_code: str, output_path: Path):
        """Append an architecture diagram section at the end of the document."""
        if not mermaid_code or not mermaid_code.strip():
            return
        
        try:
            # Render the diagram
            diagram_dir = output_path.parent / "diagrams"
            diagram_dir.mkdir(parents=True, exist_ok=True)
            diagram_path = diagram_dir / f"architecture_{output_path.stem}.png"
            
            rendered_path = self.mermaid_renderer.render_to_png(mermaid_code, diagram_path, width=800)
            
            if rendered_path and rendered_path.exists():
                # Add a heading for the diagram section
                heading_para = doc.add_paragraph()
                heading_run = heading_para.add_run("Solution Architecture")
                heading_run.bold = True
                heading_run.font.size = Pt(14)
                
                # Add the diagram
                diagram_para = doc.add_paragraph()
                run = diagram_para.add_run()
                run.add_picture(str(rendered_path), width=Inches(6))
                
                logger.info(f"Appended architecture diagram section from: {rendered_path}")
            else:
                logger.error("Mermaid rendering failed for appended diagram")
                
        except Exception as e:
            logger.error(f"Failed to append diagram section: {e}")
    
    def _fill_table(self, table, data: List[Dict[str, Any]]):
        """Fill a table with data."""
        if not data:
            return
        
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        
        # Add rows for data
        for row_data in data:
            row = table.add_row()
            for col_idx, header in enumerate(headers):
                if col_idx < len(row.cells):
                    value = row_data.get(header, "")
                    row.cells[col_idx].text = str(value)
    
    def _replace_sample_text(self, doc: Document, field: TemplateField, answer_text: str):
        """Replace sample text paragraphs with answer text."""
        if not answer_text:
            return
        
        # Simple approach: put all text in the first sample paragraph
        if field.sample_para_indices:
            try:
                first_para = doc.paragraphs[field.sample_para_indices[0]]
                # Clear existing content
                for run in first_para.runs:
                    run.text = ""
                # Add new content - preserve first run for formatting
                if first_para.runs:
                    first_para.runs[0].text = answer_text
                else:
                    first_para.add_run(answer_text)
                
                # Clear any additional sample paragraphs
                for para_idx in field.sample_para_indices[1:]:
                    try:
                        self._clear_paragraph(doc.paragraphs[para_idx])
                    except (IndexError, ValueError):
                        pass
            except (IndexError, ValueError) as e:
                logger.warning(f"Could not replace sample text for {field.tag}: {e}")
    
    def _cleanup_document(self, doc: Document):
        """Remove any remaining highlighted text from the document."""
        for para in doc.paragraphs:
            for run in para.runs:
                if run.font.highlight_color in [WD_COLOR_INDEX.BRIGHT_GREEN, WD_COLOR_INDEX.YELLOW]:
                    run.text = ""
