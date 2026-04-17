#!/usr/bin/env python3
"""
auto_run.py  —  Point d'entrée entièrement automatisé pour la génération de podcasts.
Aucune entrée utilisateur requise. Pipeline complet :
  OpenClaw TrendScout → DeepSearch (SerpAPI) → Génération de dialogue LLM → Sortie TXT

Modes d'exécution :
  1. Exécution unique (par défaut) : python auto_run.py
  2. Mode programmé :              python auto_run.py --schedule 6   (toutes les 6 heures)
  3. Spécifier le nombre d'épisodes : python auto_run.py --count 2    (générer des podcasts pour les 2 meilleurs sujets)
"""

import os
import sys
import time
import signal
import argparse
import datetime
import traceback
from pathlib import Path

# ── Modules internes ──────────────────────────────────
from trend_scout    import scout_with_fallback, TrendTopic
from deepsearch     import build_knowledge_base
from podcast_generator import (
    generate_podcast_from_topic,
    wait_for_services,
    OLLAMA_BASE_URL,
    MODEL,
)

# ─────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────

OUTPUT_DIR      = Path(os.getenv("PODCAST_OUTPUT_DIR", "./output"))  # Répertoire de sortie pour les podcasts
SCHEDULE_HOURS  = int(os.getenv("SCHEDULE_HOURS", "6"))      # Intervalle en mode programmé (heures)
TOPICS_PER_RUN  = int(os.getenv("TOPICS_PER_RUN", "1"))      # Épisodes par exécution (par défaut : top 1)
SKIP_SEARCH     = os.getenv("SKIP_SEARCH", "").lower() in ("1", "true", "yes")  # Sauter la recherche profonde

# ─────────────────────────────────────────────
#  Rapport d'exécution
# ─────────────────────────────────────────────

class RunReport:
    """
    Classe pour suivre les succès et échecs d'une exécution de génération de podcasts.
    """
    def __init__(self):
        self.start_time = datetime.datetime.now()  # Heure de début de l'exécution
        self.succeeded: list[tuple[str, Path]] = []  # Liste des succès (sujet, chemin du fichier)
        self.failed:    list[tuple[str, str]]  = []  # Liste des échecs (sujet, raison)

    def add_success(self, topic: str, path: Path):
        """Ajoute un succès à la liste."""
        self.succeeded.append((topic, path))

    def add_failure(self, topic: str, reason: str):
        """Ajoute un échec à la liste."""
        self.failed.append((topic, reason))

    def summary(self) -> str:
        """Génère un résumé de l'exécution."""
        elapsed = (datetime.datetime.now() - self.start_time).seconds
        lines = [
            "",
            "=" * 55,
            f"  Rapport d'exécution  ({self.start_time.strftime('%Y-%m-%d %H:%M')})",
            "=" * 55,
            f"  Temps écoulé: {elapsed // 60}m {elapsed % 60}s",
            f"  Réussis: {len(self.succeeded)} épisode(s)",
            f"  Échoués: {len(self.failed)} épisode(s)",
        ]
        if self.succeeded:
            lines.append("")
            lines.append("  Fichiers générés:")
            for topic, path in self.succeeded:
                lines.append(f"    ✓  {topic}")
                lines.append(f"       {path.name}")
        if self.failed:
            lines.append("")
            lines.append("  Échecs:")
            for topic, reason in self.failed:
                lines.append(f"    ✗  {topic}: {reason[:80]}")
        lines.append("=" * 55)
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  Logique principale d'exécution unique
# ─────────────────────────────────────────────

def run_once(count: int = None) -> RunReport:
    """
    Exécute un cycle complet de génération de podcast automatisée :
    1. Appelle l'agent OpenClaw trend-scout pour découvrir les sujets tendance
    2. Trie par score de tendance, sélectionne les N meilleurs
    3. Pour chaque sujet : DeepSearch + génération de dialogue LLM → TXT
    """
    report = RunReport()
    n = count or TOPICS_PER_RUN

    banner = f"""
╔══════════════════════════════════════════════════╗
║        Générateur de Podcast IA — Mode Auto       ║
║  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  Entièrement automatisé, aucune entrée utilisateur  ║
╚══════════════════════════════════════════════════╝
  Pipeline: Trend Scout → Deep Search → Génération de Dialogue LLM
  Épisodes cette exécution: {n}
"""
    print(banner)

    # ── Étape 1: Vérification de santé des services ──────────────────────
    wait_for_services()

    # ── Étape 2: OpenClaw découvre les sujets tendance ──────────────
    print("\n🔭 Étape 1: Trend Scout — découverte des sujets tendance")
    print("   Appel de la passerelle OpenClaw (agent: trend-scout)")
    print("   L'agent effectuera 2 recherches web et analysera les tendances...")

    try:
        topics = scout_with_fallback(top_n=max(n, 3))
        print(f"\n   ✅ Trouvé {len(topics)} sujets tendance, sélection des {n} meilleurs par score")
    except Exception as e:
        print(f"\n   ❌ Échec de la découverte de tendances: {e}")
        report.add_failure("TrendScout", str(e))
        print(report.summary())
        return report

    # ── Étape 3: Générer un podcast par sujet ────────────────────
    selected = topics[:n]
    for i, trend in enumerate(selected, 1):
        sep = f"\n{'─'*55}"
        print(f"{sep}")
        print(f"  🎙  Sujet {i}/{n}: {trend.topic}")
        print(f"  Score: {trend.trend_score}/10  |  Angle: {trend.angle}")
        print(f"  Mots-clés: {', '.join(trend.keywords)}")
        print(sep)

        try:
            out_path = generate_podcast_from_topic(
                trend,
                skip_search=SKIP_SEARCH,
            )
            report.add_success(trend.topic, out_path)
            print(f"\n  ✅ Terminé: {out_path.name}")
        except Exception as e:
            err_msg = str(e)
            print(f"\n  ❌ Échec de génération: {err_msg}")
            traceback.print_exc()
            report.add_failure(trend.topic, err_msg)

        # Pause brève entre les sujets (limitation du taux + prévention OOM)
        if i < n:
            pause = 10
            print(f"\n  ⏸  Attente de {pause}s avant le prochain épisode...")
            time.sleep(pause)

    print(report.summary())
    return report


