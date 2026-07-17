import pytest

from pipeline.analysis.claude_classifier import _extrair_json


def test_extrair_json_puro():
    texto = '{"tipo_chatbot": "sem_chatbot", "num_servicos": 3}'
    dados = _extrair_json(texto)
    assert dados["tipo_chatbot"] == "sem_chatbot"
    assert dados["num_servicos"] == 3


def test_extrair_json_com_fences_markdown():
    texto = '```json\n{"tipo_chatbot": "chatbot_ia_real"}\n```'
    dados = _extrair_json(texto)
    assert dados["tipo_chatbot"] == "chatbot_ia_real"


def test_extrair_json_com_texto_a_volta():
    texto = 'Aqui está a análise:\n{"tipo_chatbot": "chatbot_deterministico"}\nEspero que ajude.'
    dados = _extrair_json(texto)
    assert dados["tipo_chatbot"] == "chatbot_deterministico"


def test_extrair_json_invalido_lanca_erro():
    with pytest.raises(ValueError):
        _extrair_json("isto nao tem json nenhum")
