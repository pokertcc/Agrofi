"""
AgroFi Protocol - Módulo de Gestão da Equipe de Agentes
Fornece utilitários para consultar a equipe, listar tarefas e registrar mudanças no backlog.
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

AGENTS_DIR = Path(__file__).resolve().parent
MANIFEST_FILE = AGENTS_DIR / "squad_manifest.json"
BACKLOG_FILE = AGENTS_DIR / "changes_backlog.json"


class AgroFiTeamManager:
    """Gerenciador central da equipe de agentes multidisciplinares do AgroFi."""

    def __init__(self):
        self.manifest_file = MANIFEST_FILE
        self.backlog_file = BACKLOG_FILE

    def get_manifest(self) -> Dict[str, Any]:
        with open(self.manifest_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_backlog(self) -> Dict[str, Any]:
        with open(self.backlog_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        manifest = self.get_manifest()
        for agent in manifest.get("agents", []):
            if agent.get("id") == agent_id:
                return agent
        return None

    def list_agents(self) -> List[Dict[str, Any]]:
        return self.get_manifest().get("agents", [])

    def get_tasks_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        backlog = self.get_backlog()
        tasks = []
        for change in backlog.get("changes", []):
            if change.get("lead_agent_id") == agent_id or agent_id in change.get("support_agents", []):
                tasks.append(change)
        return tasks

    def add_change(
        self,
        title: str,
        lead_agent_id: str,
        description: str,
        priority: str = "Média",
        category: str = "Geral",
        version_target: str = "v1.2.0",
        affected_files: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        backlog = self.get_backlog()
        new_id = f"CHG-{len(backlog.get('changes', [])) + 1:03d}"
        
        new_change = {
            "id": new_id,
            "title": title,
            "category": category,
            "version_target": version_target,
            "status": "Planejado",
            "priority": priority,
            "progress_pct": 0,
            "lead_agent_id": lead_agent_id,
            "support_agents": [],
            "description": description,
            "affected_files": affected_files or [],
            "acceptance_criteria": acceptance_criteria or ["Especificação técnica validada pelo Agente Líder"]
        }
        
        backlog["changes"].append(new_change)
        
        # Recalcular sumário
        changes = backlog["changes"]
        backlog["summary"] = {
            "total_changes": len(changes),
            "completed": sum(1 for c in changes if c.get("status") == "Concluído"),
            "in_progress": sum(1 for c in changes if c.get("status") == "Em Progresso"),
            "in_review": sum(1 for c in changes if c.get("status") == "Em Revisão"),
            "planned": sum(1 for c in changes if c.get("status") == "Planejado")
        }
        
        with open(self.backlog_file, "w", encoding="utf-8") as f:
            json.dump(backlog, f, indent=2, ensure_ascii=False)
            
        return new_change


# Instância global para importação
team_manager = AgroFiTeamManager()

if __name__ == "__main__":
    print(f"👥 AgroFi Squad: {len(team_manager.list_agents())} agentes registrados.")
    for a in team_manager.list_agents():
        tasks = team_manager.get_tasks_for_agent(a['id'])
        print(f" - {a['icon']} {a['name']} ({a['title']}): {len(tasks)} tarefa(s)")
