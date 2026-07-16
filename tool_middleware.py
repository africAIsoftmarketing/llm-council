"""
tool_middleware — Middleware générique d'exécution d'outils pour LLM Council.

Enveloppe le client OpenRouter (API compatible OpenAI /chat/completions) avec
une boucle agentique : le modèle émet des tool_calls, le middleware les
exécute côté backend, renvoie les résultats au modèle, et boucle jusqu'à
obtenir une réponse finale en texte.

Conçu pour s'insérer AUTOUR des appels OpenRouter existants sans modifier
council.py : on remplace l'appel direct par `run_with_tools(...)`.

Outils intégrés :
  - http_request   : requête HTTP GET/POST vers une API publique (allowlist)
  - execute_python : exécution Python sandboxée (subprocess isolé, timeout)

Extensible : enregistrer tout outil personnalisé via `registry.register(...)`.

Dépendances : httpx (>=0.27). Python 3.11+.
Licence : usage interne AfricAIsoft.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("tool_middleware")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

@dataclass
class MiddlewareConfig:
    """Configuration du middleware — surcharger via variables d'environnement."""

    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")

    # Boucle agentique
    max_iterations: int = int(os.getenv("TOOL_MAX_ITERATIONS", "6"))
    request_timeout_s: float = float(os.getenv("TOOL_LLM_TIMEOUT_S", "120"))

    # Outil http_request
    # Allowlist de domaines (suffixes). Vide = tout refuser (fail-closed).
    http_allowed_domains: tuple[str, ...] = tuple(
        d.strip()
        for d in os.getenv(
            "TOOL_HTTP_ALLOWLIST",
            "api.kraken.com,api.coingecko.com,api.coinpaprika.com",
        ).split(",")
        if d.strip()
    )
    http_timeout_s: float = float(os.getenv("TOOL_HTTP_TIMEOUT_S", "15"))
    http_max_response_bytes: int = int(
        os.getenv("TOOL_HTTP_MAX_BYTES", str(512 * 1024))  # 512 Ko
    )

    # Outil execute_python
    python_timeout_s: float = float(os.getenv("TOOL_PY_TIMEOUT_S", "20"))
    python_max_output_bytes: int = int(
        os.getenv("TOOL_PY_MAX_BYTES", str(64 * 1024))  # 64 Ko
    )
    python_enabled: bool = os.getenv("TOOL_PY_ENABLED", "true").lower() == "true"


# --------------------------------------------------------------------------
# Registre d'outils
# --------------------------------------------------------------------------

