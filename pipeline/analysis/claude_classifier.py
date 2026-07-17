"""Fase 3 (parte 2) - Classifica o website de uma empresa usando a Claude API,
a partir dos sinais brutos recolhidos por `website_analyzer.analisar_website`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

import anthropic

from pipeline.analysis.website_analyzer import AnaliseWebsiteRaw
from pipeline.config import settings
from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)

TIPOS_CHATBOT_VALIDOS = {"sem_chatbot", "chatbot_deterministico", "chatbot_ia_real"}

_PROMPT_TEMPLATE = """\
Estás a analisar o website de uma empresa portuguesa para preparar uma proposta \
comercial de 3 serviços de IA: (1) assistente conversacional para o website, \
(2) preparação para pesquisa por IA/GEO, (3) formação prática em IA para equipas.

Empresa: {nome_empresa}

Widget de chat detetado no site: {widget_detectado}

{bloco_resposta_chatbot}

Conteúdo (texto) da homepage:
---
{homepage_texto}
---

Com base nisto, responde APENAS com um objeto JSON (sem markdown, sem texto à volta) com estes campos:

{{
  "tipo_chatbot": "sem_chatbot" | "chatbot_deterministico" | "chatbot_ia_real",
  "num_servicos": <número inteiro estimado de serviços/produtos listados, ou null>,
  "formulario_qualificado": <true se o formulário de contacto pede informação qualificadora (ex: orçamento, tipo de projeto) em vez de só nome/email/mensagem, false caso contrário, null se não souberes>,
  "tem_blog": <true/false/null>,
  "idiomas": [<lista de códigos de idioma disponíveis no site, ex: "pt", "en">],
  "exemplo_falha_chatbot": "<exemplo concreto e curto de algo que o chatbot atual (se existir) não respondeu bem, com base na resposta capturada; ou null se não houver chatbot ou não houver resposta capturada>"
}}

Regras para tipo_chatbot:
- Se não há widget de chat detetado: "sem_chatbot".
- Se há widget mas a resposta capturada é genérica, circular, ou não respondeu à pergunta fora do guião: "chatbot_deterministico".
- Se há widget e a resposta capturada demonstra compreensão real da pergunta fora do guião: "chatbot_ia_real".
- Se há widget mas não há resposta capturada, usa o teu melhor julgamento a partir do contexto (ex: nome do fornecedor do widget), e nota isso no exemplo_falha_chatbot.
"""


@dataclass
class ClassificacaoWebsite:
    tipo_chatbot: str
    exemplo_falha_chatbot: Optional[str] = None
    sinais: dict = field(default_factory=dict)


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    texto = re.sub(r"^```(json)?", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()

    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError(f"Resposta da Claude API nao contem JSON reconhecivel: {texto[:200]!r}")

    return json.loads(texto[inicio : fim + 1])


def _montar_prompt(raw: AnaliseWebsiteRaw, nome_empresa: str) -> str:
    if raw.widget_detectado and raw.resposta_chatbot:
        bloco_resposta = (
            f"Pergunta fora do guião enviada ao widget: "
            f"'Vendem/trabalham também fora de Portugal?'\n"
            f"Trecho da página logo após enviar a pergunta (pode incluir a resposta do chatbot):\n"
            f"---\n{raw.resposta_chatbot}\n---"
        )
    elif raw.widget_detectado:
        bloco_resposta = "Não foi possível capturar automaticamente uma resposta do widget (interação falhou)."
    else:
        bloco_resposta = ""

    return _PROMPT_TEMPLATE.format(
        nome_empresa=nome_empresa,
        widget_detectado=raw.widget_detectado or "nenhum",
        bloco_resposta_chatbot=bloco_resposta,
        homepage_texto=raw.homepage_texto[:6000],
    )


def classificar_website(raw: AnaliseWebsiteRaw, nome_empresa: str) -> ClassificacaoWebsite:
    """Chama a Claude API para classificar o tipo de chatbot e extrair sinais do website."""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY nao configurada")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = _montar_prompt(raw, nome_empresa)

    resposta = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = "".join(bloco.text for bloco in resposta.content if hasattr(bloco, "text"))

    dados = _extrair_json(texto)

    tipo_chatbot = dados.get("tipo_chatbot")
    if tipo_chatbot not in TIPOS_CHATBOT_VALIDOS:
        logger.warning("tipo_chatbot invalido devolvido pela Claude API: %r, a assumir 'sem_chatbot'", tipo_chatbot)
        tipo_chatbot = "sem_chatbot"

    sinais = {
        "num_servicos": dados.get("num_servicos"),
        "formulario_qualificado": dados.get("formulario_qualificado"),
        "tem_blog": dados.get("tem_blog"),
        "idiomas": dados.get("idiomas") or [],
    }

    return ClassificacaoWebsite(
        tipo_chatbot=tipo_chatbot,
        exemplo_falha_chatbot=dados.get("exemplo_falha_chatbot"),
        sinais=sinais,
    )
