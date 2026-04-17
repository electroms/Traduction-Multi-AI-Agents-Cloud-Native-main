"""Blog Agent - Service de génération de blog avec SDK GitHub Copilot

Ce module implémente un agent de génération de contenu de blog en utilisant :
- CopilotClient du SDK GitHub Copilot (agrégateur AI)
- Sidecar Skill Server pour la synchronisation des compétences (SKILL.md)
- API FastAPI pour l'exposition des endpoints REST

Architecture :
- Lit les compétences depuis un volume partagé (partagé avec le skill-server)
- Écrit les fichiers de blog générés dans un dossier partagé `blog/`
- Fonctionne en conteneur sidecar (génération de contenu dédiée)
"""

import os
import logging
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType
import httpx

# Chargement des variables d'environnement depuis .env (si présent)
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configs de base du conteneur et du service
AGENT_PORT = int(os.getenv("AGENT_PORT", "8001"))
SKILL_SERVER_URL = os.getenv("SKILL_SERVER_URL", "http://127.0.0.1:8002")
WORK_DIR = os.getcwd()
# Répertoire attendu du fichier SKILL.md synchronisé depuis skill-server sidecar
SKILLS_DIR = os.getenv("SKILLS_DIR", os.path.join(WORK_DIR, ".copilot_skills/blog/SKILL.md"))
# Répertoire où les articles générés seront stockés
BLOG_DIR = os.path.join(WORK_DIR, "blog")

# Copilot client initialisé plus tard dans le cycle de vie
copilot_client: Optional[CopilotClient] = None


definir
async def wait_for_skill_server(url: str, retries: int = 30, delay: float = 2.0):
    """Attendre que le skill-server soit prêt et accessible."""
    async with httpx.AsyncClient() as client:
        for i in range(retries):
            try:
                resp = await client.get(f"{url}/health", timeout=5.0)
                if resp.status_code == 200:
                    logger.info(f"✅ Skill server opérationnel à {url}")
                    return True
            except Exception:
                pass

            logger.info(f"⏳ En attente du skill server... ({i + 1}/{retries})")
            await asyncio.sleep(delay)

    raise RuntimeError(f"Le skill server à {url} n'est pas sain après {retries} tentatives")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application FastAPI."""
    global copilot_client, BLOG_DIR

    logger.info("🚀 Démarrage du Blog Agent (Copilot Sidecar)...")
    logger.info(f"Répertoire de travail : {WORK_DIR}")
    logger.info(f"Répertoire des compétences : {SKILLS_DIR}")
    logger.info(f"Répertoire des blogs : {BLOG_DIR}")
    logger.info(f"URL du skill server : {SKILL_SERVER_URL}")

    try:
        # Création du dossier de sortie si nécessaire
        if not os.path.exists(BLOG_DIR):
            os.makedirs(BLOG_DIR, exist_ok=True)
            logger.info(f"✅ Dossier blog créé : {BLOG_DIR}")
        else:
            logger.info(f"✅ Dossier blog déjà existant : {BLOG_DIR}")

        # Attendre le démarrage du sidecar skill-server
        await wait_for_skill_server(SKILL_SERVER_URL)

        skill_path = Path(SKILLS_DIR)
        if skill_path.exists():
            logger.info(f"✅ Fichier SKILL trouvé à : {SKILLS_DIR}")
        else:
            logger.warning(f"⚠️  SKILL non présent, demande de synchronisation...")
            async with httpx.AsyncClient() as client:
                await client.post(f"{SKILL_SERVER_URL}/sync", timeout=10.0)
            await asyncio.sleep(1)

        # Initialisation du client Copilot
        copilot_client = CopilotClient()
        await copilot_client.start()
        logger.info("✅ Blog Agent initialisé avec succès")

    except Exception as e:
        logger.error(f"❌ Échec de l'initialisation du Blog Agent : {e}")
        raise

    yield

    logger.info("🛑 Arrêt du Blog Agent...")
    if copilot_client:
        await copilot_client.stop()


# Déclaration de l'application FastAPI
app = FastAPI(
    title="Blog Agent",
    description="Agent de génération de blog basé sur GitHub Copilot SDK et DeepSearch",
    version="1.0.0",
    lifespan=lifespan
)


class TaskRequest(BaseModel):
    """Modèle de requête POST /task"""
    task: str
    user_id: Optional[str] = "anonymous"


class TaskResponse(BaseModel):
    """Modèle de réponse pour les tâches exécutées"""
    result: str
    agent: str = "blog_agent"
    blog_path: Optional[str] = None
    download_url: Optional[str] = None


@app.get("/")
async def root():
    """Point d'entrée pour vérifier que l'agent est en ligne."""
    return {
        "agent": "blog_agent",
        "status": "running",
        "capabilities": ["blog_generation", "technical_writing", "content_research"],
        "skills": ["blog_skill_with_deepsearch"]
    }


@app.get("/health")
async def health():
    """Endpoint de santé qui vérifie la disponibilité du skill server."""
    if copilot_client is None:
        raise HTTPException(status_code=503, detail="Agent non initialisé")

    skill_healthy = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SKILL_SERVER_URL}/health", timeout=3.0)
            skill_healthy = resp.status_code == 200
    except Exception:
        pass

    return {"status": "healthy", "skill_server": "healthy" if skill_healthy else "unreachable"}


@app.get("/blog/{filename}")
async def download_blog(filename: str):
    """Télécharge un article de blog existant via son nom de fichier."""
    file_path = Path(BLOG_DIR) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier blog '{filename}' introuvable")

    if file_path.suffix != ".md":
        raise HTTPException(status_code=400, detail="Seuls les fichiers .md sont autorisés")

    return FileResponse(path=str(file_path), filename=filename, media_type="text/markdown")


@app.get("/blogs")
async def list_blogs():
    """Liste tous les articles de blog générés dans le dossier blog."""
    try:
        blog_files = list(Path(BLOG_DIR).glob("blog-*.md"))
        blogs = []
        for blog_file in sorted(blog_files, reverse=True):
            blogs.append({
                "filename": blog_file.name,
                "download_url": f"/blog/{blog_file.name}",
                "size": blog_file.stat().st_size,
                "modified": datetime.fromtimestamp(blog_file.stat().st_mtime).isoformat()
            })
        return {"blogs": blogs, "total": len(blogs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur listage blogs : {str(e)}")


@app.post("/task", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """Exécute la tâche de génération de blog en utilisant le CopilotClient."""
    if copilot_client is None:
        raise HTTPException(status_code=503, detail="Agent non initialisé")

    logger.info(f"📝 Tâche de {request.user_id} : {request.task}")

    try:
        session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "streaming": True,
            "skill_directories": [SKILLS_DIR]
        })

        logger.info(f"✓ Session créée (ID : {session.session_id})")

        response_chunks = []

        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                response_chunks.append(event.data.delta_content)

        session.on(handle_event)

        enhanced_prompt = f"""
{request.task}