ToolHandler = Callable[..., Awaitable[str]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: ToolHandler

    def to_openai(self) -> dict:
        """Format attendu par l'API /chat/completions (champ `tools`)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registre extensible : ajouter un outil = un register(), zéro hardcode."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self, name: str, description: str, parameters: dict
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(fn: ToolHandler) -> ToolHandler:
            self._tools[name] = ToolSpec(name, description, parameters, fn)
            return fn

        return decorator

    def specs(self, only: Optional[list[str]] = None) -> list[dict]:
        names = only if only is not None else list(self._tools)
        return [self._tools[n].to_openai() for n in names if n in self._tools]

    async def dispatch(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Outil inconnu : {name}"})
        try:
            return await tool.handler(**arguments)
        except TypeError as exc:
            return json.dumps({"error": f"Arguments invalides pour {name}: {exc}"})
        except Exception as exc:  # noqa: BLE001 — l'erreur retourne au modèle
            logger.exception("Échec de l'outil %s", name)
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})


# --------------------------------------------------------------------------
# Outils intégrés
# --------------------------------------------------------------------------

def build_default_registry(config: MiddlewareConfig) -> ToolRegistry:
    registry = ToolRegistry()

    # ---- http_request ----------------------------------------------------

    def _domain_allowed(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return any(
            host == dom or host.endswith("." + dom)
            for dom in config.http_allowed_domains
        )

    @registry.register(
        name="http_request",
        description=(
            "Effectue une requête HTTP vers une API publique (JSON de préférence). "
            "Domaines autorisés uniquement (allowlist côté serveur). "
            "Utiliser pour interroger des API de données : marchés, météo, etc."
        ),
        parameters={
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST"]},
                "url": {"type": "string", "description": "URL complète https://…"},
                "params": {
                    "type": "object",
                    "description": "Paramètres de requête (query string)",
                    "additionalProperties": True,
                },
                "json_body": {
                    "type": "object",
                    "description": "Corps JSON (POST uniquement)",
                    "additionalProperties": True,
                },
                "headers": {
                    "type": "object",
                    "description": "En-têtes additionnels (facultatif)",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["method", "url"],
        },
    )
    async def http_request(
        method: str,
        url: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> str:
        if not url.lower().startswith("https://"):
            return json.dumps({"error": "Seul https:// est autorisé."})
        if not _domain_allowed(url):
            return json.dumps(
                {
                    "error": "Domaine hors allowlist.",
                    "allowlist": list(config.http_allowed_domains),
                }
            )
        # Filtrage des en-têtes sensibles : le modèle ne doit jamais injecter
        # de credentials — les secrets restent côté backend.
        safe_headers = {
            k: v
            for k, v in (headers or {}).items()
            if k.lower() not in {"authorization", "cookie", "x-api-key"}
        }
        async with httpx.AsyncClient(
            timeout=config.http_timeout_s, follow_redirects=False
        ) as client:
            resp = await client.request(
                method, url, params=params, json=json_body, headers=safe_headers
            )
        body = resp.content[: config.http_max_response_bytes]
        truncated = len(resp.content) > config.http_max_response_bytes
        try:
            payload: Any = json.loads(body)
        except ValueError:
            payload = body.decode("utf-8", errors="replace")
        return json.dumps(
            {
                "status": resp.status_code,
                "truncated": truncated,
                "body": payload,
            },
            ensure_ascii=False,
            default=str,
        )

    # ---- execute_python ---------------------------------------------------

    @registry.register(
        name="execute_python",
        description=(
            "Exécute un script Python 3 court dans un sandbox isolé (sans réseau, "
            "sans accès aux variables d'environnement, timeout strict). "
            "Utiliser pour parser, calculer, agréger des données déjà obtenues. "
            "Le script doit écrire son résultat sur stdout (print). "
            "Bibliothèques : stdlib uniquement (json, statistics, math, datetime…)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Script Python complet"},
            },
            "required": ["code"],
        },
    )
    async def execute_python(code: str) -> str:
        if not config.python_enabled:
            return json.dumps({"error": "execute_python est désactivé."})
        return await asyncio.to_thread(_run_python_sandboxed, code, config)

    return registry


def _run_python_sandboxed(code: str, config: MiddlewareConfig) -> str:
    """Exécution dans un subprocess isolé : env vidé, -I (mode isolé), cwd temp.

    NOTE : c'est une isolation « raisonnable » pour un dyno Heroku (pas de
    secrets exposés, pas d'import de site-packages, timeout). Pour une
    isolation forte (multi-tenant, code hostile), utiliser un vrai runtime
    sandbox : gVisor, Firecracker, ou un service type E2B/Modal.
    """
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "script.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", script],  # -I : ignore env/site/user site
                capture_output=True,
                timeout=config.python_timeout_s,
                cwd=tmp,
                env={},  # aucun secret hérité
            )
        except subprocess.TimeoutExpired:
            return json.dumps(
                {"error": f"Timeout ({config.python_timeout_s}s) dépassé."}
            )
    out = proc.stdout[: config.python_max_output_bytes].decode(
        "utf-8", errors="replace"
    )
    err = proc.stderr[: config.python_max_output_bytes].decode(
        "utf-8", errors="replace"
    )
    return json.dumps(
        {"returncode": proc.returncode, "stdout": out, "stderr": err},
        ensure_ascii=False,
    )


# --------------------------------------------------------------------------
# Boucle agentique
# --------------------------------------------------------------------------

@dataclass
class AgentResult:
    content: str
    messages: list[dict] = field(default_factory=list)  # transcription complète
    iterations: int = 0
    tool_calls_executed: int = 0
    stopped_reason: str = "final_answer"  # final_answer | max_iterations | error


class ToolMiddleware:
    """Enveloppe les appels OpenRouter avec exécution d'outils.

    Usage minimal (drop-in autour d'un appel existant) :

        mw = ToolMiddleware()
        result = await mw.run_with_tools(
            model="qwen/qwen3.7-max",
            messages=[{"role": "user", "content": prompt}],
        )
        texte_final = result.content
    """

    def __init__(
        self,
        config: Optional[MiddlewareConfig] = None,
        registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.config = config or MiddlewareConfig()
        self.registry = registry or build_default_registry(self.config)

    async def _chat(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.config.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.config.request_timeout_s) as client:
            resp = await client.post(
                f"{self.config.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()

    async def run_with_tools(
        self,
        model: str,
        messages: list[dict],
        tools: Optional[list[str]] = None,
        max_iterations: Optional[int] = None,
        extra_body: Optional[dict] = None,
    ) -> AgentResult:
        """Boucle : appel LLM → tool_calls ? → exécution → ré-appel → réponse.

        Args:
            model: identifiant OpenRouter (ex. "anthropic/claude-sonnet-4-6").
            messages: historique au format OpenAI.
            tools: sous-ensemble d'outils à exposer (None = tous).
            max_iterations: plafond d'allers-retours outil.
            extra_body: champs additionnels (temperature, provider, etc.).
        """
        limit = max_iterations or self.config.max_iterations
        convo = list(messages)
        tool_calls_total = 0

        for iteration in range(1, limit + 1):
            payload = {
                "model": model,
                "messages": convo,
                "tools": self.registry.specs(tools),
                **(extra_body or {}),
            }
            try:
                data = await self._chat(payload)
            except httpx.HTTPStatusError as exc:
                return AgentResult(
                    content=f"[erreur API OpenRouter : {exc.response.status_code}]",
                    messages=convo,
                    iterations=iteration,
                    tool_calls_executed=tool_calls_total,
                    stopped_reason="error",
                )

            choice = data["choices"][0]
            message = choice["message"]
            convo.append(message)

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return AgentResult(
                    content=message.get("content") or "",
                    messages=convo,
                    iterations=iteration,
                    tool_calls_executed=tool_calls_total,
                    stopped_reason="final_answer",
                )

            # Exécution parallèle des tool_calls de ce tour
            async def _run(tc: dict) -> dict:
                fn = tc["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                result = await self.registry.dispatch(fn["name"], args)
                return {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }

            results = await asyncio.gather(*(_run(tc) for tc in tool_calls))
            convo.extend(results)
            tool_calls_total += len(tool_calls)
            logger.info(
                "Itération %d : %d tool_call(s) exécuté(s) [%s]",
                iteration,
                len(tool_calls),
                ", ".join(tc["function"]["name"] for tc in tool_calls),
            )

        # Plafond atteint : on force une réponse finale sans outils
        convo.append(
            {
                "role": "user",
                "content": (
                    "Limite d'appels d'outils atteinte. Produis maintenant ta "
                    "réponse finale avec les données déjà obtenues."
                ),
            }
        )
        payload = {"model": model, "messages": convo, **(extra_body or {})}
        try:
            data = await self._chat(payload)
            content = data["choices"][0]["message"].get("content") or ""
        except Exception:  # noqa: BLE001
            content = "[réponse finale indisponible après la limite d'itérations]"
        return AgentResult(
            content=content,
            messages=convo,
            iterations=limit,
            tool_calls_executed=tool_calls_total,
            stopped_reason="max_iterations",
        )

    def run_with_tools_sync(self, *args: Any, **kwargs: Any) -> AgentResult:
        """Variante synchrone pour un code appelant non-async."""
        return asyncio.run(self.run_with_tools(*args, **kwargs))
