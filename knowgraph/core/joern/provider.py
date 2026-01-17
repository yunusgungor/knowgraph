"""Joern integration provider - CPG generation and entity extraction."""

import logging
import platform
import subprocess
import tempfile
import networkx as nx
from pathlib import Path

from knowgraph.core.joern.types import ExportFormat, JoernCPG, JoernEntity
from knowgraph.core.joern.manager import INSTALL_DIR

logger = logging.getLogger(__name__)


class JoernNotFoundError(Exception):
    """Raised when Joern CLI is not found."""


class JoernProvider:
    """Joern CPG generator and exporter.
    
    Handles Joern CLI execution, CPG generation, GraphML export,
    and entity extraction for KnowGraph integration.
    """
    
    def __init__(self, joern_path: str | None = None):
        """Initialize Joern provider.
        
        Args:
        ----
            joern_path: Path to Joern CLI (auto-detected if None)
            
        Raises:
        ------
            JoernNotFoundError: If Joern CLI not found
            
        """
        self.joern_path = joern_path or self._find_joern()
        if not self.joern_path:
            raise JoernNotFoundError(
                "Joern CLI not found. Run: knowgraph-setup-joern"
            )
        logger.info(f"Joern found at: {self.joern_path}")
        
    def _find_joern(self) -> str | None:
        """Auto-detect Joern installation.
        
        Checks:
        1. ~/.knowgraph/joern/joern-cli (Default Managed Location)
        2. /usr/local/joern/joern-cli
        3. $PATH (finds executable, returns parent)
        
        Returns
        -------
            Path to Joern CLI directory (not executable) or None
            
        """
        # Check 1: KnowGraph installation directory (using constant from manager)
        knowgraph_joern = INSTALL_DIR / "joern-cli"
        
        if knowgraph_joern.exists() and knowgraph_joern.is_dir():
            return str(knowgraph_joern)
            
        # Check 2: Common install locations
        common_paths = [
            "/usr/local/joern/joern-cli",
            "/opt/joern/joern-cli",
        ]
        for path in common_paths:
            if Path(path).exists() and Path(path).is_dir():
                return path
                
        # Check 3: $PATH (find executable, return parent directory)
        try:
            result = subprocess.run(
                ["which" if platform.system() != "Windows" else "where", "joern"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                exe_path = Path(result.stdout.strip().split("\n")[0])
                # Return parent directory (joern-cli)
                return str(exe_path.parent)
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass
            
        return None
        
    def generate_cpg(
        self,
        repo_path: Path,
        language: str | None = None,
        timeout: int = 600,
    ) -> Path:
        """Generate Code Property Graph using Joern.
        
        Args:
        ----
            repo_path: Path to source code repository
            language: Language hint (auto-detected if None)
            timeout: Timeout in seconds (default: 600)
            
        Returns:
        -------
            Path to generated cpg.bin file
            
        Raises:
        ------
            subprocess.CalledProcessError: If joern-parse fails
            subprocess.TimeoutExpired: If timeout exceeded
            
        """
        output_path = tempfile.mkdtemp(prefix="joern_cpg_")
        output_file = Path(output_path) / "cpg.bin"
        
        # Build joern-parse command
        # joern_path is now the joern-cli directory
        joern_parse = str(Path(self.joern_path) / "joern-parse")
        cmd = [joern_parse, str(repo_path), "--output", str(output_file)]
        
        if language:
            cmd.extend(["--language", language])
            
        logger.info(f"Generating CPG: {' '.join(cmd)}")
        print(f"🔧 Generating Code Property Graph...")
        
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                logger.error(f"joern-parse failed: {result.stderr}")
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    result.stdout,
                    result.stderr,
                )
                
            logger.info(f"✅ CPG generated: {output_file}")
            return output_file
            
        except subprocess.TimeoutExpired:
            logger.error(f"CPG generation timed out after {timeout}s")
            raise
            
    def export_graphml(self, cpg_path: Path, timeout: int = 300) -> Path:
        """Export CPG to GraphML format.
        
        Args:
        ----
            cpg_path: Path to cpg.bin file
            timeout: Timeout in seconds (default: 300)
            
        Returns:
        -------
            Path to exported GraphML file
            
        Raises:
        ------
            subprocess.CalledProcessError: If joern-export fails
            subprocess.TimeoutExpired: If timeout exceeded
            FileNotFoundError: If export succeeds but file not found
            
        """
        output_dir = cpg_path.parent
        export_dir = output_dir / "graphml_export"  # Separate directory for export
        
        # Build joern-export command
        # Note: -o expects a DIRECTORY that DOESN'T EXIST YET in Joern v4.x
        joern_export = str(Path(self.joern_path) / "joern-export")
        cmd = [
            joern_export,
            "--repr", "all",  # "all" works with GraphML (cpg14 doesn't!)
            "--format", "graphml",
            "-o", str(export_dir),  # Must not exist yet!
            str(cpg_path),
        ]
        
        logger.info(f"Exporting GraphML: {' '.join(cmd)}")
        print(f"📤 Exporting to GraphML...")
        
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
            
            # Check if command succeeded
            if result.returncode != 0:
                logger.warning(f"joern-export returned {result.returncode}: {result.stderr}")
                # Try alternative: maybe output goes to stdout
                if result.stdout:
                    # Write stdout to file (create a generic name for it)
                    stdout_output_file = output_dir / "stdout_export.graphml"
                    stdout_output_file.write_text(result.stdout)
                    logger.info(f"✅ Created GraphML from stdout: {stdout_output_file}")
                    return stdout_output_file
            
            # Joern might return non-zero but still create files
            
            # Joern exports GraphML files (may use .xml or .graphml extension)
            # Return the directory itself - parse_graphml_to_cpg will handle it
            graphml_files = []
            if export_dir.exists():
                graphml_files = list(export_dir.glob("**/*.graphml")) + list(export_dir.glob("**/*.xml"))
            
            if graphml_files:
                logger.info(f"✅ GraphML exported: {len(graphml_files)} files in {export_dir}")
                # Return export directory - caller will parse all files
                return export_dir
                    
            # No GraphML found - log debug info
            logger.error(f"No GraphML files found in {export_dir}")
            if export_dir.exists():
                logger.error(f"Export directory contents: {list(export_dir.iterdir())}")
            logger.error(f"stdout: {result.stdout[:500] if result.stdout else 'empty'}")
            logger.error(f"stderr: {result.stderr[:500] if result.stderr else 'empty'}")
            
            raise FileNotFoundError(
                f"GraphML export completed but no .graphml files found in {export_dir}"
            )
            
        except subprocess.TimeoutExpired:
            logger.error(f"GraphML export timed out after {timeout}s")
            raise
            
    def parse_graphml_to_cpg(self, graphml_path: Path) -> JoernCPG:
        """Parse GraphML file(s) to CPG structure.
        
        Joern exports multiple GraphML files (per-method) to a directory.
        This method handles both single files and directories.
        
        Args:
        ----
            graphml_path: Path to GraphML file or directory containing .graphml files
            
        Returns:
        -------
            JoernCPG object with nodes, edges, metadata
            
        """
        logger.info(f"Parsing GraphML: {graphml_path}")
        
        try:
            # Determine if path is file or directory
            if graphml_path.is_dir():
                # Directory: find all .graphml and .xml files (Joern uses both)
                graphml_files = list(graphml_path.glob("**/*.graphml")) + list(graphml_path.glob("**/*.xml"))
                if not graphml_files:
                    logger.warning(f"No GraphML/XML files found in {graphml_path}")
                    # Return empty CPG
                    return JoernCPG(nodes=[], edges=[], metadata={"num_nodes": 0, "num_edges": 0})
                    
                logger.info(f"Found {len(graphml_files)} GraphML files to merge")
                
                # Merge all GraphML files into single graph
                # Use MultiDiGraph because Joern exports multigraphs (multiple edges between same nodes)
                merged_graph = nx.MultiDiGraph()
                for gml_file in graphml_files:
                    try:
                        subgraph = nx.read_graphml(str(gml_file))
                        # Merge nodes and edges
                        merged_graph = nx.compose(merged_graph, subgraph)
                        logger.debug(f"Merged {len(subgraph.nodes())} nodes from {gml_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to parse {gml_file.name}: {e}")
                        continue
                        
                graph = merged_graph
                
            else:
                # Single file
                graph = nx.read_graphml(str(graphml_path))
            
            # Extract nodes
            nodes = []
            for node_id, node_data in graph.nodes(data=True):
                nodes.append({
                    "id": node_id,
                    **node_data,
                })
                
            # Extract edges
            edges = []
            for source, target, edge_data in graph.edges(data=True):
                edges.append({
                    "source": source,
                    "target": target,
                    **edge_data,
                })
                
            # Metadata
            metadata = {
                "num_nodes": len(nodes),
                "num_edges": len(edges),
                "source_file": str(graphml_path),
            }
            
            logger.info(f"✅ Parsed {len(nodes)} nodes, {len(edges)} edges")
            return JoernCPG(nodes=nodes, edges=edges, metadata=metadata)
            
        except Exception as e:
            logger.error(f"GraphML parsing failed: {e}")
            raise
            
    def export_cpg(
        self,
        cpg_path: Path,
        format: ExportFormat = ExportFormat.GRAPHML,
        output_path: Path | None = None,
        timeout: int = 300,
    ) -> Path:
        """Export CPG in various formats.
        
        Args:
        ----
            cpg_path: Path to CPG binary (.bin file)
            format: Export format (GraphML, JSON, SARIF, Neo4j, DOT)
            output_path: Output directory (auto-generated if None)
            timeout: Export timeout in seconds
            
        Returns:
        -------
            Path to exported file or directory
            
        """
        # Determine output directory
        if output_path:
            output_dir = output_path
        else:
            output_dir = cpg_path.parent / f"export_{format.value}"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build joern-export command
        joern_export = str(Path(self.joern_path) / "joern-export")
        
        cmd = [
            joern_export,
            "--format", format.value,
            "-o", str(output_dir),
            str(cpg_path),
        ]
        
        # Add format-specific options
        if format == ExportFormat.GRAPHML:
            cmd.insert(2, "--repr")
            cmd.insert(3, "all")
        
        logger.info(f"Exporting CPG to {format.value}: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.joern_path),
            )
            
            if result.returncode != 0:
                logger.error(f"Export failed: {result.stderr}")
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    result.stdout,
                    result.stderr,
                )
            
            # Find exported file(s)
            exported_files = []
            
            if format == ExportFormat.GRAPHML:
                exported_files = list(output_dir.glob("*.graphml")) + list(output_dir.glob("*.xml"))
            elif format == ExportFormat.JSON:
                exported_files = list(output_dir.glob("*.json"))
            elif format == ExportFormat.SARIF:
                exported_files = list(output_dir.glob("*.sarif"))
            elif format == ExportFormat.DOT:
                exported_files = list(output_dir.glob("*.dot"))
            elif format == ExportFormat.NEO4J:
                # Neo4j exports to directory structure
                return output_dir
            
            if exported_files:
                logger.info(f"✅ Exported to {format.value}: {len(exported_files)} files")
                return exported_files[0] if len(exported_files) == 1 else output_dir
            
            logger.warning(f"Export succeeded but no files found in {output_dir}")
            return output_dir
            
        except subprocess.TimeoutExpired:
            logger.error(f"Export timeout after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
            
    def extract_entities_from_cpg(self, cpg: JoernCPG) -> list[JoernEntity]:
        """Extract KnowGraph entities from Joern CPG.
        
        Converts CPG nodes to KnowGraph-compatible entities.
        
        Args:
        ----
            cpg: Joern CPG object
            
        Returns:
        -------
            List of JoernEntity objects
            
        """
        entities = []
        
        for node in cpg.nodes:
            # Joern uses 'labelV' for node type (not 'label')
            node_type = node.get("labelV", node.get("label", "")).upper()
            # Try NAME first, then CODE for node name
            node_name = node.get("NAME", node.get("CODE", node.get("FULL_NAME", "")))
            
            # Skip if no name
            if not node_name:
                continue
            
            # Map Joern node types to KnowGraph entity types
            if node_type in ["METHOD", "FUNCTION"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="definition",
                    description=f"Function definition: {node_name}",
                ))
            elif node_type in ["CALL"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="call",
                    description=f"Function call: {node_name}",
                ))
            elif node_type in ["IDENTIFIER", "LOCAL"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="reference",
                    description=f"Variable reference: {node_name}",
                ))
            elif node_type in ["IMPORT"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="import",
                    description=f"Import: {node_name}",
                ))
                
        logger.info(f"✅ Extracted {len(entities)} entities from CPG")
        return entities

    def run_security_scan(self, cpg_path: Path) -> dict:
        """Run security scan using PolicyEngine."""
        # Delayed import to avoid circular dependency
        from knowgraph.application.security.policy_engine import PolicyEngine
        engine = PolicyEngine()
        violations = engine.validate_policies(cpg_path)
        
        # Convert to dict format expected by CodeQueryHandler
        return {"violations": [
            {
                "rule_name": v.policy.name,
                "description": v.description,
                "severity": v.severity.name,
                "message": v.description,
                "file_path": str(v.location),
                "line_number": 0
            }
            for v in violations
        ]}

    def find_dead_code(self, cpg_path: Path) -> dict:
        """Find dead code using DominanceAnalyzer."""
        # Delayed import
        from knowgraph.application.analysis.dominance_analyzer import DominanceAnalyzer
        analyzer = DominanceAnalyzer()
        dead_methods = analyzer.find_dead_code(cpg_path)
        # CodeQueryHandler expects simple list of names in 'unreachable_methods'
        return {"unreachable_methods": [m.get('name') for m in dead_methods if isinstance(m, dict)]}

    def analyze_call_graph(self, cpg_path: Path, analysis_type: str = "validate") -> dict:
        """Analyze call graph using CallGraphAnalyzer."""
        # Delayed import
        from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer
        analyzer = CallGraphAnalyzer()
        
        if analysis_type == "validate":
            result = analyzer.validate_call_graph(cpg_path)
            # Handle the named tuple result
            return {
                "is_valid": result.is_valid,
                "total_methods": result.total_methods,
                "call_edges": result.call_edges,
                "entry_points": result.entry_points
            }
        elif analysis_type == "recursive":
             recursive_methods = analyzer.find_recursive_calls(cpg_path)
             return {"recursive_methods": recursive_methods}
        return {}
