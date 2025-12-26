"""Integration module for code analysis in KnowGraph indexing pipeline.

This module provides hooks for automatic code detection and CPG generation
during the indexing process.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CodeIndexIntegration:
    """Handles code analysis integration during indexing."""
    
    def __init__(self):
        """Initialize code index integration."""
        self.cpg_generated = False
        self.cpg_path: Optional[Path] = None
        self.entities_extracted = 0
    
    def process_code_directory(
        self, 
        input_path: Path,
        graph_path: Path,
        skip_cpg: bool = False
    ) -> dict:
        """Process code directory for indexing.
        
        Args:
            input_path: Directory to analyze
            graph_path: Graph storage path
            skip_cpg: Skip CPG generation (for testing)
            
        Returns:
            Dictionary with processing results
        """
        from knowgraph.infrastructure.indexing.code_file_detector import CodeFileDetector
        from knowgraph.domain.intelligence.joern_provider import JoernProvider
        from knowgraph.domain.intelligence.code_entity_extractor import CodeEntityExtractor
        
        results = {
            'code_files_detected': 0,
            'cpg_generated': False,
            'cpg_path': None,
            'entities_extracted': 0,
            'error': None
        }
        
        try:
            # Step 1: Detect code files
            logger.info("Detecting code files...")
            detector = CodeFileDetector()
            code_files = detector.detect_code_files(input_path)
            
            results['code_files_detected'] = len(code_files)
            
            if not code_files:
                logger.info("No code files detected")
                return results
            
            # Get statistics
            stats = detector.get_statistics(code_files)
            logger.info(f"Found {stats['total_files']} code files ({stats['total_loc']} LOC)")
            
            # Step 2: Check if CPG generation is worthwhile
            if not detector.should_generate_cpg(code_files):
                logger.info("Skipping CPG generation (below threshold)")
                return results
            
            if skip_cpg:
                logger.info("CPG generation skipped (skip_cpg=True)")
                return results
            
            # Step 3: Generate CPG
            logger.info("Generating CPG...")
            try:
                provider = JoernProvider()
                cpg_path = provider.generate_cpg(
                    repo_path=input_path,
                    timeout=300  # 5 minutes
                )
                
                results['cpg_generated'] = True
                results['cpg_path'] = str(cpg_path)
                self.cpg_path = cpg_path
                self.cpg_generated = True
                
                logger.info(f"CPG generated at: {cpg_path}")
                
            except Exception as e:
                logger.error(f"CPG generation failed: {e}")
                results['error'] = f"CPG generation failed: {e}"
                return results
            
            # Step 4: Extract entities
            logger.info("Extracting code entities...")
            try:
                extractor = CodeEntityExtractor()
                entities = extractor.extract_entities(cpg_path)
                
                results['entities_extracted'] = len(entities)
                self.entities_extracted = len(entities)
                
                logger.info(f"Extracted {len(entities)} code entities")
                
                # Step 5: Convert to graph nodes
                if entities:
                    nodes = extractor.entities_to_graph_nodes(entities)
                    results['graph_nodes'] = nodes
                    logger.info(f"Converted to {len(nodes)} graph nodes")
                
            except Exception as e:
                logger.error(f"Entity extraction failed: {e}")
                results['error'] = f"Entity extraction failed: {e}"
                return results
            
            return results
            
        except Exception as e:
            logger.error(f"Code processing failed: {e}")
            results['error'] = str(e)
            return results
    
    def get_summary(self) -> str:
        """Get human-readable summary of code processing.
        
        Returns:
            Summary string
        """
        if not self.cpg_generated:
            return "No code analysis performed"
        
        summary = f"🔧 Code Analysis:\n"
        summary += f"  - CPG generated: {self.cpg_path}\n"
        summary += f"  - Entities extracted: {self.entities_extracted}\n"
        
        return summary
