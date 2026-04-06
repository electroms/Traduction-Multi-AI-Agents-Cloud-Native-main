"""Agent PPT - Service de génération PPT avec GitHub Copilot SDK

Cet agent offre des capacités de génération de PPT en intégrant :
- GitHub Copilot SDK pour génération de contenu IA
- Compétence PPT pour création de présentations
- Endpoints FastAPI pour compatibilité protocole A2A

Architecture :
- Utilise CopilotClient du SDK GitHub Copilot
- Expose des endpoints A2A pour découverte
- Peut être appelé par orchestrateur ou autres agents
"""

import os
import logging
import asyncio
import sys
import uuid
from typing import Optional, Any, Dict, List
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from copilot import CopilotClient
from copilot.generated.session_events import SessionEventType

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration globale
AGENT_PORT = int(os.getenv("AGENT_PORT", "8002"))
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8002")
WORK_DIR = os.getcwd()
SKILLS_DIR = os.path.join(WORK_DIR, ".copilot_skills/ppt/SKILL.md")
PPT_DIR = os.path.join(WORK_DIR, "ppt")

# Variables globales
copilot_client: Optional[CopilotClient] = None
current_session = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie de l'application - initialisation du client Copilot au démarrage."""
    global copilot_client, PPT_DIR

    logger.info("?? Démarrage de l'agent PPT...")
    logger.info(f"Répertoire de travail: {WORK_DIR}")
    logger.info(f"Répertoire des compétences: {SKILLS_DIR}")
    logger.info(f"Répertoire PPT: {PPT_DIR}")

    try:
        # Vérifie et crée le dossier ppt si nécessaire
        if not os.path.exists(PPT_DIR):
            os.makedirs(PPT_DIR)
            logger.info(f"? Dossier ppt créé: {PPT_DIR}")
        else:
            logger.info(f"? Dossier ppt existant: {PPT_DIR}")

        # Initialisation du client Copilot
        copilot_client = CopilotClient()
        await copilot_client.start()

        logger.info("? Agent PPT initialisé avec succès")

    except Exception as e:
        logger.error(f"? Échec de l'initialisation de l'agent PPT : {e}")
        raise

    yield

    # Nettoyage à l'arrêt
    logger.info("?? Arrêt de l'agent PPT...")
    if copilot_client:
        await copilot_client.stop()


# Application FastAPI
app = FastAPI(
    title="PPT Agent",
    description="Agent de génération de PPT basé sur GitHub Copilot SDK",
    version="1.0.0",
    lifespan=lifespan
)


class TaskRequest(BaseModel):
    """Modèle de requête pour l'exécution de tâches."""
    task: str
    user_id: Optional[str] = "anonymous"


class TaskResponse(BaseModel):
    """Modèle de réponse pour l'exécution de tâches."""
    result: str
    agent: str = "ppt_agent"
    ppt_path: Optional[str] = None
    download_url: Optional[str] = None


# Modèles A2A JSON-RPC
class A2AMessage(BaseModel):
    """Message du protocole A2A."""
    role: str
    parts: List[Dict[str, Any]]


class A2ATaskParams(BaseModel):
    """Paramètres de tâche A2A."""
    id: Optional[str] = None
    message: A2AMessage


class A2ARequest(BaseModel):
    """Requête JSON-RPC A2A."""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str
    params: Optional[Dict[str, Any]] = None


