"""Factory multi-proveedor para modelos de chat (LangChain).

Este proyecto usa LangChain para orquestar generación + ejecución de SQL vía tools.
Para mantener compatibilidad, el proveedor se selecciona por variables de entorno.

Variables principales:
  - LLM_PROVIDER: "openai" (default), "anthropic", "google" ("gemini" alias)
  - LLM_MODEL: modelo por defecto del proveedor (recomendado para no-openai)
  - OPENAI_MODEL: compatibilidad legacy (solo openai)

Notas:
  - Cuando require_tools=True, se valida que el modelo permita bind_tools().
  - Las dependencias por proveedor se importan en forma lazy para no forzar instalación.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from src.utils.logger import logger

_SUPPORTED_PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "google")

_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    # Defaults razonables; pueden (y deberían) sobreescribirse por env.
    "anthropic": "claude-3-5-sonnet-20241022",
    "google": "gemini-1.5-pro",
}


def normalize_provider(provider: str | None = None) -> str:
    """Normaliza el nombre del proveedor desde env/entrada.

    Args:
        provider: Proveedor solicitado (opcional). Si no se pasa, usa LLM_PROVIDER.

    Returns:
        Proveedor normalizado: openai|anthropic|google
    """
    value = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    if value in ("gemini", "google-genai", "google_genai", "google_gemini"):
        return "google"
    return value


def get_default_model_name(provider: str | None = None) -> str:
    """Obtiene el modelo por defecto para el proveedor.

    Prioridad:
      1) LLM_MODEL (si está seteado)
      2) Para openai: OPENAI_MODEL (compatibilidad)
      3) Default interno por proveedor

    Args:
        provider: Proveedor solicitado (opcional).

    Returns:
        Nombre del modelo.
    """
    normalized = normalize_provider(provider)

    env_model = os.getenv("LLM_MODEL")
    if env_model:
        return env_model

    if normalized == "openai":
        return os.getenv("OPENAI_MODEL", _DEFAULT_MODELS["openai"])

    return _DEFAULT_MODELS.get(normalized, "")


def supports_tools(llm: BaseChatModel) -> bool:
    """Indica si el modelo soporta tool calling vía bind_tools()."""
    return callable(getattr(llm, "bind_tools", None))


def bind_tools_safe(llm: BaseChatModel, tools: list[Any], tool_choice: str | None = "any") -> BaseChatModel:
    """Bindea tools al modelo, con fallback si tool_choice no es soportado."""
    if not supports_tools(llm):
        raise ValueError("El modelo no soporta tool calling (bind_tools).")

    try:
        if tool_choice is None:
            return llm.bind_tools(tools)
        return llm.bind_tools(tools, tool_choice=tool_choice)
    except TypeError:
        # Algunos wrappers no aceptan tool_choice.
        logger.debug("Proveedor no soporta tool_choice; reintentando sin tool_choice.")
        return llm.bind_tools(tools)
    except NotImplementedError as e:
        raise ValueError("El modelo no soporta tool calling (bind_tools).") from e


def get_chat_model(
    *,
    model_name: str | None = None,
    provider: str | None = None,
    temperature: float | None = 0,
    max_tokens: int | None = None,
    require_tools: bool = False,
    **kwargs: Any,
) -> BaseChatModel:
    """Crea un modelo de chat multi-proveedor.

    Args:
        model_name: Nombre del modelo (opcional). Si no, usa get_default_model_name().
        provider: Proveedor (opcional). Si no, usa LLM_PROVIDER.
        temperature: Temperatura del modelo.
        max_tokens: Límite de tokens de salida (si el wrapper lo soporta).
        require_tools: Si True, valida que el modelo soporte bind_tools().
        **kwargs: Parámetros extra específicos del wrapper (uso avanzado).

    Returns:
        Instancia BaseChatModel.
    """
    normalized = normalize_provider(provider)
    if normalized not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Proveedor no soportado: {normalized}. Soportados: {', '.join(_SUPPORTED_PROVIDERS)}. "
            "Configura LLM_PROVIDER y el paquete langchain-* correspondiente."
        )

    model = model_name or get_default_model_name(normalized)
    if not model:
        raise ValueError(
            f"No se pudo determinar el modelo para provider={normalized}. "
            "Configura LLM_MODEL (recomendado) o OPENAI_MODEL (solo openai)."
        )

    llm: BaseChatModel
    if normalized == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError("Falta dependencia: instala langchain-openai para usar provider=openai.") from e

        llm_kwargs: dict[str, Any] = {"model": model, "temperature": temperature, "max_tokens": max_tokens}
        llm_kwargs.update(kwargs)
        llm = ChatOpenAI(**llm_kwargs)

    elif normalized == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as e:
            raise ImportError("Falta dependencia: instala langchain-anthropic para usar provider=anthropic.") from e

        llm_kwargs = {"model": model, "temperature": temperature}
        if max_tokens is not None:
            llm_kwargs["max_tokens"] = max_tokens
        llm_kwargs.update(kwargs)
        llm = ChatAnthropic(**llm_kwargs)

    else:  # google
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            raise ImportError("Falta dependencia: instala langchain-google-genai para usar provider=google/gemini.") from e

        llm_kwargs = {"model": model, "temperature": temperature}
        if max_tokens is not None:
            llm_kwargs["max_output_tokens"] = max_tokens
        llm_kwargs.update(kwargs)
        llm = ChatGoogleGenerativeAI(**llm_kwargs)

    if require_tools and not supports_tools(llm):
        raise ValueError(
            f"El provider/modelo no soporta tool calling requerido para este flujo: {normalized}:{model}."
        )

    # Avisos suaves si falta API key; la llamada real fallará con más detalle.
    if normalized == "openai" and not (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")):
        logger.warning("OPENAI_API_KEY no está configurado (provider=openai).")
    if normalized == "anthropic" and not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")):
        logger.warning("ANTHROPIC_API_KEY no está configurado (provider=anthropic).")
    if normalized == "google" and not (os.getenv("GOOGLE_API_KEY") or os.getenv("LLM_API_KEY")):
        logger.warning("GOOGLE_API_KEY no está configurado (provider=google/gemini).")

    return llm

