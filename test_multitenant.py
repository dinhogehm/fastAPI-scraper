#!/usr/bin/env python3
"""
Script de teste para demonstrar o funcionamento do sistema multi-tenant.
Testa isolamento, rate limiting e concorrência entre diferentes usuários.
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import time

# Configuração dos testes
BASE_URL = "http://localhost:8080"

# API Keys de diferentes tenants
API_KEYS = {
    "user1": "test_key_123",    # Tenant 1
    "user2": "demo_key_456",    # Tenant 1 (mesmo tenant, usuário diferente)
    "user3": "prod_key_789"     # Tenant 2
}

TEST_URLS = [
    "https://httpbin.org/delay/1",
    "https://httpbin.org/delay/2", 
    "https://httpbin.org/delay/3",
    "https://example.com",
    "https://httpbin.org/html"
]

class MultiTenantTester:
    def __init__(self):
        self.results = {}
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def make_request(self, method: str, endpoint: str, api_key: str, data: dict = None):
        """Faz uma requisição para a API."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{BASE_URL}{endpoint}"
        
        try:
            if method == "POST":
                async with self.session.post(url, headers=headers, json=data) as response:
                    return response.status, await response.json()
            else:
                async with self.session.get(url, headers=headers) as response:
                    return response.status, await response.json()
        except Exception as e:
            return None, {"error": str(e)}
    
    async def test_basic_functionality(self):
        """Testa funcionalidade básica para cada usuário."""
        print("\n=== Teste 1: Funcionalidade Básica ===")
        
        for user, api_key in API_KEYS.items():
            print(f"\nTestando usuário: {user}")
            
            # Inicia um scraping
            status, response = await self.make_request(
                "POST", "/scrape",
                api_key,
                {"url": "https://example.com", "limit": 5, "knowledge_base_id": f"kb_{user}_001"}
            )
            
            if status == 200:
                task_id = response["id"]
                print(f"  ✅ Scraping iniciado: {task_id}")
                
                # Verifica status
                status, task_status = await self.make_request(
                    "GET", 
                    f"/status/{task_id}",
                    api_key
                )
                
                if status == 200:
                    print(f"  ✅ Status obtido: {task_status['status']}")
                else:
                    print(f"  ❌ Erro ao obter status: {task_status}")
            else:
                print(f"  ❌ Erro ao iniciar scraping: {response}")
    
    async def test_isolation(self):
        """Testa isolamento entre tenants."""
        print("\n=== Teste 2: Isolamento entre Tenants ===")
        
        # User1 inicia uma tarefa
        status, response = await self.make_request(
            "POST", "/scrape",
            API_KEYS["user1"],
            {"url": "https://example.com", "limit": 3, "knowledge_base_id": "kb_user1_001"}
        )
        
        if status == 200:
            task_id = response["id"]
            print(f"User1 criou tarefa: {task_id}")
            
            # User3 (tenant diferente) tenta acessar a tarefa do User1
            status, response = await self.make_request(
                "GET",
                f"/status/{task_id}",
                API_KEYS["user3"]
            )
            
            if status == 404:
                print("  ✅ Isolamento funcionando: User3 não pode acessar tarefa do User1")
            else:
                print(f"  ❌ Falha no isolamento: {response}")
            
            # User2 (mesmo tenant) tenta acessar a tarefa do User1
            status, response = await self.make_request(
                "GET",
                f"/status/{task_id}",
                API_KEYS["user2"]
            )
            
            if status == 200:
                print("  ✅ Acesso dentro do tenant funcionando: User2 pode acessar tarefa do User1")
            else:
                print(f"  ❌ Erro no acesso dentro do tenant: {response}")
    
    async def test_rate_limiting(self):
        """Testa rate limiting por tenant."""
        print("\n=== Teste 3: Rate Limiting ===")
        
        user = "user1"
        api_key = API_KEYS[user]
        
        print(f"Testando rate limiting para {user}...")
        
        # Faz muitas requisições rapidamente
        tasks = []
        for i in range(25):  # Mais que o limite de 20/min
            task = self.make_request(
                "POST", "/scrape",
                api_key,
                {"url": f"https://httpbin.org/delay/{i%3+1}", "limit": 2, "knowledge_base_id": "kb_user1_rate_test"}
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for status, _ in results if isinstance(status, int) and status == 200)
        rate_limited_count = sum(1 for status, _ in results if isinstance(status, int) and status == 429)
        
        print(f"  Sucessos: {success_count}")
        print(f"  Rate limited: {rate_limited_count}")
        
        if rate_limited_count > 0:
            print("  ✅ Rate limiting funcionando")
        else:
            print("  ⚠️  Rate limiting pode não estar funcionando")
    
    async def test_concurrent_tasks(self):
        """Testa limite de tarefas concorrentes."""
        print("\n=== Teste 4: Limite de Tarefas Concorrentes ===")
        
        user = "user3"
        api_key = API_KEYS[user]
        
        print(f"Testando limite de concorrência para {user}...")
        
        # Inicia várias tarefas simultaneamente
        tasks = []
        for i in range(8):  # Mais que o limite de 5 concorrentes
            task = self.make_request(
                "POST", "/scrape",
                api_key,
                {"url": f"https://httpbin.org/delay/{i%3+2}", "limit": 10, "knowledge_base_id": "kb_user3_concurrent_test"}
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for status, _ in results if isinstance(status, int) and status == 200)
        rejected_count = sum(1 for status, _ in results if isinstance(status, int) and status == 429)
        
        print(f"  Tarefas aceitas: {success_count}")
        print(f"  Tarefas rejeitadas: {rejected_count}")
        
        if rejected_count > 0:
            print("  ✅ Limite de concorrência funcionando")
        else:
            print("  ⚠️  Limite de concorrência pode não estar funcionando")
    
    async def test_statistics(self):
        """Testa endpoint de estatísticas."""
        print("\n=== Teste 5: Estatísticas por Tenant ===")
        
        for user, api_key in API_KEYS.items():
            status, stats = await self.make_request("GET", "/stats", api_key)
            
            if status == 200:
                print(f"\nEstatísticas para {user}:")
                print(f"  Tenant: {stats['user_info']['tenant_id']}")
                print(f"  Total de requisições: {stats['total_requests']}")
                print(f"  Tarefas ativas: {stats['active_tasks']}")
                print(f"  Tarefas concluídas: {stats['completed_tasks']}")
                print(f"  Tarefas falhadas: {stats['failed_tasks']}")
                print(f"  Rate limit atual: {stats['rate_limit']['requests_this_minute']}/{stats['rate_limit']['max_requests_per_minute']}")
                print(f"  Tarefas concorrentes: {stats['rate_limit']['concurrent_tasks']}/{stats['rate_limit']['max_concurrent_tasks']}")
            else:
                print(f"❌ Erro ao obter estatísticas para {user}: {stats}")
    
    async def test_health_check(self):
        """Testa endpoint de health check."""
        print("\n=== Teste 6: Health Check ===")
        
        async with self.session.get(f"{BASE_URL}/health") as response:
            if response.status == 200:
                health = await response.json()
                print(f"Status: {health['status']}")
                print(f"Tenants ativos: {health['active_tenants']}")
                print(f"IDs dos tenants: {health['tenant_ids']}")
                print("✅ Health check funcionando")
            else:
                print(f"❌ Health check falhou: {response.status}")
    
    async def run_all_tests(self):
        """Executa todos os testes."""
        print("🚀 Iniciando testes do sistema multi-tenant...")
        print(f"Testando API em: {BASE_URL}")
        
        await self.test_health_check()
        await self.test_basic_functionality()
        await self.test_isolation()
        await self.test_statistics()
        await self.test_rate_limiting()
        await self.test_concurrent_tasks()
        
        print("\n✅ Todos os testes concluídos!")
        print("\n📊 Verifique as estatísticas finais:")
        await self.test_statistics()

