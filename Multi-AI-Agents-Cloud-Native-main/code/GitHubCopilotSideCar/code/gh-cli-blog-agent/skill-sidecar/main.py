"""Skill Server - Sidecar de gestion des compétences de blog

Fournit la gestion des compétences dans un conteneur sidecar dédié :
- Sert le contenu SKILL.md via une API REST
- Synchronise les compétences vers un volume partagé pour Copilot Client
- Permet la consultation dynamique des compétences et leur récupération

Architecture :
- Lit les définitions de compétences depuis le point de montage ConfigMap (/skills-source)
- Écrit les compétences dans le volume partagé (/skills-shared) utilisé par le copilot-agent
- Expose une API REST sur le port 8002 pour la gestion des compétences
"""

import os
import shutil
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SKILL_PORT = int(os.getenv("SKILL_PORT", "8002"))
# Point de montage ConfigMap (source en lecture seule)
SKILLS_SOURCE_DIR = os.getenv("SKILLS_SOURCE_DIR", "/skills-source")
# Point de montage du volume partagé (écriture autorisée, partagé avec copilot-agent)
SKILLS_SHARED_DIR = os.getenv("SKILLS_SHARED_DIR", "/skills-shared")


def sync_skills():
    """Copie les fichiers de compétences du source ConfigMap vers le volume partagé."""
    source = Path(SKILLS_SOURCE_DIR)
    dest = Path(SKILLS_SHARED_DIR) / "blog"
    dest.mkdir(parents=True, exist_ok=True)

    synced = 0
    for skill_file in source.iterdir():
        if skill_file.is_file():
            target = dest / skill_file.name
            shutil.copy2(str(skill_file), str(target))
            logger.info(f"Synced skill: {skill_file.name} -> {target}")
            synced += 1

    logger.info(f"Synced {synced} skill file(s) to {dest}")
    return synced


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Skill Server...")
    logger.info(f"Skills Source: {SKILLS_SOURCE_DIR}")
    logger.info(f"Skills Shared: {SKILLS_SHARED_DIR}")

    count = sync_skills()
    logger.info(f"✅ Skill Server initialized, {count} skills synced")

    yield

    logger.info("🛑 Shutting down Skill Server...")


app = FastAPI(
    title="Skill Server",
    description="Blog Skill Management Sidecar - Provides skill files for Copilot Agent",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "skill-server"}


@app.get("/skills")
async def list_skills():
    """List all available skills."""
    source = Path(SKILLS_SOURCE_DIR)
    skills = []
    for f in sorted(source.iterdir()):
        if f.is_file():
            skills.append({
                "name": f.stem,
                "filename": f.name,
                "size": f.stat().st_size,
                "url": f"/skill/{f.name}",
            })
    return {"skills": skills, "total": len(skills)}


@app.get("/skill/{filename}")
async def get_skill(filename: str):
    """Get skill content by filename."""
    file_path = Path(SKILLS_SOURCE_DIR) / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Skill '{filename}' not found")
    return {"filename": filename, "content": file_path.read_text(encoding="utf-8")}


@app.post("/sync")
async def trigger_sync():
    """Manually trigger a skill sync from source to shared volume."""
    count = sync_skills()
    return {"synced": count, "message": f"Synced {count} skill file(s)"}


if __name__ == "__main__":
    logger.info(f"📚 Starting Skill Server on port {SKILL_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SKILL_PORT, log_level="info")
