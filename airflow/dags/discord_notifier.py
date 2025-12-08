"""
🔔 DISCORD NOTIFIER - Envia notificações formatadas para o Discord
===================================================================

Funções para enviar notificações ricas (embeds) para o Discord via webhook.
Usado pelo Streaming Supervisor para alertar sobre eventos importantes.

Tipos de notificações:
- ✅ Jobs iniciados com sucesso
- ⚠️ Jobs reiniciados após falha
- ❌ Falhas críticas
- 📊 Status geral do cluster
"""

import requests
import json
from datetime import datetime


# Webhook do Discord
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1447677762252046417/oVsnCG8DHcmE17solRpRtOHpLVwo8d_G0pE0JiEQ-MIQrUk-mPVR8Zvi-9jvK7zb2uj4"

# Cores para diferentes tipos de mensagens (formato decimal)
COLOR_SUCCESS = 3066993   # Verde (0x2ecc71)
COLOR_WARNING = 16776960  # Amarelo (0xffff00)
COLOR_ERROR = 15158332    # Vermelho (0xe74c3c)
COLOR_INFO = 3447003      # Azul (0x3498db)


def send_discord_notification(webhook_url, embeds, username="🤖 Spark Supervisor", content=None):
    """
    Envia notificação para o Discord usando webhook.
    
    Args:
        webhook_url: URL do webhook do Discord
        embeds: Lista de embeds (dicionários)
        username: Nome do bot
        content: Mensagem de texto simples (opcional)
    """
    payload = {
        "username": username,
        "embeds": embeds if isinstance(embeds, list) else [embeds]
    }
    
    if content:
        payload["content"] = content
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar notificação Discord: {e}")
        return False