async def test_basic_scraping():
    """Teste básico de scraping."""
    print("\n=== Teste de Scraping ===")
    scrape_data = {
        "url": "https://httpbin.org/html",
        "limit": 5,
        "knowledge_base_id": "kb_empresa_a_001"
    }
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {API_KEYS['user1']}", "Content-Type": "application/json"}
        
        async with session.post(f"{BASE_URL}/scrape", json=scrape_data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Scraping iniciado: {result['id']} para knowledge base: kb_empresa_a_001")
                task_id = result['id']
            else:
                text = await response.text()
                print(f"❌ Erro no scraping: {response.status} - {text}")
                return

async def main():
    """Função principal."""
    async with MultiTenantTester() as tester:
        await tester.run_all_tests()
    
    # Teste adicional de scraping básico
    await test_basic_scraping()

if __name__ == "__main__":
    print("Multi-Tenant Scraper API - Script de Teste")
    print("===========================================")
    print("")
    print("Este script testa:")
    print("- Isolamento entre tenants")
    print("- Rate limiting por usuário")
    print("- Limite de tarefas concorrentes")
    print("- Estatísticas por tenant")
    print("- Funcionalidade básica")
    print("")
    print("Certifique-se de que a API multi-tenant está rodando em http://localhost:8080")
    print("")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Testes interrompidos pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")