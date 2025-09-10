#!/usr/bin/env python3

import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8080"

API_KEYS = {
    "user1": "test_key_123",    # Tenant 1
    "user3": "prod_key_789"     # Tenant 2
}

async def make_request(method: str, endpoint: str, api_key: str, data: dict = None):
    """Faz uma requisição HTTP."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        url = f"{BASE_URL}{endpoint}"
        
        if method == "POST":
            async with session.post(url, headers=headers, json=data) as response:
                return response.status, await response.json()
        elif method == "GET":
            async with session.get(url, headers=headers) as response:
                return response.status, await response.json()

async def test_isolation():
    """Testa isolamento específico entre tenants."""
    print("=== Teste de Isolamento Específico ===")
    
    # User1 (tenant_1) cria uma tarefa
    print("\n1. User1 criando tarefa...")
    status, response = await make_request(
        "POST", "/scrape",
        API_KEYS["user1"],
        {
            "url": "https://httpbin.org/json",
            "knowledge_base_id": "kb_user1_001",
            "limit": 1
        }
    )
    
    if status != 200:
        print(f"❌ Erro ao criar tarefa: {status} - {response}")
        return
    
    task_id = response["id"]
    print(f"✅ Tarefa criada: {task_id}")
    
    # User1 verifica sua própria tarefa
    print("\n2. User1 verificando sua própria tarefa...")
    status, response = await make_request(
        "GET",
        f"/status/{task_id}",
        API_KEYS["user1"]
    )
    print(f"Status: {status}")
    print(f"Response: {response}")
    
    # User3 (tenant_2) tenta acessar a tarefa do User1
    print("\n3. User3 (tenant diferente) tentando acessar tarefa do User1...")
    status, response = await make_request(
        "GET",
        f"/status/{task_id}",
        API_KEYS["user3"]
    )
    print(f"Status: {status}")
    print(f"Response: {response}")
    
    if status == 404:
        print("✅ ISOLAMENTO FUNCIONANDO: User3 não conseguiu acessar tarefa do User1")
    else:
        print("❌ FALHA NO ISOLAMENTO: User3 conseguiu acessar tarefa do User1")

if __name__ == "__main__":
    asyncio.run(test_isolation())