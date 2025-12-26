#!/usr/bin/env python3
"""Debug parse_graphml_to_cpg method."""

import networkx as nx
from pathlib import Path

# Simulate what parse_graphml_to_cpg does
graphml_path = Path("/tmp/test_joern/export_test")

print(f"Testing parse logic with: {graphml_path}")
print(f"Is directory: {graphml_path.is_dir()}")
print(f"Exists: {graphml_path.exists()}")
print("=" * 60)

if graphml_path.is_dir():
    # Find GraphML files
    graphml_files = list(graphml_path.glob("**/*.graphml")) + list(graphml_path.glob("**/*.xml"))
    print(f"Found {len(graphml_files)} files:")
    for f in graphml_files:
        print(f"  - {f.name} ({f.stat().st_size} bytes)")
    
    if not graphml_files:
        print("❌ No files found!")
    else:
        # Try to merge
        merged_graph = nx.DiGraph()
        for gml_file in graphml_files:
            try:
                print(f"\nParsing {gml_file.name}...")
                subgraph = nx.read_graphml(str(gml_file))
                print(f"  Parsed: {len(subgraph.nodes())} nodes, {len(subgraph.edges())} edges")
                
                # Merge
                merged_graph = nx.compose(merged_graph, subgraph)
                print(f"  After merge: {len(merged_graph.nodes())} total nodes")
            except Exception as e:
                print(f"  ERROR: {e}")
                
        print(f"\n✅ Final merged graph:")
        print(f"   Nodes: {len(merged_graph.nodes())}")
        print(f"   Edges: {len(merged_graph.edges())}")
