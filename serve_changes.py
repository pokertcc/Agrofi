"""
AgroFi Protocol - Servidor Localhost da Central de Mudanças & Equipe de Agentes
Porta padrão: 8085 (http://localhost:8085)
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

BASE_DIR = Path(__file__).resolve().parent
AGENTS_MANIFEST = BASE_DIR / "agents" / "squad_manifest.json"
CHANGES_BACKLOG = BASE_DIR / "agents" / "changes_backlog.json"
PORT = 8085


class AgroFiChangesHandler(SimpleHTTPRequestHandler):
    """
    Handler customizado para servir a interface visual de mudanças (changes.html)
    e fornecer APIs REST para leitura e escrita do backlog e agentes.
    """

    def log_message(self, format, *args):
        # Log simplificado
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")
        sys.stdout.flush()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Rota Principal -> changes.html
        if path in ("/", "/index", "/changes", "/changes.html"):
            self.serve_file(BASE_DIR / "changes.html", "text/html; charset=utf-8")
            return

        # API: Lista de Agentes
        elif path == "/api/agents":
            self.send_json_file(AGENTS_MANIFEST)
            return

        # API: Lista de Mudanças
        elif path == "/api/changes":
            self.send_json_file(CHANGES_BACKLOG)
            return

        # API: Status Git
        elif path == "/api/git-status":
            self.serve_git_status()
            return

        # API: Health Check
        elif path == "/api/health":
            self.send_json_response({"status": "online", "port": PORT, "service": "AgroFi Evolution Hub"})
            return

        # Arquivos estáticos normais
        file_path = BASE_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            super().do_GET()
        else:
            self.send_error(404, "Arquivo nao encontrado")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/changes":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                new_change = json.loads(post_data.decode("utf-8"))
                success, msg = self.append_change(new_change)
                if success:
                    self.send_json_response({"success": True, "message": msg, "change": new_change}, status=201)
                else:
                    self.send_json_response({"success": False, "error": msg}, status=400)
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, status=500)
            return

        self.send_error(404, "Endpoint POST desconhecido")

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/changes/"):
            change_id = path.split("/")[-1]
            content_length = int(self.headers.get("Content-Length", 0))
            put_data = self.rfile.read(content_length)
            try:
                update_data = json.loads(put_data.decode("utf-8"))
                success, msg = self.update_change_status(change_id, update_data)
                if success:
                    self.send_json_response({"success": True, "message": msg})
                else:
                    self.send_json_response({"success": False, "error": msg}, status=404)
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, status=500)
            return

        self.send_error(404, "Endpoint PUT desconhecido")

    def serve_file(self, file_path: Path, content_type: str):
        if not file_path.exists():
            self.send_error(404, f"Arquivo {file_path.name} nao encontrado")
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def send_json_file(self, file_path: Path):
        if not file_path.exists():
            self.send_json_response({"error": f"Arquivo {file_path.name} nao encontrado"}, status=404)
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def serve_git_status(self):
        try:
            status_output = subprocess.check_output(
                ["git", "status", "-s"],
                cwd=str(BASE_DIR),
                text=True,
                stderr=subprocess.STDOUT
            )
            branch_output = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=str(BASE_DIR),
                text=True,
                stderr=subprocess.STDOUT
            ).strip()
            self.send_json_response({
                "branch": branch_output or "main",
                "status": status_output or "Nenhum arquivo modificado no momento (repositorio limpo)."
            })
        except Exception as e:
            self.send_json_response({"branch": "local", "status": f"Git indisponivel: {str(e)}"})

    def append_change(self, new_change: dict):
        if not CHANGES_BACKLOG.exists():
            return False, "Arquivo changes_backlog.json nao encontrado"
        try:
            with open(CHANGES_BACKLOG, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["changes"].append(new_change)
            # Atualiza sumario
            total = len(data["changes"])
            completed = sum(1 for c in data["changes"] if c.get("status") == "Concluído")
            in_progress = sum(1 for c in data["changes"] if c.get("status") == "Em Progresso")
            in_review = sum(1 for c in data["changes"] if c.get("status") == "Em Revisão")
            planned = sum(1 for c in data["changes"] if c.get("status") == "Planejado")
            data["summary"] = {
                "total_changes": total,
                "completed": completed,
                "in_progress": in_progress,
                "in_review": in_review,
                "planned": planned
            }
            with open(CHANGES_BACKLOG, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True, "Mudanca registrada com sucesso"
        except Exception as e:
            return False, str(e)

    def update_change_status(self, change_id: str, update_data: dict):
        if not CHANGES_BACKLOG.exists():
            return False, "Arquivo changes_backlog.json nao encontrado"
        try:
            with open(CHANGES_BACKLOG, "r", encoding="utf-8") as f:
                data = json.load(f)
            found = False
            for c in data["changes"]:
                if c.get("id") == change_id:
                    if "status" in update_data:
                        c["status"] = update_data["status"]
                        if update_data["status"] == "Concluído":
                            c["progress_pct"] = 100
                        elif update_data["status"] == "Em Progresso" and c.get("progress_pct", 0) == 0:
                            c["progress_pct"] = 30
                    if "progress_pct" in update_data:
                        c["progress_pct"] = update_data["progress_pct"]
                    found = True
                    break
            if not found:
                return False, f"Mudanca {change_id} nao encontrada"

            # Recomputa sumario
            total = len(data["changes"])
            completed = sum(1 for c in data["changes"] if c.get("status") == "Concluído")
            in_progress = sum(1 for c in data["changes"] if c.get("status") == "Em Progresso")
            in_review = sum(1 for c in data["changes"] if c.get("status") == "Em Revisão")
            planned = sum(1 for c in data["changes"] if c.get("status") == "Planejado")
            data["summary"] = {
                "total_changes": total,
                "completed": completed,
                "in_progress": in_progress,
                "in_review": in_review,
                "planned": planned
            }
            with open(CHANGES_BACKLOG, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True, f"Mudanca {change_id} atualizada"
        except Exception as e:
            return False, str(e)


def run_server(port=PORT):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, AgroFiChangesHandler)
    print("=" * 65)
    print(f"🌱 AgroFi Evolution Hub - Central de Mudancas & Agentes")
    print(f"👉 Acesse a tela em: http://localhost:{port}")
    print(f"📡 API de Agentes:    http://localhost:{port}/api/agents")
    print(f"📋 API de Mudancas:   http://localhost:{port}/api/changes")
    print(f"📂 API de Git Status: http://localhost:{port}/api/git-status")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor finalizado pelo usuario.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
