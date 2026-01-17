
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from knowgraph.application.query.code_query_handler import CodeQueryHandler
from knowgraph.application.query.query_classifier import QueryClassifier, QueryType

class TestGapFill(unittest.TestCase):
    def setUp(self):
        self.classifier = QueryClassifier()
        self.handler = CodeQueryHandler(Path("/tmp/test_graph"))
        
        # Mock dependencies in handler
        self.patcher_provider = patch("knowgraph.core.joern.JoernProvider")
        self.MockProvider = self.patcher_provider.start()
        self.mock_provider_instance = self.MockProvider.return_value
        
        self.patcher_get_cpg = patch("knowgraph.infrastructure.indexing.cpg_metadata.get_cpg_path")
        self.mock_get_cpg = self.patcher_get_cpg.start()
        self.mock_get_cpg.return_value = Path("/tmp/cpg.bin")

    def tearDown(self):
        self.patcher_provider.stop()
        self.patcher_get_cpg.stop()

    def test_annotations(self):
        """Test routing for 'find methods annotated with Transaction'."""
        query = "find methods annotated with Transaction"
        
        # 1. Classification
        q_type = self.classifier.classify(query)
        self.assertEqual(q_type, QueryType.CODE)
        
        # 2. Execution
        async def run_test():
            self.mock_provider_instance.find_annotations.return_value = {
                "pattern": "Transaction",
                "findings": [{"method": "save", "filename": "db.py", "annotations": "@Transaction"}]
            }
            
            result = await self.handler.handle(query)
            
            self.assertEqual(result["tool"], "find_annotations")
            self.assertEqual(result["results"][0]["type"], "annotation")
            self.assertEqual(result["results"][0]["annotations"], "@Transaction")

        asyncio.run(run_test())

    def test_imports(self):
        """Test routing for 'which files import requests'."""
        query = "which files import requests"
        
        async def run_test():
            self.mock_provider_instance.find_imports.return_value = {
                "pattern": "requests",
                "imports": [{"import": "import requests", "filename": "api.py"}]
            }
            
            result = await self.handler.handle(query)
            
            self.assertEqual(result["tool"], "find_imports")
            self.assertEqual(result["results"][0]["import_stmt"], "import requests")

        asyncio.run(run_test())

    def test_structures(self):
        """Test routing for 'show loops in processData'."""
        query = "show loops in processData"
        
        async def run_test():
            self.mock_provider_instance.analyze_structures.return_value = {
                "pattern": "processData",
                "structures": [{"method": "processData", "filename": "data.py", "loops": 2, "ifs": 1}]
            }
            
            result = await self.handler.handle(query)
            
            self.assertEqual(result["tool"], "analyze_structures")
            self.assertEqual(result["results"][0]["loops"], 2)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
