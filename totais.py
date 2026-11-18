"""Histórico total: soma o que o bot gastou e comprou em todas as vezes que rodou.

Fica em %APPDATA%\\SecretShop, e não na pasta do programa, para continuar depois de baixar uma versão nova.
"""
import json
import os
from pathlib import Path

PASTA = Path(os.environ.get("APPDATA") or Path.home()) / "SecretShop"
ARQUIVO = PASTA / "historico_total.json"
CHAVES_ITENS = ("marca", "medalha", "amizade")
CONTAGENS = ("sessoes", "segundos", "renovacoes", "pedras", "ouro")


def vazio():
    dados = {"desde": None}
    dados.update({campo: 0 for campo in CONTAGENS})
    dados["itens"] = {chave: {"compras": 0, "unidades": 0} for chave in CHAVES_ITENS}
    return dados


def _contagem(valor):
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0 else 0


def carregar():
    """Lê o histórico. Sem arquivo, ou com um arquivo estragado, começa do zero em vez de travar o programa."""
    dados = vazio()
    try:
        salvo = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dados
    if not isinstance(salvo, dict):
        return dados
    if isinstance(salvo.get("desde"), str):
        dados["desde"] = salvo["desde"]
    for campo in CONTAGENS:
        dados[campo] = _contagem(salvo.get(campo))
    itens = salvo.get("itens") if isinstance(salvo.get("itens"), dict) else {}
    for chave in CHAVES_ITENS:
        item = itens.get(chave) if isinstance(itens.get(chave), dict) else {}
        dados["itens"][chave] = {"compras": _contagem(item.get("compras")), "unidades": _contagem(item.get("unidades"))}
    return dados


def somar(base, sessao):
    total = vazio()
    total["desde"] = base["desde"] or sessao["desde"]
    for campo in CONTAGENS:
        total[campo] = base[campo] + sessao[campo]
    for chave in CHAVES_ITENS:
        for campo in ("compras", "unidades"):
            total["itens"][chave][campo] = base["itens"][chave][campo] + sessao["itens"][chave][campo]
    return total


def salvar(dados):
    """Grava num arquivo à parte e troca de uma vez: se o PC desligar no meio, o histórico anterior continua inteiro."""
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        temporario = ARQUIVO.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporario, ARQUIVO)
        return True
    except OSError:
        return False
