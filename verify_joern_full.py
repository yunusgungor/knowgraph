import logging
import sys
import shutil
import time
from pathlib import Path
from uuid import uuid4

# Import KnowGraph components
from knowgraph.infrastructure.indexing.code_index_integration import CodeIndexIntegration
from knowgraph.infrastructure.storage.filesystem import read_node_json
from knowgraph.infrastructure.search.sparse_index import SparseIndex
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.application.querying.query_engine import QueryEngine

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(levelname)s: %(message)s')
logger = logging.getLogger("test_runner")

def run_verification():
    print("🚀 STARTING FINAL JOERN VERIFICATION")
    print("=" * 60)
    
    # Paths
    base_dir = Path('/Users/yunusgungor/knowrag')
    code_dir = base_dir / 'knowgraph'
    graph_dir = base_dir / 'graphstore'
    
    # 1. RUN INDEXING (Triggers CPG + Embeddings)
    print("\n📦 STEP 1: Running Code Indexing...")
    start_time = time.time()
    
    try:
        integration = CodeIndexIntegration()
        results = integration.process_code_directory(
            input_path=code_dir,
            graph_path=graph_dir
        )
        
        duration = time.time() - start_time
        print(f"✅ Indexing completed in {duration:.2f}s")
        print(f"   - Entities written: {results.get('entities_written_to_graph', 0)}")
        print(f"   - Entities indexed: {results.get('entities_indexed', 0)}")
        
    except Exception as e:
        print(f"❌ Indexing FAILED: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. VERIFY SPARSE INDEX
    print("\n🔍 STEP 2: Verifying Vector Search (Sparse Index)...")
    try:
        index = SparseIndex()
        index.load(graph_dir / "index")
        print(f"   - Total documents in index: {index.n_docs}")
        
        embedder = SparseEmbedder()
        query = "security scanning"
        query_vec = embedder.embed_text(query)
        
        search_results = index.search(query_vec, top_k=10)
        
        found_code = False
        print(f"   - Results for '{query}':")
        for node_id, score in search_results:
            node = read_node_json(node_id, graph_dir)
            if node:
                prefix = "[CODE]" if node.type.startswith('code_') else "[DOC ]"
                print(f"     {prefix} {node.title} ({node.type}) - Score: {score:.3f}")
                if node.type.startswith('code_'):
                    found_code = True
        
        if found_code:
            print("✅ SUCCESS: Code nodes found in search index!")
        else:
            print("❌ FAILURE: No code nodes found in search results.")
            
    except Exception as e:
        print(f"❌ Search Verification FAILED: {e}")
        return

    # 3. VERIFY QUERY ENGINE (End-to-End)
    print("\n🧠 STEP 3: Verifying Query Engine (End-to-End)...")
    try:
        engine = QueryEngine(graph_dir)
        result = engine.query(
            query_text="how does security scanning work?",
            top_k=5,
            max_hops=2
        )
        
        print(f"   - Seed Nodes: {len(result.seed_nodes)}")
        print(f"   - Context Length: {len(result.context)} chars")
        
        # Check context for code signatures
        context_preview = result.context[:500] + "..."
        # print(f"   - Context Preview:\n{context_preview}")
        
        # Check if seed nodes contain code
        code_seeds = 0
        for node_id in result.seed_nodes:
            node = read_node_json(node_id, graph_dir)
            if node and node.type.startswith('code_'):
                code_seeds += 1
                
        print(f"   - Code Seed Nodes: {code_seeds}")
        
        if code_seeds > 0:
            print("✅ SUCCESS: Query Engine is retrieving code nodes!")
        else:
            print("⚠️ WARNING: Query Engine did not pick code nodes as seeds (might be score threshold).")

    except Exception as e:
        print(f"❌ Query Engine Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n🎉 FINAL VERIFICATION COMPLETE!")

if __name__ == "__main__":
    run_verification()
