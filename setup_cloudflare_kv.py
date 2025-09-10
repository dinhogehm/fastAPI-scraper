#!/usr/bin/env python3
"""
Script para configurar as API keys no Cloudflare KV após o deploy.

Este script deve ser executado uma vez após o deploy para configurar
as chaves de API no Cloudflare KV.

Uso:
    python3 setup_cloudflare_kv.py

Pré-requisitos:
    - wrangler CLI instalado e configurado
    - Worker já deployado
    - KV namespaces criados
"""

import json
import subprocess
import sys
from typing import Dict, Any

# Configuração das API keys
API_KEYS_CONFIG = {
    "test_key_123": {
        "tenant_id": "tenant_1",
        "user_id": "user1",
        "knowledge_bases": ["kb_user1_001"],
        "created_at": "2024-01-15T10:00:00Z",
        "active": True
    },
    "demo_key_456": {
        "tenant_id": "tenant_1",
        "user_id": "user2",
        "knowledge_bases": ["kb_user2_001"],
        "created_at": "2024-01-15T10:00:00Z",
        "active": True
    },
    "prod_key_789": {
        "tenant_id": "tenant_2",
        "user_id": "user3",
        "knowledge_bases": ["kb_user3_001"],
        "created_at": "2024-01-15T10:00:00Z",
        "active": True
    },
    "enterprise_key_abc": {
        "tenant_id": "tenant_3",
        "user_id": "enterprise_user",
        "knowledge_bases": ["kb_enterprise_001", "kb_enterprise_002"],
        "created_at": "2024-01-15T10:00:00Z",
        "active": True
    }
}

def run_wrangler_command(command: list) -> tuple[bool, str]:
    """Executa um comando wrangler e retorna o resultado."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Erro: {e.stderr}"
    except FileNotFoundError:
        return False, "Erro: wrangler CLI não encontrado. Instale com 'npm install -g wrangler'"

def setup_api_keys(worker_name: str = "fastapi-multitenant-scraper") -> bool:
    """Configura as API keys no Cloudflare KV."""
    print("🔧 Configurando API keys no Cloudflare KV...")
    
    success_count = 0
    total_keys = len(API_KEYS_CONFIG)
    
    for api_key, config in API_KEYS_CONFIG.items():
        print(f"📝 Configurando chave: {api_key[:8]}...")
        
        # Preparar dados para o KV
        kv_key = f"key:{api_key}"
        kv_value = json.dumps(config)
        
        # Comando wrangler para inserir no KV
        command = [
            "wrangler", "kv:key", "put",
            kv_key,
            kv_value,
            "--binding", "API_KEYS_KV",
            "--name", worker_name
        ]
        
        success, output = run_wrangler_command(command)
        
        if success:
            print(f"✅ Chave {api_key[:8]}... configurada com sucesso")
            success_count += 1
        else:
            print(f"❌ Erro ao configurar chave {api_key[:8]}...: {output}")
    
    print(f"\n📊 Resultado: {success_count}/{total_keys} chaves configuradas")
    return success_count == total_keys

def verify_kv_setup(worker_name: str = "fastapi-multitenant-scraper") -> bool:
    """Verifica se as chaves foram configuradas corretamente."""
    print("\n🔍 Verificando configuração das chaves...")
    
    # Listar chaves no KV
    command = [
        "wrangler", "kv:key", "list",
        "--binding", "API_KEYS_KV",
        "--name", worker_name
    ]
    
    success, output = run_wrangler_command(command)
    
    if not success:
        print(f"❌ Erro ao listar chaves: {output}")
        return False
    
    try:
        keys_list = json.loads(output)
        configured_keys = [key["name"] for key in keys_list if key["name"].startswith("key:")]
        expected_keys = [f"key:{api_key}" for api_key in API_KEYS_CONFIG.keys()]
        
        print(f"📋 Chaves encontradas: {len(configured_keys)}")
        print(f"📋 Chaves esperadas: {len(expected_keys)}")
        
        missing_keys = set(expected_keys) - set(configured_keys)
        if missing_keys:
            print(f"⚠️  Chaves faltando: {missing_keys}")
            return False
        
        print("✅ Todas as chaves estão configuradas corretamente")
        return True
        
    except json.JSONDecodeError:
        print(f"❌ Erro ao parsear resposta do KV: {output}")
        return False

def create_kv_namespaces(worker_name: str = "fastapi-multitenant-scraper") -> bool:
    """Cria os namespaces KV necessários."""
    print("🏗️  Criando namespaces KV...")
    
    namespaces = ["TASKS_KV", "API_KEYS_KV"]
    
    for namespace in namespaces:
        print(f"📦 Criando namespace: {namespace}")
        
        command = [
            "wrangler", "kv:namespace", "create",
            namespace,
            "--name", worker_name
        ]
        
        success, output = run_wrangler_command(command)
        
        if success:
            print(f"✅ Namespace {namespace} criado")
            print(f"📋 Output: {output.strip()}")
        else:
            if "already exists" in output.lower():
                print(f"ℹ️  Namespace {namespace} já existe")
            else:
                print(f"❌ Erro ao criar namespace {namespace}: {output}")
                return False
    
    print("\n⚠️  IMPORTANTE: Atualize o wrangler.toml com os IDs dos namespaces mostrados acima")
    return True

def main():
    """Função principal."""
    print("🚀 Setup do Cloudflare KV para FastAPI Multi-tenant Scraper")
    print("=" * 60)
    
    # Verificar se wrangler está instalado
    success, output = run_wrangler_command(["wrangler", "--version"])
    if not success:
        print("❌ Wrangler CLI não encontrado. Instale com: npm install -g wrangler")
        sys.exit(1)
    
    print(f"✅ Wrangler encontrado: {output.strip()}")
    
    # Obter nome do worker
    worker_name = input("\n📝 Nome do worker (padrão: fastapi-multitenant-scraper): ").strip()
    if not worker_name:
        worker_name = "fastapi-multitenant-scraper"
    
    # Menu de opções
    while True:
        print("\n📋 Opções disponíveis:")
        print("1. Criar namespaces KV")
        print("2. Configurar API keys")
        print("3. Verificar configuração")
        print("4. Fazer tudo (1 + 2 + 3)")
        print("5. Sair")
        
        choice = input("\n🔢 Escolha uma opção (1-5): ").strip()
        
        if choice == "1":
            create_kv_namespaces(worker_name)
        elif choice == "2":
            setup_api_keys(worker_name)
        elif choice == "3":
            verify_kv_setup(worker_name)
        elif choice == "4":
            print("\n🔄 Executando setup completo...")
            if create_kv_namespaces(worker_name):
                if setup_api_keys(worker_name):
                    verify_kv_setup(worker_name)
                    print("\n🎉 Setup completo finalizado!")
                else:
                    print("\n❌ Falha na configuração das API keys")
            else:
                print("\n❌ Falha na criação dos namespaces")
        elif choice == "5":
            print("\n👋 Saindo...")
            break
        else:
            print("\n❌ Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()