# ─────────────────────────────────────────────
#  Dispatcher programmé
# ─────────────────────────────────────────────

_running = True

def _handle_signal(sig, frame):
    """Gestionnaire de signal pour arrêt gracieux."""
    global _running
    print(f"\nSignal {sig} reçu, arrêt du programmateur...")
    _running = False


def run_scheduler(interval_hours: float, count: int = None):
    """
    Mode programmé : exécute run_once() toutes les interval_hours heures.
    Prend en charge l'arrêt gracieux via SIGTERM / SIGINT.
    """
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    interval_sec = int(interval_hours * 3600)
    run_count = 0

    print(f"""
╔══════════════════════════════════════════════════╗
║       Programmateur de Podcast IA — Démarré       ║
║       Intervalle: toutes les {interval_hours:.1f} heure(s)              
║       Appuyez sur Ctrl+C pour arrêter gracieusement ║
╚══════════════════════════════════════════════════╝
""")

    while _running:
        run_count += 1
        print(f"\n[programmateur] Tour {run_count} commencé  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            run_once(count=count)
        except Exception as e:
            print(f"[programmateur] Exception dans ce tour (interceptée, continuation): {e}")
            traceback.print_exc()

        if not _running:
            break

        next_run = datetime.datetime.now() + datetime.timedelta(seconds=interval_sec)
        print(f"\n[programmateur] Prochaine exécution: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"            (attente de {interval_hours:.1f} heure(s), Ctrl+C pour quitter tôt)")

        # Sommeil segmenté, permet la réponse SIGTERM en milieu d'attente
        waited = 0
        while waited < interval_sec and _running:
            chunk = min(30, interval_sec - waited)
            time.sleep(chunk)
            waited += chunk

    print("\n[programmateur] Arrêté. Au revoir!")


# ─────────────────────────────────────────────
#  Point d'entrée CLI
# ─────────────────────────────────────────────

def main():
    """Point d'entrée principal pour l'interface en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Générateur de Podcast IA — entièrement automatisé, aucune entrée utilisateur requise",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes d'exécution:
  # Exécution unique, générer 1 épisode (par défaut)
  python auto_run.py

  # Exécution unique, générer des podcasts pour les 2 meilleurs sujets tendance
  python auto_run.py --count 2

  # Mode programmé, exécuter toutes les 6 heures (recommandé pour Docker)
  python auto_run.py --schedule 6

  # Sauter DeepSearch (test / économiser le quota SerpAPI)
  python auto_run.py --no-search

  # Afficher seulement les tendances actuelles (pas de génération de script de podcast)
  python auto_run.py --scout-only
        """,
    )
    parser.add_argument(
        "--schedule", "-s", type=float, metavar="HEURES",
        help="Mode programmé: exécuter toutes les N heures (par défaut: exécution unique)"
    )
    parser.add_argument(
        "--count", "-n", type=int, default=TOPICS_PER_RUN,
        help=f"Nombre d'épisodes de podcast par exécution (par défaut: {TOPICS_PER_RUN})"
    )
    parser.add_argument(
        "--no-search", dest="no_search", action="store_true",
        help="Sauter SerpAPI DeepSearch (pour les tests)"
    )
    parser.add_argument(
        "--scout-only", action="store_true",
        help="Exécuter seulement l'exploration de tendances, ne pas générer de script de podcast"
    )
    args = parser.parse_args()

    if args.no_search:
        os.environ["SKIP_SEARCH"] = "1"
        global SKIP_SEARCH
        SKIP_SEARCH = True

    if args.scout_only:
        print("\n🔭 Exécution seulement d'OpenClaw TrendScout (--scout-only mode)")
        wait_for_services()
        topics = scout_with_fallback(top_n=5)
        print(f"\n{'='*55}")
        print("Top 5 sujets tendance IA/tech:")
        for i, t in enumerate(topics, 1):
            print(f"\n{i}. {t}")
        return

    if args.schedule:
        run_scheduler(interval_hours=args.schedule, count=args.count)
    else:
        report = run_once(count=args.count)
        sys.exit(0 if report.succeeded else 1)


if __name__ == "__main__":
    main()