def notify_jobs_started(jobs_info, cluster_status):
    """
    Notifica que jobs foram iniciados com sucesso.
    
    Args:
        jobs_info: Lista de dicionários com info dos jobs iniciados
        cluster_status: Dicionário com status do cluster
    """
    timestamp = datetime.now().isoformat()
    
    # Calcula recursos usados
    total_cores = cluster_status.get('total_cores', 0)
    cores_used = cluster_status.get('cores_used', 0)
    usage_percent = (cores_used * 100 // total_cores) if total_cores > 0 else 0
    
    # Cria descrição dos jobs
    jobs_description = ""
    for job in jobs_info:
        jobs_description += f"• **{job['name']}**\n"
        jobs_description += f"  └ Cores: {job['cores']} | Memória: {job['memory']}\n"
    
    embed = {
        "title": "🚀 Jobs de Streaming Iniciados",
        "description": f"{len(jobs_info)} job(s) iniciado(s) com sucesso",
        "color": COLOR_SUCCESS,
        "fields": [
            {
                "name": "📋 Jobs Iniciados",
                "value": jobs_description or "Nenhum job iniciado",
                "inline": False
            },
            {
                "name": "💻 Recursos do Cluster",
                "value": f"**Cores:** {cores_used}/{total_cores} ({usage_percent}%)\n"
                         f"**Workers:** {cluster_status.get('alive_workers', 0)}",
                "inline": True
            },
            {
                "name": "⚙️ Configuração",
                "value": f"**Limite:** 60% (6 cores)\n"
                         f"**Reserva batch:** 40% (4 cores)",
                "inline": True
            }
        ],
        "footer": {
            "text": "Spark Fraud Detection Pipeline"
        },
        "timestamp": timestamp
    }
    
    send_discord_notification(DISCORD_WEBHOOK_URL, embed)


def notify_jobs_already_running(jobs_running, cluster_status):
    """
    Notifica que todos os jobs já estão rodando (check de saúde OK).
    
    Args:
        jobs_running: Lista de nomes dos jobs rodando
        cluster_status: Dicionário com status do cluster
    """
    timestamp = datetime.now().isoformat()
    
    total_cores = cluster_status.get('total_cores', 0)
    cores_used = cluster_status.get('cores_used', 0)
    usage_percent = (cores_used * 100 // total_cores) if total_cores > 0 else 0
    
    embed = {
        "title": "✅ Streaming Health Check",
        "description": "Todos os jobs estão rodando normalmente",
        "color": COLOR_INFO,
        "fields": [
            {
                "name": "📊 Jobs Ativos",
                "value": "\n".join([f"• {job}" for job in jobs_running]) or "Nenhum",
                "inline": False
            },
            {
                "name": "💻 Cluster Status",
                "value": f"**Cores:** {cores_used}/{total_cores} ({usage_percent}%)\n"
                         f"**Workers:** {cluster_status.get('alive_workers', 0)}\n"
                         f"**Apps:** {cluster_status.get('active_apps', 0)}",
                "inline": True
            }
        ],
        "footer": {
            "text": "Verificação a cada 5 minutos"
        },
        "timestamp": timestamp
    }
    
    # Envia apenas se for uma situação especial (não enviar a cada 5 min)
    # Pode ser ativado para debug
    # send_discord_notification(DISCORD_WEBHOOK_URL, embed)


def notify_job_failure(job_name, error_message, cluster_status, attempted_restart=False):
    """
    Notifica falha crítica de um job.
    
    Args:
        job_name: Nome do job que falhou
        error_message: Mensagem de erro
        cluster_status: Status do cluster
        attempted_restart: Se tentou reiniciar
    """
    timestamp = datetime.now().isoformat()
    
    title = "❌ Falha Crítica no Streaming" if not attempted_restart else "⚠️ Job Reiniciado Após Falha"
    color = COLOR_ERROR if not attempted_restart else COLOR_WARNING
    
    embed = {
        "title": title,
        "description": f"O job **{job_name}** apresentou falha",
        "color": color,
        "fields": [
            {
                "name": "🔴 Job Afetado",
                "value": f"**{job_name}**",
                "inline": True
            },
            {
                "name": "📊 Status Cluster",
                "value": f"**Cores livres:** {cluster_status.get('cores_free', 0)}\n"
                         f"**Workers:** {cluster_status.get('alive_workers', 0)}",
                "inline": True
            },
            {
                "name": "💥 Erro",
                "value": f"```{error_message[:1000]}```",  # Limita tamanho
                "inline": False
            }
        ],
        "footer": {
            "text": "Verificar logs do Spark Master para mais detalhes"
        },
        "timestamp": timestamp
    }
    
    if attempted_restart:
        embed["fields"].append({
            "name": "🔄 Ação Tomada",
            "value": "Tentativa automática de reiniciar o job",
            "inline": False
        })
    
    send_discord_notification(DISCORD_WEBHOOK_URL, embed, content="@here" if not attempted_restart else None)


def notify_cluster_unhealthy(cluster_status, reason):
    """
    Notifica que o cluster Spark está com problemas.
    
    Args:
        cluster_status: Status do cluster
        reason: Motivo do problema
    """
    timestamp = datetime.now().isoformat()
    
    embed = {
        "title": "🚨 Cluster Spark com Problemas",
        "description": "O cluster Spark não está saudável",
        "color": COLOR_ERROR,
        "fields": [
            {
                "name": "⚠️ Problema Detectado",
                "value": reason,
                "inline": False
            },
            {
                "name": "📊 Status Atual",
                "value": f"**Workers ativos:** {cluster_status.get('alive_workers', 0)}\n"
                         f"**Cores totais:** {cluster_status.get('total_cores', 0)}\n"
                         f"**Apps ativos:** {cluster_status.get('active_apps', 0)}",
                "inline": True
            },
            {
                "name": "🔧 Ação Necessária",
                "value": "Verificar status dos containers:\n"
                         "```\n"
                         "docker ps\n"
                         "docker logs fraud_spark_master\n"
                         "```",
                "inline": False
            }
        ],
        "footer": {
            "text": "Os jobs de streaming podem estar parados"
        },
        "timestamp": timestamp
    }
    
    send_discord_notification(DISCORD_WEBHOOK_URL, embed, content="@here")


def notify_supervisor_execution(status, jobs_started=None, jobs_failed=None, cluster_status=None):
    """
    Notifica resultado da execução do supervisor.
    
    Args:
        status: 'success', 'partial', 'failed'
        jobs_started: Lista de jobs iniciados
        jobs_failed: Lista de jobs que falharam
        cluster_status: Status do cluster
    """
    timestamp = datetime.now().isoformat()
    
    if status == 'success':
        color = COLOR_SUCCESS
        title = "✅ Supervisor Executado com Sucesso"
        description = "Todos os jobs estão rodando normalmente"
    elif status == 'partial':
        color = COLOR_WARNING
        title = "⚠️ Execução Parcial do Supervisor"
        description = "Alguns jobs foram iniciados, mas outros falharam"
    else:
        color = COLOR_ERROR
        title = "❌ Falha na Execução do Supervisor"
        description = "Não foi possível garantir todos os jobs rodando"
    
    fields = []
    
    if jobs_started:
        fields.append({
            "name": "✅ Jobs Iniciados",
            "value": "\n".join([f"• {job}" for job in jobs_started]) or "Nenhum",
            "inline": True
        })
    
    if jobs_failed:
        fields.append({
            "name": "❌ Falhas",
            "value": "\n".join([f"• {job}" for job in jobs_failed]) or "Nenhum",
            "inline": True
        })
    
    if cluster_status:
        total_cores = cluster_status.get('total_cores', 0)
        cores_used = cluster_status.get('cores_used', 0)
        usage_percent = (cores_used * 100 // total_cores) if total_cores > 0 else 0
        
        fields.append({
            "name": "💻 Cluster",
            "value": f"**Cores:** {cores_used}/{total_cores} ({usage_percent}%)\n"
                     f"**Workers:** {cluster_status.get('alive_workers', 0)}",
            "inline": True
        })
    
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": fields,
        "footer": {
            "text": "Próxima verificação em 5 minutos"
        },
        "timestamp": timestamp
    }
    
    # Menciona @here apenas em falhas
    content = "@here" if status == 'failed' else None
    send_discord_notification(DISCORD_WEBHOOK_URL, embed, content=content)


# Função de teste
if __name__ == "__main__":
    print("🧪 Testando notificações Discord...")
    
    # Teste 1: Jobs iniciados
    test_jobs = [
        {"name": "streaming_to_postgres", "cores": 4, "memory": "1g"},
        {"name": "streaming_realtime_dashboard", "cores": 2, "memory": "1g"}
    ]
    test_cluster = {
        "alive_workers": 5,
        "total_cores": 10,
        "cores_used": 6,
        "cores_free": 4,
        "active_apps": 2
    }
    
    print("📤 Enviando: Jobs iniciados...")
    notify_jobs_started(test_jobs, test_cluster)
    
    print("✅ Teste concluído! Verifique o Discord.")


# ================================================================
# 🏅 NOTIFICAÇÕES DO BATCH PIPELINE (Medallion)
# ================================================================

def notify_batch_started(dag_run_id, scheduled_time):
    """
    Notifica que o pipeline batch iniciou.
    
    Args:
        dag_run_id: ID da execução da DAG
        scheduled_time: Horário agendado
    """
    timestamp = datetime.now().isoformat()
    
    embed = {
        "title": "🏅 Pipeline Batch Iniciado",
        "description": "O pipeline Medallion (Bronze → Silver → Gold → Postgres) iniciou",
        "color": COLOR_INFO,
        "fields": [
            {
                "name": "📋 Etapas",
                "value": "```\n"
                         "1. 🔧 Preparar recursos (streaming → 40%)\n"
                         "2. 🥉 Bronze - Ingestão de dados brutos\n"
                         "3. 🥈 Silver - Limpeza e transformação\n"
                         "4. 🥇 Gold - Agregações e métricas\n"
                         "5. 🗄️ Postgres - Carregar para BI\n"
                         "6. 🔄 Restaurar streaming (100%)\n"
                         "```",
                "inline": False
            },
            {
                "name": "⚙️ Recursos",
                "value": "**Batch:** 6 cores (60%)\n"
                         "**Streaming:** 4 cores (40%)",
                "inline": True
            },
            {
                "name": "🕐 Agendamento",
                "value": f"**Horário:** {scheduled_time}\n"
                         f"**Run ID:** `{dag_run_id[:20]}...`",
                "inline": True
            }
        ],
        "footer": {
            "text": "Medallion Pipeline - Spark Fraud Detection"
        },
        "timestamp": timestamp
    }
    
    send_discord_notification(DISCORD_WEBHOOK_URL, embed)


def notify_batch_task_completed(task_name, duration_seconds, records_processed=None):
    """
    Notifica que uma etapa do batch foi concluída.
    
    Args:
        task_name: Nome da task (bronze, silver, gold, postgres)
        duration_seconds: Duração em segundos
        records_processed: Número de registros processados (opcional)
    """
    # Mapeia task para emoji e descrição
    task_info = {
        "bronze_ingestion": ("🥉", "Bronze", "Ingestão de dados brutos"),
        "silver_transformation": ("🥈", "Silver", "Limpeza e transformação"),
        "gold_aggregation": ("🥇", "Gold", "Agregações e métricas"),
        "load_to_postgres": ("🗄️", "Postgres", "Carregamento para BI"),
        "prepare_resources": ("🔧", "Recursos", "Preparação de recursos"),
        "restore_resources": ("🔄", "Restaurar", "Restauração de streaming"),
    }
    
    emoji, layer, description = task_info.get(task_name, ("📦", task_name, ""))
    
    # Formata duração
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
    
    # Não notifica cada task individualmente para evitar spam
    # Apenas loga - a notificação final é mais importante
    print(f"✅ {emoji} {layer}: {duration_str}")


def notify_batch_completed(dag_run_id, total_duration_seconds, tasks_status):
    """
    Notifica que o pipeline batch foi concluído com sucesso.
    
    Args:
        dag_run_id: ID da execução
        total_duration_seconds: Duração total em segundos
        tasks_status: Dicionário com status de cada task
    """
    timestamp = datetime.now().isoformat()
    
    # Formata duração total
    minutes = int(total_duration_seconds // 60)
    seconds = int(total_duration_seconds % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
    
    # Cria resumo das tasks
    tasks_summary = ""
    for task_name, status in tasks_status.items():
        emoji = "✅" if status == "success" else "❌"
        task_display = task_name.replace("_", " ").title()
        tasks_summary += f"{emoji} {task_display}\n"
    
    embed = {
        "title": "🎉 Pipeline Batch Concluído!",
        "description": "Todas as etapas do Medallion Pipeline foram executadas com sucesso",
        "color": COLOR_SUCCESS,
        "fields": [
            {
                "name": "📊 Resumo das Etapas",
                "value": f"```\n{tasks_summary}```",
                "inline": False
            },
            {
                "name": "⏱️ Duração Total",
                "value": duration_str,
                "inline": True
            },
            {
                "name": "🔄 Próxima Execução",
                "value": "Amanhã às 00:00",
                "inline": True
            }
        ],
        "footer": {
            "text": f"Run ID: {dag_run_id[:30]}"
        },
        "timestamp": timestamp
    }
    
    send_discord_notification(DISCORD_WEBHOOK_URL, embed)


def notify_batch_failed(dag_run_id, failed_task, error_message, tasks_completed):
    """
    Notifica que o pipeline batch falhou.
    
    Args:
        dag_run_id: ID da execução
        failed_task: Task que falhou
        error_message: Mensagem de erro
        tasks_completed: Lista de tasks que completaram antes da falha
    """
    timestamp = datetime.now().isoformat()
    
    # Mapeia task para nome amigável
    task_names = {
        "bronze_ingestion": "🥉 Bronze - Ingestão",
        "silver_transformation": "🥈 Silver - Transformação",
        "gold_aggregation": "🥇 Gold - Agregação",
        "load_to_postgres": "🗄️ Postgres - Carregamento",
        "prepare_resources": "🔧 Preparar Recursos",
        "restore_resources": "🔄 Restaurar Streaming",
    }
    
    failed_task_name = task_names.get(failed_task, failed_task)
    
    # Cria lista de tasks completadas
    completed_str = "\n".join([f"✅ {task_names.get(t, t)}" for t in tasks_completed]) or "Nenhuma"
    
    embed = {
        "title": "❌ Pipeline Batch Falhou!",
        "description": f"O pipeline parou na etapa: **{failed_task_name}**",
        "color": COLOR_ERROR,
        "fields": [
            {
                "name": "🔴 Task com Falha",
                "value": failed_task_name,
                "inline": True
            },
            {
                "name": "✅ Tasks Completadas",
                "value": completed_str,
                "inline": True
            },
            {
                "name": "💥 Erro",
                "value": f"```\n{error_message[:800]}\n```",
                "inline": False
            },
            {
                "name": "🔧 Ação Automática",
                "value": "Streaming restaurado para 100% (se aplicável)",
                "inline": False
            },
            {
                "name": "📋 Investigar",
                "value": "```\n"
                         "# Ver logs da DAG:\n"
                         "Airflow UI → DAGs → medallion_pipeline → Logs\n\n"
                         "# Ver logs do Spark:\n"
                         "docker logs fraud_spark_master\n"
                         "```",
                "inline": False
            }
        ],
        "footer": {
            "text": f"Run ID: {dag_run_id[:30]}"
        },
        "timestamp": timestamp
    }
    
    send_discord_notification(DISCORD_WEBHOOK_URL, embed, content="@here")