async def process_a2a_message_streaming(message_text: str, jsonrpc: str, request_id: str, task_id: str, context_id: str):
    """Traite un message A2A et renvoie des événements SSE au fur et à mesure."""
    import json
    global copilot_client

    message_id_working = str(uuid.uuid4())
    message_id_complete = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    # Envoyer un statut 'working' immédiatement
    status_event = {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "contextId": context_id,
            "taskId": task_id,
            "final": False,
            "status": {
                "state": "working",
                "message": {
                    "messageId": message_id_working,
                    "role": "agent",
                    "parts": [{"kind": "text", "text": "Processing your PPT request..."}]
                }
            },
            "kind": "status-update"
        }
    }
    yield f"data: {json.dumps(status_event)}\n\n"

    # Vérifie que le client Copilot est initialisé
    if copilot_client is None:
        error_event = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "result": {
                "contextId": context_id,
                "taskId": task_id,
                "final": True,
                "status": {
                    "state": "failed",
                    "message": {
                        "messageId": str(uuid.uuid4()),
                        "role": "agent",
                        "parts": [{"kind": "text", "text": "Agent not initialized"}]
                    }
                },
                "kind": "status-update"
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"
        return

    try:
        # Créer une session Copilot pour cette tâche
        session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "streaming": True,
            "skill_directories": [SKILLS_DIR]
        })

        logger.info(f"? Session A2A créée avec ID : {session.session_id}")

        # Collecte les fragments de réponse
        response_chunks = []

        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                response_chunks.append(event.data.delta_content)

        session.on(handle_event)

        # Démarre la tâche en arrière-plan
        task = asyncio.create_task(session.send_and_wait({"prompt": message_text}, timeout=600))

        # Envoi de battements de cœur pendant l'attente
        heartbeat_count = 0
        while not task.done():
            await asyncio.sleep(5)  # vérifie toutes les 5 secondes
            heartbeat_count += 1

            heartbeat_event = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "result": {
                    "contextId": context_id,
                    "taskId": task_id,
                    "final": False,
                    "status": {
                        "state": "working",
                        "message": {
                            "messageId": str(uuid.uuid4()),
                            "role": "agent",
                            "parts": [{"kind": "text", "text": f"Still generating PPT... ({heartbeat_count * 5}s elapsed, {len(response_chunks)} chunks received)"}]
                        }
                    },
                    "kind": "status-update"
                }
            }
            yield f"data: {json.dumps(heartbeat_event)}\n\n"

        # Attendre la fin de la tâche et gérer les exceptions
        await task

        # Combiner le texte de réponse
        response_text = ''.join(response_chunks)
        if not response_text:
            response_text = "PPT generation completed successfully."

        # Envoyer l'artefact avec le résultat
        artifact_event = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "result": {
                "contextId": context_id,
                "taskId": task_id,
                "artifact": {
                    "artifactId": artifact_id,
                    "parts": [{
                        "kind": "text",
                        "text": response_text
                    }]
                },
                "kind": "artifact-update"
            }
        }
        yield f"data: {json.dumps(artifact_event)}\n\n"

        # Envoyer le statut de complétion
        complete_event = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "result": {
                "contextId": context_id,
                "taskId": task_id,
                "final": True,
                "status": {
                    "state": "completed",
                    "message": {
                        "messageId": message_id_complete,
                        "role": "agent",
                        "parts": [{"kind": "text", "text": response_text}]
                    }
                },
                "kind": "status-update"
            }
        }
        yield f"data: {json.dumps(complete_event)}\n\n"

    except Exception as e:
        logger.error(f"? Erreur lors du traitement du message A2A : {e}", exc_info=True)
        error_event = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "result": {
                "contextId": context_id,
                "taskId": task_id,
                "final": True,
                "status": {
                    "state": "failed",
                    "message": {
                        "messageId": str(uuid.uuid4()),
                        "role": "agent",
                        "parts": [{"kind": "text", "text": f"Error: {str(e)}"}]
                    }
                },
                "kind": "status-update"
            }
        }
        yield f"data: {json.dumps(error_event)}\n\n"


async def process_a2a_message(message_text: str) -> str:
    """Traite un message A2A et renvoie la réponse (legacy non-streaming)."""
    global copilot_client

    if copilot_client is None:
        return "Agent not initialized"

    try:
        # Créer une session pour la tâche
        session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "streaming": True,
            "skill_directories": [SKILLS_DIR]
        })

        logger.info(f"? Session A2A créée avec ID : {session.session_id}")

        response_chunks = []

        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                response_chunks.append(event.data.delta_content)

        session.on(handle_event)

        await session.send_and_wait({"prompt": message_text}, timeout=600)

        response_text = ''.join(response_chunks)
        return response_text if response_text else "PPT generation completed successfully."

    except Exception as e:
        logger.error(f"? Erreur lors du traitement du message A2A : {e}", exc_info=True)
        return f"Error: {str(e)}"


