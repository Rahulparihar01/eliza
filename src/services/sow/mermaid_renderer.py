"""
Mermaid Diagram Renderer

Renders Mermaid diagram code to PNG images for embedding in documents.
Uses online rendering services (mermaid.ink, kroki.io) as fallbacks.
"""
import base64
import logging
import tempfile
import zlib
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class MermaidRenderer:
    """Renders Mermaid diagrams to PNG images."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def render_to_png(
        self,
        mermaid_code: str,
        output_path: Optional[Path] = None,
        width: int = 800,
        theme: str = "default",
    ) -> Optional[Path]:
        """
        Render Mermaid diagram code to a PNG image.
        
        Args:
            mermaid_code: The Mermaid diagram code
            output_path: Where to save the PNG (if None, creates temp file)
            width: Width of the rendered image
            theme: Mermaid theme (default, dark, forest, neutral)
        
        Returns:
            Path to the rendered PNG image, or None if rendering failed
        """
        if not mermaid_code or not mermaid_code.strip():
            logger.warning("Empty mermaid code provided")
            return None
        
        # Try multiple rendering methods
        result = self._render_via_mermaid_ink(mermaid_code, output_path, width, theme)
        if result:
            return result
        
        # Fallback: try kroki.io
        result = self._render_via_kroki(mermaid_code, output_path)
        if result:
            return result
        
        logger.error("All mermaid rendering methods failed")
        return None
    
    def _render_via_mermaid_ink(
        self,
        mermaid_code: str,
        output_path: Optional[Path],
        width: int,
        theme: str,
    ) -> Optional[Path]:
        """Render using mermaid.ink service."""
        try:
            # Base64 encode the mermaid code
            encoded = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
            
            # Build the URL
            url = f"https://mermaid.ink/img/{encoded}?width={width}&theme={theme}"
            
            logger.debug(f"Fetching mermaid diagram from mermaid.ink")
            
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200 and response.content:
                # Save to output path
                if output_path is None:
                    output_path = Path(tempfile.mktemp(suffix=".png"))
                
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                
                logger.info(f"Rendered mermaid diagram to: {output_path}")
                return output_path
            else:
                logger.warning(f"mermaid.ink returned status {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"mermaid.ink rendering failed: {e}")
            return None
    
    def _render_via_kroki(
        self,
        mermaid_code: str,
        output_path: Optional[Path],
    ) -> Optional[Path]:
        """Render using kroki.io service as fallback."""
        try:
            # Kroki uses deflate + base64
            compressed = zlib.compress(mermaid_code.encode('utf-8'), 9)
            encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
            
            url = f"https://kroki.io/mermaid/png/{encoded}"
            
            logger.debug(f"Fetching mermaid diagram from kroki.io")
            
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200 and response.content:
                if output_path is None:
                    output_path = Path(tempfile.mktemp(suffix=".png"))
                
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                
                logger.info(f"Rendered mermaid diagram via kroki to: {output_path}")
                return output_path
            else:
                logger.warning(f"kroki.io returned status {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"kroki.io rendering failed: {e}")
            return None
    
    @staticmethod
    def get_image_dimensions(image_path: Path) -> Tuple[int, int]:
        """Get the dimensions of a PNG image."""
        try:
            # Read PNG header to get dimensions
            with open(image_path, 'rb') as f:
                # PNG signature (8 bytes) + IHDR chunk
                f.read(8)  # Skip signature
                f.read(4)  # Skip length
                f.read(4)  # Skip 'IHDR'
                width = int.from_bytes(f.read(4), 'big')
                height = int.from_bytes(f.read(4), 'big')
                return width, height
        except Exception as e:
            logger.warning(f"Could not read image dimensions: {e}")
            return 800, 600  # Default
    
    def validate_mermaid(self, mermaid_code: str) -> bool:
        """
        Validate that mermaid code can be rendered.
        
        Returns True if the code renders successfully, False otherwise.
        """
        if not mermaid_code or not mermaid_code.strip():
            return False
        
        test_path = Path(tempfile.mktemp(suffix=".png"))
        try:
            result = self.render_to_png(mermaid_code, test_path)
            return result is not None and result.exists()
        finally:
            if test_path.exists():
                test_path.unlink()


# Convenience function for backward compatibility
def render_mermaid_to_png(
    mermaid_code: str,
    output_path: Optional[Path] = None,
    width: int = 800,
    theme: str = "default",
) -> Optional[Path]:
    """Render Mermaid diagram code to a PNG image."""
    renderer = MermaidRenderer()
    return renderer.render_to_png(mermaid_code, output_path, width, theme)
