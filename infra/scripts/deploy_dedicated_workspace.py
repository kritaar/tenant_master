#!/usr/bin/env python3
"""
Script para deployment automático de workspaces dedicados
- Copia código base
- Inicializa Git
- Crea repo privado en GitHub
- Push automático
- Genera docker-compose.yml
"""

import os
import sys
import subprocess
import shutil
import json
import requests
from pathlib import Path


class WorkspaceDeployer:
    def __init__(self, product_name, subdomain, db_name, db_user, db_password):
        self.product_name = product_name
        self.subdomain = subdomain
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        
        # Paths
        self.source_path = f"/opt/proyectos/{product_name}-system"
        self.dest_path = f"/opt/proyectos/{product_name}-system-clients/{subdomain}"
        
        # GitHub config
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME', 'kritaar')
        self.repo_name = f"{product_name}-{subdomain}"
        
    def log(self, message):
        """Print con formato"""
        print(f"[DEPLOY] {message}")
    
    def run_command(self, command, cwd=None):
        """Ejecuta comando shell"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.log(f"Error ejecutando: {command}")
            self.log(f"Error: {e.stderr}")
            raise
    
    def copy_source_code(self):
        """Copia código base a carpeta del cliente"""
        self.log(f"Copiando código de {self.source_path} a {self.dest_path}")
        
        if not os.path.exists(self.source_path):
            raise Exception(f"No existe el código fuente en {self.source_path}")
        
        # Crear carpeta destino
        os.makedirs(os.path.dirname(self.dest_path), exist_ok=True)
        
        # Copiar todo excepto .git
        if os.path.exists(self.dest_path):
            shutil.rmtree(self.dest_path)
        
        shutil.copytree(
            self.source_path,
            self.dest_path,
            ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'venv', 'node_modules')
        )
        
        self.log(f"Código copiado exitosamente")
    
    def initialize_git(self):
        """Inicializa repositorio Git"""
        self.log("Inicializando Git...")
        
        self.run_command("git init", cwd=self.dest_path)
        self.run_command("git config user.name 'Tenant Master'", cwd=self.dest_path)
        self.run_command("git config user.email 'deploy@surgir.online'", cwd=self.dest_path)
        
        # Crear .gitignore
        gitignore_content = """
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.env
.venv
venv/
ENV/
db.sqlite3
*.log
.DS_Store
node_modules/
"""
        gitignore_path = os.path.join(self.dest_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        self.run_command("git add .", cwd=self.dest_path)
        self.run_command('git commit -m "Initial commit - Deployment automático"', cwd=self.dest_path)
        
        self.log("Git inicializado")
    
    def create_github_repo(self):
        """Crea repositorio privado en GitHub"""
        self.log(f"Creando repo privado en GitHub: {self.repo_name}")
        
        if not self.github_token:
            self.log("⚠️ GITHUB_TOKEN no configurado, saltando creación de repo")
            return None
        
        url = "https://api.github.com/user/repos"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "name": self.repo_name,
            "description": f"Workspace dedicado para {self.subdomain}",
            "private": True,
            "auto_init": False
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                repo_data = response.json()
                repo_url = repo_data['clone_url']
                self.log(f"✅ Repo creado: {repo_url}")
                return repo_url
            elif response.status_code == 422:
                # Repo ya existe
                repo_url = f"https://github.com/{self.github_username}/{self.repo_name}.git"
                self.log(f"ℹ️ Repo ya existe: {repo_url}")
                return repo_url
            else:
                self.log(f"❌ Error creando repo: {response.status_code}")
                self.log(response.json())
                return None
        except Exception as e:
            self.log(f"Error conectando a GitHub: {e}")
            return None
    
    def push_to_github(self, repo_url):
        """Push código a GitHub"""
        if not repo_url:
            self.log("No hay repo URL, saltando push")
            return
        
        self.log(f"Haciendo push a {repo_url}")
        
        # Configurar remote
        try:
            self.run_command(f"git remote add origin {repo_url}", cwd=self.dest_path)
        except:
            self.run_command(f"git remote set-url origin {repo_url}", cwd=self.dest_path)
        
        # Push
        try:
            # Cambiar a branch main si es necesario
            self.run_command("git branch -M main", cwd=self.dest_path)
            self.run_command("git push -u origin main --force", cwd=self.dest_path)
            self.log("✅ Push exitoso")
        except Exception as e:
            self.log(f"⚠️ Error en push: {e}")
    
    def generate_docker_compose(self):
        """Genera docker-compose.yml personalizado"""
        self.log("Generando docker-compose.yml")
        
        compose_content = f"""version: '3.8'

services:
  {self.subdomain}-app:
    build: .
    container_name: {self.product_name}-{self.subdomain}
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://{self.db_user}:{self.db_password}@postgres:5432/{self.db_name}
      - DB_NAME={self.db_name}
      - DB_USER={self.db_user}
      - DB_PASSWORD={self.db_password}
      - DB_HOST=postgres
      - DB_PORT=5432
      - SUBDOMAIN={self.subdomain}
    networks:
      - tenant-master-core_default
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{self.subdomain}.rule=Host(`{self.subdomain}.surgir.online`)"
      - "traefik.http.routers.{self.subdomain}.entrypoints=websecure"
      - "traefik.http.routers.{self.subdomain}.tls.certresolver=letsencrypt"
      - "traefik.http.services.{self.subdomain}.loadbalancer.server.port=8000"

networks:
  tenant-master-core_default:
    external: true
"""
        
        compose_path = os.path.join(self.dest_path, 'docker-compose.yml')
        with open(compose_path, 'w') as f:
            f.write(compose_content)
        
        self.log("docker-compose.yml generado")
    
    def deploy(self):
        """Ejecuta todo el proceso de deployment"""
        try:
            self.log(f"=== INICIANDO DEPLOYMENT: {self.subdomain} ===")
            
            # 1. Copiar código
            self.copy_source_code()
            
            # 2. Generar docker-compose
            self.generate_docker_compose()
            
            # 3. Git init
            self.initialize_git()
            
            # 4. Crear repo en GitHub
            repo_url = self.create_github_repo()
            
            # 5. Push a GitHub
            if repo_url:
                self.push_to_github(repo_url)
            
            self.log(f"=== DEPLOYMENT COMPLETADO ===")
            
            return {
                'success': True,
                'path': self.dest_path,
                'repo_url': repo_url or '',
                'compose_path': os.path.join(self.dest_path, 'docker-compose.yml')
            }
            
        except Exception as e:
            self.log(f"❌ ERROR EN DEPLOYMENT: {e}")
            return {
                'success': False,
                'error': str(e)
            }


def main():
    if len(sys.argv) < 6:
        print("Uso: deploy_dedicated_workspace.py <product_name> <subdomain> <db_name> <db_user> <db_password>")
        sys.exit(1)
    
    product_name = sys.argv[1]
    subdomain = sys.argv[2]
    db_name = sys.argv[3]
    db_user = sys.argv[4]
    db_password = sys.argv[5]
    
    deployer = WorkspaceDeployer(product_name, subdomain, db_name, db_user, db_password)
    result = deployer.deploy()
    
    # Output JSON para que Django lo pueda leer
    print("\n=== RESULT ===")
    print(json.dumps(result))
    
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