Veuillez suivre les directives du Blog Skill :
1. Utiliser DeepSearch pour rechercher chaque section en profondeur
2. Rédiger en tant qu'évangéliste technique : engageant, inspirant, enthousiaste
3. Inclure des exemples de code pratiques
4. Sauvegarder l'article sous blog-{datetime.now().strftime('%Y-%m-%d')}.md dans le dossier blog
5. Ajouter les métadonnées, optimisation SEO et citations nécessaires
"""

        await session.send_and_wait({"prompt": enhanced_prompt}, timeout=600)

        response_text = ''.join(response_chunks)

        # Rechercher le fichier de blog généré le plus récent
        blog_path = None
        download_url = None
        try:
            blog_files = list(Path(BLOG_DIR).glob("blog-*.md"))
            if blog_files:
                latest_blog = max(blog_files, key=lambda p: p.stat().st_mtime)
                blog_path = str(latest_blog.absolute())
                download_url = f"/blog/{latest_blog.name}"
                logger.info(f"📄 Blog généré : {blog_path}")
        except Exception as e:
            logger.warning(f"Impossible de déterminer le chemin du blog : {e}")

        logger.info(f"✅ Tâche terminée pour {request.user_id}")

        return TaskResponse(
            result=response_text if response_text else "Article généré avec succès. Vérifiez le dossier blog.",
            agent="blog_agent",
            blog_path=blog_path,
            download_url=download_url
        )

    except Exception as e:
        logger.error(f"❌ Erreur exécution tâche : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur exécution tâche : {str(e)}")


if __name__ == "__main__":
    # Le démarrage direct n’est pas requis quand on utilise uvicorn.
    pass
    import uvicorn

    logger.info(f"📝 Starting Blog Agent on port {AGENT_PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=AGENT_PORT,
        log_level="info"
    )