async def generate_sse_response(jsonrpc: str, request_id: str, task_id: str, context_id: str, result_text: str):
    """Génère une réponse SSE (Server-Sent Events) pour le protocole A2A."""
    import json

    message_id_working = str(uuid.uuid4())
    message_id_complete = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    status_event = {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "contextId": context_id,
            "taskId": task_id,
            "final": False,
            "status": {
                "state": "working",
                "message": {
                    "messageId": message_id_working,
                    "role": "agent",
                    "parts": [{"kind": "text", "text": "Processing your PPT request..."}]
                }
            },
            "kind": "status-update"
        }
    }
    yield f"data: {json.dumps(status_event)}\n\n"

    artifact_event = {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "contextId": context_id,
            "taskId": task_id,
            "artifact": {
                "artifactId": artifact_id,
                "parts": [{"kind": "text", "text": result_text}]
            },
            "kind": "artifact-update"
        }
    }
    yield f"data: {json.dumps(artifact_event)}\n\n"

    complete_event = {
        "jsonrpc": jsonrpc,
        "id": request_id,
        "result": {
            "contextId": context_id,
            "taskId": task_id,
            "final": True,
            "status": {
                "state": "completed",
                "message": {
                    "messageId": message_id_complete,
                    "role": "agent",
                    "parts": [{"kind": "text", "text": result_text}]
                }
            },
            "kind": "status-update"
        }
    }
    yield f"data: {json.dumps(complete_event)}\n\n"


@app.post("/")
async def a2a_jsonrpc_endpoint(request: Request):
    """Endpoint JSON-RPC 2.0 pour le protocole A2A avec streaming SSE."""
    try:
        body = await request.json()
        logger.info(f"?? Requête A2A : {body.get('method', 'unknown')}")

        jsonrpc = body.get("jsonrpc", "2.0")
        request_id = body.get("id")
        method = body.get("method", "")
        params = body.get("params", {})

        # Gère plusieurs méthodes A2A
        if method in ["message/send", "message/stream", "tasks/send", "tasks/sendSubscribe"]:
            message = params.get("message", {})
            parts = message.get("parts", [])

            # Agrège le texte des différentes parties du message
            message_text = ""
            for part in parts:
                if part.get("kind") == "text" or "text" in part:
                    message_text += part.get("text", "")

            if not message_text:
                message_text = str(params)

            logger.info(f"?? Traitement de la requête PPT : {message_text[:100]}...")

            task_id = params.get("id") or str(uuid.uuid4())
            context_id = params.get("contextId") or str(uuid.uuid4())

            return StreamingResponse(
                process_a2a_message_streaming(message_text, jsonrpc, request_id, task_id, context_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

        elif method == "tasks/get":
            # Retourne un statut de tâche "completed" via SSE
            task_id = params.get("id", "unknown")
            context_id = params.get("contextId") or str(uuid.uuid4())

            async def status_sse():
                import json
                event = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": {
                        "contextId": context_id,
                        "taskId": task_id,
                        "final": True,
                        "status": {"state": "completed"},
                        "kind": "status-update"
                    }
                }
                yield f"data: {json.dumps(event)}\n\n"

            return StreamingResponse(status_sse(), media_type="text/event-stream")

        else:
            # Méthode inconnue - erreur
            async def error_sse():
                import json
                event = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                yield f"data: {json.dumps(event)}\n\n"

            return StreamingResponse(error_sse(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"? Erreur A2A : {e}", exc_info=True)

        async def exception_sse():
            import json
            event = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(exception_sse(), media_type="text/event-stream")


@app.get("/")
async def root():
    """Endpoint racine pour vérifier que l'agent est actif."""
    return {
        "agent": "ppt_agent",
        "status": "running",
        "capabilities": ["ppt_generation", "presentation_creation", "slide_design"],
        "skills": ["ppt_skill"]
    }


@app.get("/health")
async def health():
    """Check santé de l'agent."""
    if copilot_client is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return {"status": "healthy"}


@app.get("/ppt/{filename}")
async def download_ppt(filename: str):
    """Télécharge un fichier PPT par son nom."""
    file_path = Path(PPT_DIR) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier PPT '{filename}' introuvable")

    allowed_extensions = [".pptx", ".ppt", ".pdf", ".md"]
    if file_path.suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Seuls les fichiers de présentation sont autorisés")

    media_types = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pdf": "application/pdf",
        ".md": "text/markdown"
    }

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_types.get(file_path.suffix.lower(), "application/octet-stream")
    )


