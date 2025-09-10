#!/usr/bin/env python3
"""
Teste Abrangente de Isolamento Multi-Tenant

Este teste verifica:
1. Isolamento básico entre tenants
2. Tentativas de acesso com IDs inválidos
3. Tentativas de acesso com API keys inválidas
4. Verificação de que tarefas não vazam entre tenants
5. Teste de concorrência entre tenants
6. Verificação de estatísticas isoladas
"""

import asyncio
import aiohttp
import json
import uuid
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8080"

# Configuração de tenants e usuários
TENANTS = {
    "tenant_1": {
        "users": {
            "user1": {"api_key": "test_key_123", "kb": "kb_user1_001"},
            "user2": {"api_key": "demo_key_456", "kb": "kb_user2_001"}
        }
    },
    "tenant_2": {
        "users": {
            "user3": {"api_key": "prod_key_789", "kb": "kb_user3_001"}
        }
    }
}

class IsolationTester:
    def __init__(self):
        self.created_tasks: Dict[str, List[str]] = {}  # user_id -> [task_ids]
        self.test_results: List[Dict] = []
    
    async def make_request(self, method: str, endpoint: str, api_key: str, data: dict = None) -> Tuple[int, dict]:
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
    
    def log_test(self, test_name: str, expected: str, actual: str, passed: bool, details: str = ""):
        """Registra resultado de um teste."""
        result = {
            "test": test_name,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "details": details
        }
        self.test_results.append(result)
        
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} {test_name}")
        print(f"   Esperado: {expected}")
        print(f"   Obtido: {actual}")
        if details:
            print(f"   Detalhes: {details}")
        print()
    
    async def create_task_for_user(self, user_id: str, tenant_config: dict) -> str:
        """Cria uma tarefa para um usuário específico."""
        user_config = None
        for tenant_data in TENANTS.values():
            if user_id in tenant_data["users"]:
                user_config = tenant_data["users"][user_id]
                break
        
        if not user_config:
            raise ValueError(f"Usuário {user_id} não encontrado")
        
        status, response = await self.make_request(
            "POST", "/scrape",
            user_config["api_key"],
            {
                "url": "https://httpbin.org/json",
                "knowledge_base_id": user_config["kb"],
                "limit": 1
            }
        )
        
        if status == 200:
            task_id = response["id"]
            if user_id not in self.created_tasks:
                self.created_tasks[user_id] = []
            self.created_tasks[user_id].append(task_id)
            return task_id
        else:
            raise Exception(f"Falha ao criar tarefa para {user_id}: {status} - {response}")
    
    async def test_basic_isolation(self):
        """Teste 1: Isolamento básico entre tenants."""
        print("=== Teste 1: Isolamento Básico Entre Tenants ===")
        
        # Criar tarefas para cada usuário
        user_tasks = {}
        for tenant_id, tenant_data in TENANTS.items():
            for user_id in tenant_data["users"]:
                try:
                    task_id = await self.create_task_for_user(user_id, tenant_data)
                    user_tasks[user_id] = task_id
                    print(f"✅ Tarefa criada para {user_id}: {task_id}")
                except Exception as e:
                    print(f"❌ Erro ao criar tarefa para {user_id}: {e}")
                    return
        
        # Testar acesso próprio
        for user_id, task_id in user_tasks.items():
            user_config = None
            for tenant_data in TENANTS.values():
                if user_id in tenant_data["users"]:
                    user_config = tenant_data["users"][user_id]
                    break
            
            status, response = await self.make_request(
                "GET", f"/status/{task_id}", user_config["api_key"]
            )
            
            self.log_test(
                f"{user_id} acessando própria tarefa",
                "Status 200",
                f"Status {status}",
                status == 200,
                f"Task ID: {task_id}"
            )
        
        # Testar acesso cruzado (deve falhar)
        for user_id, task_id in user_tasks.items():
            for other_user_id in user_tasks:
                if user_id != other_user_id:
                    # Verificar se são de tenants diferentes
                    user_tenant = None
                    other_tenant = None
                    
                    for tenant_id, tenant_data in TENANTS.items():
                        if user_id in tenant_data["users"]:
                            user_tenant = tenant_id
                        if other_user_id in tenant_data["users"]:
                            other_tenant = tenant_id
                    
                    if user_tenant != other_tenant:
                        other_user_config = None
                        for tenant_data in TENANTS.values():
                            if other_user_id in tenant_data["users"]:
                                other_user_config = tenant_data["users"][other_user_id]
                                break
                        
                        status, response = await self.make_request(
                            "GET", f"/status/{task_id}", other_user_config["api_key"]
                        )
                        
                        self.log_test(
                            f"{other_user_id} tentando acessar tarefa de {user_id}",
                            "Status 404",
                            f"Status {status}",
                            status == 404,
                            f"Cross-tenant access: {other_tenant} -> {user_tenant}"
                        )
    
    async def test_invalid_scenarios(self):
        """Teste 2: Cenários com dados inválidos."""
        print("=== Teste 2: Cenários com Dados Inválidos ===")
        
        # Teste com API key inválida
        fake_task_id = str(uuid.uuid4())
        status, response = await self.make_request(
            "GET", f"/status/{fake_task_id}", "invalid_api_key_123"
        )
        
        self.log_test(
            "Acesso com API key inválida",
            "Status 401",
            f"Status {status}",
            status == 401,
            "API key: invalid_api_key_123"
        )
        
        # Teste com task ID inexistente (mas API key válida)
        fake_task_id = str(uuid.uuid4())
        status, response = await self.make_request(
            "GET", f"/status/{fake_task_id}", "test_key_123"
        )
        
        self.log_test(
            "Acesso a tarefa inexistente",
            "Status 404",
            f"Status {status}",
            status == 404,
            f"Task ID inexistente: {fake_task_id}"
        )
    
    async def test_stats_isolation(self):
        """Teste 3: Isolamento de estatísticas entre tenants."""
        print("=== Teste 3: Isolamento de Estatísticas ===")
        
        stats_by_user = {}
        
        for tenant_id, tenant_data in TENANTS.items():
            for user_id, user_config in tenant_data["users"].items():
                status, response = await self.make_request(
                    "GET", "/stats", user_config["api_key"]
                )
                
                if status == 200:
                    stats_by_user[user_id] = response
                    self.log_test(
                        f"Obter estatísticas para {user_id}",
                        "Status 200",
                        f"Status {status}",
                        status == 200,
                        f"Tenant: {response.get('user_info', {}).get('tenant_id', 'N/A')}"
                    )
                else:
                    self.log_test(
                        f"Obter estatísticas para {user_id}",
                        "Status 200",
                        f"Status {status}",
                        False,
                        f"Erro: {response}"
                    )
        
        # Verificar se usuários do mesmo tenant têm estatísticas do mesmo tenant
        for tenant_id, tenant_data in TENANTS.items():
            tenant_users = list(tenant_data["users"].keys())
            if len(tenant_users) > 1:
                user1_stats = stats_by_user.get(tenant_users[0], {})
                user2_stats = stats_by_user.get(tenant_users[1], {})
                
                user1_tenant = user1_stats.get('user_info', {}).get('tenant_id')
                user2_tenant = user2_stats.get('user_info', {}).get('tenant_id')
                
                self.log_test(
                    f"Usuários do mesmo tenant têm mesmo tenant_id",
                    f"Ambos: {tenant_id}",
                    f"{tenant_users[0]}: {user1_tenant}, {tenant_users[1]}: {user2_tenant}",
                    user1_tenant == user2_tenant == tenant_id,
                    f"Verificando {tenant_users[0]} e {tenant_users[1]}"
                )
    
    async def test_concurrent_access(self):
        """Teste 4: Acesso concorrente entre tenants."""
        print("=== Teste 4: Acesso Concorrente ===")
        
        # Criar múltiplas tarefas simultaneamente
        tasks = []
        for i in range(3):
            tasks.append(self.create_task_for_user("user1", TENANTS["tenant_1"]))
            tasks.append(self.create_task_for_user("user3", TENANTS["tenant_2"]))
        
        try:
            created_task_ids = await asyncio.gather(*tasks)
            
            self.log_test(
                "Criação concorrente de tarefas",
                "6 tarefas criadas",
                f"{len(created_task_ids)} tarefas criadas",
                len(created_task_ids) == 6,
                f"Task IDs: {created_task_ids}"
            )
            
            # Verificar que cada usuário só vê suas próprias tarefas
            user1_tasks = [tid for i, tid in enumerate(created_task_ids) if i % 2 == 0]
            user3_tasks = [tid for i, tid in enumerate(created_task_ids) if i % 2 == 1]
            
            # User1 tentando acessar tarefas do User3
            for task_id in user3_tasks:
                status, response = await self.make_request(
                    "GET", f"/status/{task_id}", "test_key_123"
                )
                
                self.log_test(
                    f"User1 tentando acessar tarefa concorrente do User3",
                    "Status 404",
                    f"Status {status}",
                    status == 404,
                    f"Task ID: {task_id}"
                )
                
        except Exception as e:
            self.log_test(
                "Criação concorrente de tarefas",
                "Sucesso",
                f"Erro: {str(e)}",
                False,
                str(e)
            )
    
    def print_summary(self):
        """Imprime resumo dos testes."""
        print("\n" + "="*60)
        print("RESUMO DOS TESTES DE ISOLAMENTO")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total de testes: {total_tests}")
        print(f"✅ Passou: {passed_tests}")
        print(f"❌ Falhou: {failed_tests}")
        print(f"Taxa de sucesso: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n🚨 TESTES QUE FALHARAM:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}")
                    print(f"    Esperado: {result['expected']}")
                    print(f"    Obtido: {result['actual']}")
                    if result["details"]:
                        print(f"    Detalhes: {result['details']}")
        else:
            print("\n🎉 TODOS OS TESTES PASSARAM!")
            print("✅ O isolamento multi-tenant está funcionando corretamente.")
        
        print("\n" + "="*60)
    
    async def run_all_tests(self):
        """Executa todos os testes de isolamento."""
        print("🔒 INICIANDO TESTES ABRANGENTES DE ISOLAMENTO MULTI-TENANT")
        print("="*60)
        
        await self.test_basic_isolation()
        await self.test_invalid_scenarios()
        await self.test_stats_isolation()
        await self.test_concurrent_access()
        
        self.print_summary()

async def main():
    tester = IsolationTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())