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
        
        try:
            if method == "POST":
                async with session.post(url, headers=headers, json=data) as response:
                    return response.status, await response.json()
            elif method == "GET":
                async with session.get(url, headers=headers) as response:
                    return response.status, await response.json()
        except Exception as e:
            return None, {"error": str(e)}

async def debug_isolation():
    """Debug detalhado do isolamento entre tenants."""
    print("=== Debug de Isolamento Entre Tenants ===")
    
    # 1. User1 (tenant_1) cria uma tarefa
    print("\n1. User1 (tenant_1) criando tarefa...")
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
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    # 2. User1 verifica sua própria tarefa
    print("\n2. User1 verificando sua própria tarefa...")
    status, response = await make_request(
        "GET", 
        f"/status/{task_id}",
        API_KEYS["user1"]
    )
    
    print(f"   Status: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status == 200:
        print(f"   ✅ User1 conseguiu acessar sua tarefa")
    else:
        print(f"   ❌ User1 NÃO conseguiu acessar sua própria tarefa")
    
    # 3. User3 (tenant_2) tenta acessar a tarefa do User1
    print("\n3. User3 (tenant_2) tentando acessar tarefa do User1...")
    status, response = await make_request(
        "GET", 
        f"/status/{task_id}",
        API_KEYS["user3"]
    )
    
    print(f"   Status: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status == 404:
        print(f"   ✅ ISOLAMENTO OK: User3 recebeu 404 (tarefa não encontrada)")
    elif status == 403:
        print(f"   ✅ ISOLAMENTO OK: User3 recebeu 403 (acesso negado)")
    elif status == 200:
        print(f"   ❌ FALHA NO ISOLAMENTO: User3 conseguiu acessar tarefa do User1")
        print(f"   🚨 DADOS VAZADOS: {response}")
    else:
        print(f"   ⚠️  COMPORTAMENTO INESPERADO: Status {status}")
        print(f"   🔍 Investigar: {response}")
    
    # 4. User3 cria sua própria tarefa
    print("\n4. User3 (tenant_2) criando sua própria tarefa...")
    status, response = await make_request(
        "POST", "/scrape",
        API_KEYS["user3"],
        {
            "url": "https://httpbin.org/json",
            "knowledge_base_id": "kb_user3_001",
            "limit": 1
        }
    )
    
    if status != 200:
        print(f"❌ Erro ao criar tarefa: {status} - {response}")
        return
    
    user3_task_id = response["id"]
    print(f"✅ Tarefa do User3 criada: {user3_task_id}")
    
    # 5. User1 tenta acessar a tarefa do User3
    print("\n5. User1 (tenant_1) tentando acessar tarefa do User3...")
    status, response = await make_request(
        "GET", 
        f"/status/{user3_task_id}",
        API_KEYS["user1"]
    )
    
    print(f"   Status: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status == 404:
        print(f"   ✅ ISOLAMENTO OK: User1 recebeu 404 (tarefa não encontrada)")
    elif status == 403:
        print(f"   ✅ ISOLAMENTO OK: User1 recebeu 403 (acesso negado)")
    elif status == 200:
        print(f"   ❌ FALHA NO ISOLAMENTO: User1 conseguiu acessar tarefa do User3")
        print(f"   🚨 DADOS VAZADOS: {response}")
    else:
        print(f"   ⚠️  COMPORTAMENTO INESPERADO: Status {status}")
        print(f"   🔍 Investigar: {response}")
    
    # 6. User3 verifica sua própria tarefa
    print("\n6. User3 verificando sua própria tarefa...")
    status, response = await make_request(
        "GET", 
        f"/status/{user3_task_id}",
        API_KEYS["user3"]
    )
    
    print(f"   Status: {status}")
    print(f"   Response: {json.dumps(response, indent=2)}")
    
    if status == 200:
        print(f"   ✅ User3 conseguiu acessar sua tarefa")
    else:
        print(f"   ❌ User3 NÃO conseguiu acessar sua própria tarefa")
    
    print("\n=== Resumo do Teste ===")
    print("- Cada tenant deve conseguir acessar apenas suas próprias tarefas")
    print("- Tentativas de acesso cross-tenant devem retornar 404 ou 403")
    print("- Status 200 com dados = FALHA DE SEGURANÇA")
    print("- Status 500 = BUG no código")

if __name__ == "__main__":
    asyncio.run(debug_isolation())