@app.get("/ppts")
async def list_ppts():
    """Liste tous les fichiers PPT disponibles."""
    try:
        ppt_files = []
        for ext in ["*.pptx", "*.ppt", "*.pdf", "*.md"]:
            ppt_files.extend(list(Path(PPT_DIR).glob(ext)))

        ppts = []
        for ppt_file in sorted(ppt_files, key=lambda p: p.stat().st_mtime, reverse=True):
            ppts.append({
                "filename": ppt_file.name,
                "download_url": f"/ppt/{ppt_file.name}",
                "size": ppt_file.stat().st_size,
                "modified": datetime.fromtimestamp(ppt_file.stat().st_mtime).isoformat()
            })
        return {"ppts": ppts, "total": len(ppts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la liste des PPT: {str(e)}")


@app.post("/task", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    """Exécute une tâche de génération PPT."""
    if copilot_client is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    logger.info(f"?? Tâche de {request.user_id}: {request.task}")

    try:
        session = await copilot_client.create_session({
            "model": "claude-sonnet-4.5",
            "streaming": True,
            "skill_directories": [SKILLS_DIR]
        })

        logger.info(f"? Session créée avec ID : {session.session_id}")

        response_chunks = []

        def handle_event(event):
            if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                response_chunks.append(event.data.delta_content)

        session.on(handle_event)

        # Prompt amélioré pour exploiter la compétence PPT
        enhanced_prompt = f"""
{request.task}

Please follow the PPT Skill guidelines:
1. Research the topic thoroughly
2. Create well-structured presentation slides
3. Include practical code examples where relevant
4. Save the presentation in the ppt folder
5. Follow all the requirements specified in the skill documentation
        """

        # Exécution de la tâche avec timeout de 10 minutes
        await session.send_and_wait({"prompt": enhanced_prompt}, timeout=600)

        response_text = ''.join(response_chunks)

        # Recherche du fichier PPT généré
        ppt_path = None
        download_url = None
        try:
            ppt_files = []
            for ext in ["*.pptx", "*.ppt", "*.pdf", "*.md"]:
                ppt_files.extend(list(Path(PPT_DIR).glob(ext)))

            if ppt_files:
                latest_ppt = max(ppt_files, key=lambda p: p.stat().st_mtime)
                ppt_path = str(latest_ppt.absolute())
                download_url = f"/ppt/{latest_ppt.name}"
                logger.info(f"?? PPT généré : {ppt_path}")
        except Exception as e:
            logger.warning(f"Impossible de déterminer le chemin du PPT : {e}")

        logger.info(f"? Tâche terminée pour {request.user_id}")

        return TaskResponse(
            result=response_text if response_text else "PPT generated successfully. Check the ppt folder.",
            agent="ppt_agent",
            ppt_path=ppt_path,
            download_url=download_url
        )

    except Exception as e:
        logger.error(f"? Erreur lors de l'exécution de la tâche : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur d'exécution de la tâche : {str(e)}")


@app.get("/.well-known/agent-card.json")
async def agent_card():
    """Endpoint Agent Card A2A pour découverte des capacités."""
    return JSONResponse({
        "name": "ppt_agent",
        "description": "Agent spécialisé génération de PPT pour présentations professionnelles avec exemples de code",
        "version": "1.0.0",
        "url": "Your PPT Agent URL on Azure Container Apps Endpoint",
        "protocol": "a2a",
        "protocolVersion": "0.2.0",

        # Champs requis par A2A
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],

        # Mots-clés principaux pour le routage des tâches
        "primaryKeywords": ["ppt", "powerpoint", "presentation", "slides", "slide deck", "create ppt", "create a ppt", "make slides"],

        # Compétences au niveau racine
        "skills": [
            {
                "id": "ppt_generation",
                "name": "PPT Generation",
                "description": "Generate comprehensive, well-structured presentations with code examples",
                "tags": ["ppt", "presentation", "slides"],
                "examples": [
                    "Create a PPT about Microsoft Agent Framework",
                    "Generate a presentation on Kubernetes architecture",
                    "Make slides about GitHub Copilot SDK"
                ]
            },
            {
                "id": "technical_presentation",
                "name": "Technical Presentation",
                "description": "Create technical presentations with diagrams, code snippets, and best practices",
                "tags": ["technical", "tutorial", "guide"],
                "examples": [
                    "Create a technical presentation on Docker containerization",
                    "Generate slides for a Kubernetes workshop",
                    "Make a presentation about microservices architecture"
                ]
            },
            {
                "id": "code_showcase",
                "name": "Code Showcase",
                "description": "Create presentations that showcase code examples and implementations",
                "tags": ["code", "examples", "demo"],
                "examples": [
                    "Create slides showcasing Python async patterns",
                    "Generate a code walkthrough presentation",
                    "Make slides demonstrating API usage"
                ]
            }
        ],

        # Informations de capacités supplémentaires
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },

        # Informations du fournisseur
        "provider": {
            "organization": "Kinfey Lo",
            "url": "https://github.com/kinfey"
        }
    })


if __name__ == "__main__":
    import uvicorn

    logger.info(f"?? Démarrage de l'agent PPT sur le port {AGENT_PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=AGENT_PORT,
        log_level="info"
    )
