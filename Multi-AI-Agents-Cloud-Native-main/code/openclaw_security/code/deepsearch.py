"""
deepsearch.py  —  Module DeepSearch.
Utilise SerpAPI Google Search + scraping de pages + résumé LLM
pour construire un arrière-plan de connaissances pour un sujet de podcast.

Dépendances: pip install serpapi requests beautifulsoup4
Clé SerpAPI: https://serpapi.com/manage-api-key
"""

import os
import re
import time
import datetime
import urllib.parse
import urllib.request
import json
import html

try:
    import serpapi          # pip install serpapi  (nouveau package officiel)
    HAS_SERPAPI = True
except ImportError:
    HAS_SERPAPI = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# Clé SerpAPI lue depuis la variable d'environnement
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


# ─────────────────────────────────────────────
#  1. Couche de recherche  —  SerpAPI Google Search
# ─────────────────────────────────────────────

def search_serpapi(query: str, max_results: int = 8) -> list[dict]:
    """
    Utilise le package officiel serpapi pour appeler l'API Google Search.
    Retourne une liste normalisée [{"title", "url", "snippet"}, ...].

    Docs: https://serpapi.com/search-api
    Package: pip install serpapi
    """
    if not HAS_SERPAPI:
        raise ImportError(
            "Package serpapi non installé. Exécutez: pip install serpapi\n"
            "ou ajoutez serpapi aux dépendances dans Dockerfile.app"
        )
    if not SERPAPI_KEY:
        raise ValueError(
            "La variable d'environnement SERPAPI_KEY n'est pas définie.\n"
            "Ajoutez-la à votre fichier .env: SERPAPI_KEY=votre_clé_api_ici\n"
            "Obtenez une clé sur: https://serpapi.com/manage-api-key"
        )

    client = serpapi.Client(api_key=SERPAPI_KEY)
    raw = client.search({
        "engine":  "google",
        "q":       query,
        "hl":      "zh-cn",        # langue de l'interface: Chinois
        "gl":      "cn",           # région: Chine (changez en 'us' pour les résultats anglais)
        "num":     max_results,    # résultats par page (max 100)
        "safe":    "off",
    })

    results = []
    for item in raw.get("organic_results", []):
        results.append({
            "title":   item.get("title", ""),
            "url":     item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return results[:max_results]


def search_serpapi_http(query: str, max_results: int = 8) -> list[dict]:
    """
    Solution de secours HTTP pure: appelle directement le point de terminaison REST SerpAPI (pas de package serpapi nécessaire).
    Utilisez ceci lorsque le package serpapi ne peut pas être installé.
    """
    if not SERPAPI_KEY:
        raise ValueError("La variable d'environnement SERPAPI_KEY n'est pas définie")

    import requests  # type: ignore
    params = {
        "engine":  "google",
        "q":       query,
        "hl":      "zh-cn",
        "gl":      "cn",
        "num":     max_results,
        "api_key": SERPAPI_KEY,
    }
    resp = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("organic_results", []):
        results.append({
            "title":   item.get("title", ""),
            "url":     item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return results[:max_results]


def web_search(query: str, max_results: int = 8) -> list[dict]:
    """
    Point d'entrée de recherche unifié:
      1. Préfère le package officiel serpapi
      2. Retombe sur l'appel REST HTTP simple
    Les deux méthodes nécessitent une SERPAPI_KEY valide.
    """
    print(f"  [DeepSearch] Recherche Google: {query!r}")
    try:
        if HAS_SERPAPI:
            results = search_serpapi(query, max_results)
        else:
            print("  [DeepSearch] Package serpapi non installé, utilisation de la solution de secours HTTP")
            results = search_serpapi_http(query, max_results)
        print(f"  [DeepSearch] Obtenu {len(results)} résultats")
        return results
    except ValueError as e:
        raise
    except Exception as e:
        print(f"  [DeepSearch] Échec de l'appel serpapi: {e}, essai de la solution de secours HTTP")
        try:
            return search_serpapi_http(query, max_results)
        except Exception as e2:
            print(f"  [DeepSearch] La solution de secours HTTP a aussi échoué: {e2}")
            return []


# ─────────────────────────────────────────────
#  2. Scraping du corps de la page web
# ─────────────────────────────────────────────

def fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Récupère le texte du corps de la page (préfère BeautifulSoup, retombe sur regex)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PodcastBot/1.0)",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

    if HAS_BS4:
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    else:
        text = re.sub(r"<[^>]+>", " ", raw)
        text = html.unescape(text)
        text = re.sub(r"\s{3,}", "\n", text).strip()

    return text[:max_chars]


# ─────────────────────────────────────────────
#  3. Expansion multi-requêtes (cœur de DeepSearch)
# ─────────────────────────────────────────────

SEARCH_ANGLE_PROMPT = """\
Vous êtes un expert en stratégie de recherche. Étant donné un sujet de podcast, générez 4 requêtes de recherche complémentaires (mélange de chinois et d'anglais)
couvrant: principes techniques, derniers développements, applications industrielles, controverses/défis.
Sortez seulement un tableau JSON au format: ["requête1","requête2","requête3","requête4"]
N'incluez aucun autre texte.
"""


def expand_queries(topic: str, ollama_base_url: str = "", model: str = "") -> list[str]:
    """Construit des requêtes de recherche complémentaires pour le sujet (pas d'appel LLM nécessaire)."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return [
        f"{topic} dernières nouvelles {today}",
        f"{topic} principes techniques comment ça marche",
        f"{topic} applications industrielles cas d'usage",
        f"{topic} défis tendances futures",
    ]


# ─────────────────────────────────────────────
#  4. Résumé des connaissances (pour le script de podcast)
# ─────────────────────────────────────────────

SUMMARY_SYSTEM = """\
Vous êtes un assistant de recherche qui organise le matériel source pour les épisodes de podcast.
Basé sur les résumés de recherche fournis et le contenu des pages web, distillez les points de connaissance principaux nécessaires pour la discussion de l'invité du podcast.
Exigences:
- Divisez en 5–8 points de connaissance clés
- Chaque point de connaissance inclut: un titre + 2–3 phrases explicatives
- Langue: Chinois, concis et professionnel, adapté à la discussion parlée
- Incluez des données spécifiques, études de cas ou chronologies si disponibles
"""


def build_knowledge_base(
    topic: str,
    ollama_base_url: str,
    model: str,
    max_sources: int = 6,
) -> str:
    """
    Pipeline DeepSearch complet:
    1. LLM étend les angles de recherche
    2. SerpAPI Google Search sur plusieurs requêtes
    3. Récupère les corps des N meilleures pages
    4. LLM distille en points de connaissance structurés
    """
    import requests  # type: ignore

    print(f"\n{'='*50}")
    print(f"  Deep Search: sujet = {topic!r}")
    print(f"  Moteur de recherche: SerpAPI Google Search")
    print(f"{'='*50}")

    queries = expand_queries(topic, ollama_base_url, model)
    print(f"  Requêtes étendues: {queries}")

    all_results: list[dict] = []
    seen_urls: set[str] = set()
    for q in queries:
        try:
            for r in web_search(q, max_results=5):
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)
        except ValueError as e:
            print(f"  [DeepSearch] ⚠ saut de la recherche: {e}")
            break
        time.sleep(0.5)

    print(f"  Total des résultats uniques collectés: {len(all_results)}")

    enriched: list[str] = []
    for i, r in enumerate(all_results[:max_sources]):
        enriched.append(f"[Source {i+1}] {r['title']}\nURL: {r['url']}")
        enriched.append(f"Extrait: {r['snippet']}")
        full_text = fetch_page_text(r["url"], max_chars=2000)
        if full_text:
            enriched.append(f"Extrait du corps:\n{full_text[:800]}")
        enriched.append("")
        time.sleep(0.3)

    raw_content = "\n".join(enriched)
    print(f"  Longueur du contenu brut: {len(raw_content)} caractères")

    print("  Distillation des points de connaissance...")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": (
                f"Podcast topic: {topic}\n\n"
                f"Source material collected:\n\n{raw_content[:8000]}"
            )},
        ],
        "temperature": 0.4,
        "max_tokens": 2000,
    }
    try:
        resp = requests.post(
            f"{ollama_base_url}/chat/completions",
            json=payload, timeout=600
        )
        resp.raise_for_status()
        knowledge = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [DeepSearch] Échec de la distillation des connaissances: {e}")
        knowledge = f"Sujet: {topic}\n\nExtraits de recherche:\n" + "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in all_results[:8]
        )

    print(f"  Base de connaissances construite ({len(knowledge)} caractères)")
    return knowledge


# ─── Test autonome ─────────────────────────────
if __name__ == "__main__":
    import sys
    if not SERPAPI_KEY:
        print("Veuillez définir d'abord la variable d'environnement: export SERPAPI_KEY=votre_clé_ici")
        sys.exit(1)
    topic = sys.argv[1] if len(sys.argv) > 1 else "Développement de la technologie des agents IA"
    kb = build_knowledge_base(
        topic,
        ollama_base_url="http://localhost:11434/v1",
        model="qwen2.5:3b",
    )
    print("\n" + "="*50)
    print("Contenu de la base de connaissances:")
    print(kb)
