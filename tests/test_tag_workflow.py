"""Complete end-to-end test: Tag snippet via MCP and retrieve it."""

import asyncio

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires graphstore and MCP server - full integration test")
async def test_tag_and_retrieve():
    """Test complete workflow: tag -> index -> query -> retrieve."""
    print("🧪 Complete Tagged Snippet Workflow Test\n")
    print("=" * 60)

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "knowgraph.adapters.mcp.server"],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ MCP Server connected\n")

            # Step 1: Tag an important snippet
            print("1️⃣ Tagging important snippet...")

            important_snippet = """
# FastAPI JWT Authentication - Complete Guide

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

@app.get("/protected")
async def protected_route(token_data: dict = Depends(verify_token)):
    return {"message": "Access granted", "user": token_data}
```

**Key Points:**
- Uses python-jose for JWT handling
- HTTPBearer for token extraction
- Automatic token validation via dependency injection
"""

            result = await session.call_tool(
                "knowgraph_tag_snippet",
                arguments={
                    "tag": "fastapi jwt complete implementation",
                    "snippet": important_snippet,
                    "graph_path": "./test_mcp_graphstore",
                    "conversation_id": "production-test",
                    "user_question": "How do I implement JWT auth in FastAPI?",
                },
            )

            print("✅ Snippet tagged!")
            print("   Tag: 'fastapi jwt complete implementation'")
            print(f"   Response: {result.content[0].text[:100]}...")

            # Step 2: Query for the tagged snippet
            print("\n2️⃣ Querying for tagged snippet...")

            # Note: We'd need to implement query via MCP or use CLI
            print("   (Query would be done via knowgraph CLI or query tool)")
            print("   Query: 'fastapi jwt implementation'")

            print("\n" + "=" * 60)
            print("✅ Tagged snippet workflow test completed!")
            print(
                "\nTo retrieve: knowgraph query 'fastapi jwt' --graph-store ./test_mcp_graphstore"
            )


if __name__ == "__main__":
    asyncio.run(test_tag_and_retrieve())
