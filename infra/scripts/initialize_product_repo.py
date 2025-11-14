#!/usr/bin/env python3
"""
Script para inicializar repositorio base de productos SHARED
- Crea carpeta /opt/proyectos/{producto}-system/
- Inicializa Git
- Crea repo privado en GitHub
- Push inicial
"""

import os
import sys
import subprocess
import requests


class ProductRepoInitializer:
    def __init__(self, product_name):
        self.product_name = product_name
        self.project_path = f"/opt/proyectos/{product_name}-system"
        
        # GitHub config
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME', 'kritaar')
        self.repo_name = f"{product_name}-system"
        
    def log(self, message):
        print(f"[INIT] {message}")
    
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
    
    def create_project_folder(self):
        """Crea carpeta del proyecto"""
        self.log(f"Creando carpeta {self.project_path}")
        os.makedirs(self.project_path, exist_ok=True)
        
        # Crear README.md básico
        readme_content = f"""# {self.product_name.upper()} System

Sistema base compartido para todos los workspaces de tipo {self.product_name}.

## Estructura

Agrega aquí tu código (Django, Flask, FastAPI, etc)

## Deployment

Este código es usado por todos los workspaces SHARED de {self.product_name}.
Cualquier cambio aquí afecta a todos los clientes compartidos.
"""
        readme_path = os.path.join(self.project_path, 'README.md')
        with open(readme_path, 'w') as f:
            f.write(readme_content)
        
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
        gitignore_path = os.path.join(self.project_path, '.gitignore')
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        self.log("Carpeta creada con README.md y .gitignore")
    
    def initialize_git(self):
        """Inicializa repositorio Git"""
        self.log("Inicializando Git...")
        
        self.run_command("git init", cwd=self.project_path)
        self.run_command("git config user.name 'Tenant Master'", cwd=self.project_path)
        self.run_command("git config user.email 'deploy@surgir.online'", cwd=self.project_path)
        self.run_command("git add .", cwd=self.project_path)
        self.run_command('git commit -m "Initial commit - Repositorio base"', cwd=self.project_path)
        
        self.log("Git inicializado")
    
    def create_github_repo(self):
        """Crea repositorio privado en GitHub"""
        self.log(f"Creando repo privado en GitHub: {self.repo_name}")
        
        if not self.github_token:
            self.log("⚠️ GITHUB_TOKEN no configurado")
            return None
        
        url = "https://api.github.com/user/repos"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "name": self.repo_name,
            "description": f"Código base compartido para {self.product_name}",
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
        
        try:
            self.run_command(f"git remote add origin {repo_url}", cwd=self.project_path)
        except:
            self.run_command(f"git remote set-url origin {repo_url}", cwd=self.project_path)
        
        try:
            self.run_command("git branch -M main", cwd=self.project_path)
            self.run_command("git push -u origin main --force", cwd=self.project_path)
            self.log("✅ Push exitoso")
        except Exception as e:
            self.log(f"⚠️ Error en push: {e}")
    
    def initialize(self):
        """Ejecuta todo el proceso de inicialización"""
        try:
            self.log(f"=== INICIALIZANDO REPOSITORIO: {self.product_name} ===")
            
            # 1. Crear carpeta
            self.create_project_folder()
            
            # 2. Git init
            self.initialize_git()
            
            # 3. Crear repo en GitHub
            repo_url = self.create_github_repo()
            
            # 4. Push a GitHub
            if repo_url:
                self.push_to_github(repo_url)
            
            self.log(f"=== INICIALIZACIÓN COMPLETADA ===")
            
            return {
                'success': True,
                'path': self.project_path,
                'repo_url': repo_url or ''
            }
            
        except Exception as e:
            self.log(f"❌ ERROR EN INICIALIZACIÓN: {e}")
            return {
                'success': False,
                'error': str(e)
            }


def main():
    if len(sys.argv) < 2:
        print("Uso: initialize_product_repo.py <product_name>")
        sys.exit(1)
    
    product_name = sys.argv[1]
    
    initializer = ProductRepoInitializer(product_name)
    result = initializer.initialize()
    
    # Output JSON
    import json
    print("\n=== RESULT ===")
    print(json.dumps(result))
    
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
