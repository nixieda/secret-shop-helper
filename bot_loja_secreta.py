"""Bot da Loja Secreta do Epic Seven (cliente de PC da Steam ou do STOVE).

Renova a loja, desce a lista e compra Marca-Páginas da Aliança, Medalhas Místicas
e, se você pedir, Pontos de Amizade. Aperte F8 a qualquer momento para parar.
A interface gráfica fica em interface.py; este arquivo também funciona sozinho:

    python bot_loja_secreta.py --testar           só olha a tela, não clica em nada
    python bot_loja_secreta.py --renovacoes 100   renova 100 vezes (300 Pedras Celestes)
"""
import argparse
import ctypes
import sys
import time
from collections import Counter
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from idiomas import formatar, t

if getattr(sys, "frozen", False):  # no .exe, as imagens vêm no pacote e o que é gravado fica ao lado dele
    PASTA, PASTA_RECURSOS = Path(sys.executable).parent, Path(sys._MEIPASS)
else:
    PASTA = PASTA_RECURSOS = Path(__file__).resolve().parent
PASTA_MODELOS = PASTA_RECURSOS / "modelos"
PASTA_CAPTURAS = PASTA / "capturas"
ARQUIVO_LOG = PASTA / "historico.log"

VERSAO = "1.2.1"
PROJETO = "github.com/nixieda/secret-shop-helper"
KOFI = "https://ko-fi.com/nixieda"
CHAVE_PIX = "d8d05d06-fd35-47f7-9cec-91ed5a06b250"

TITULO_JANELA = "Epic Seven"
CUSTO_RENOVACAO = 3

# Todas as coordenadas abaixo são nesta resolução; a captura é redimensionada para ela.
BASE = (1769, 995)
PROPORCAO = BASE[0] / BASE[1]
TOLERANCIA_PROPORCAO = 0.03
FOLGA_TELA = 16  # pixels que a janela pode passar da tela sem atrapalhar os cliques
ALTURA_MINIMA = 576
COLUNA_ICONES = (740, 95, 930, 995)
REGIAO_LOJA = (90, 870, 270, 960)
REGIAO_LISTA = (600, 110, 1769, 995)
# ícone e nome nas posições das linhas 2 a 4: o aviso da compra cobre a 1ª linha, e o botão apaga depois da compra
X_ICONE_E_NOME = (770, 1400)
FAIXAS_DAS_LINHAS = ((334, 484), (534, 684), (735, 885))
# a moeda do preço nestas posições diz onde a lista está, sem precisar arrastar para descobrir
REGIAO_MOEDA_TOPO = (1465, 118, 1541, 186)  # 1ª linha, com a lista no topo
REGIAO_MOEDA_LINHA4 = (1465, 718, 1541, 786)  # 4ª linha: é das últimas a chegar quando a lista nova entra deslizando
REGIAO_MOEDA_FIM = (1465, 820, 1541, 888)  # última linha, com a lista no fim
REGIAO_DIALOGO = (700, 560, 1000, 770)
REGIAO_ICONE_DIALOGO = (670, 410, 830, 570)
BOTAO_RENOVAR = (305, 915)
FAIXA_RENOVAR = (110, 885, 500, 955)
X_COMPRAR = 1600
# os modelos das confirmações mostram só o encontro dos dois botões, sem texto; o clique é à direita
DX_CONFIRMAR, DX_COMPRAR = 151, 323
DY_COMPRAR = 36  # distância vertical entre o centro do ícone e o botão Comprar
LIMITE_Y_BOTAO = 960
# medido no jogo: a lista anda 300 e, com menos de 360, o arrasto rápido às vezes não chega ao fim
ARRASTO_X, ARRASTO_ALTO, ARRASTO_BAIXO = 1100, 420, 800
PASSOS_ARRASTO, TEMPO_PASSO = 4, 0.015
PONTO_NEUTRO = (300, 400)
ALTURA_SALDO = 90  # faixa do topo da tela, onde aparecem o ouro e as Pedras Celestes

ESCALAS = (1.0, 0.985, 1.015, 0.97, 1.03)
NOTA_CERTEZA, NOTA_DESCARTE = 0.9, 0.5  # com a escala 1 já decidida, não testa as outras
LIMIAR_ITEM = 0.80
# Medalha e Marca-Páginas: perder um custa muito mais que o ouro de um engano. Em mais de 1.300 linhas reais, o ícone
# errado mais parecido deu 0,51; o certo, mesmo com o desenho bem piorado, fica acima disso
LIMIAR_ITEM_VALIOSO = 0.60
# segunda via: o começo do preço, na lista (2 algarismos) e na janela de compra (3, porque lá 18,000 e 184,000 começam igual)
REGIAO_MOEDAS = (1465, 95, 1541, 995)
PRECO_X = (1582, 1638)
PRECO_ACIMA, PRECO_ABAIXO = 26, 28  # em relação ao centro da moeda da linha
DY_ICONE_MOEDA = 38  # distância vertical entre a moeda do preço e o centro do ícone
DISTANCIA_LINHAS = 60  # metade da distância entre uma linha e outra da lista
REGIAO_PRECO_JANELA = (888, 682, 956, 730)
LIMIAR_PRECO_JANELA = 0.94  # em janelas reais, 380,000 deu 0,92 contra o molde de 280,000; o preço certo fica acima de 0,96
# quanto tempo cada posição da lista é observada antes de seguir: em cima, mais, porque as 2 primeiras linhas só aparecem ali
SEGUNDOS_OLHANDO_TOPO, SEGUNDOS_OLHANDO_FIM = 0.4, 0.25
SEGUNDOS_FIRME = 0.25  # parada por esse tempo, a lista parou mesmo
SEGUNDOS_ATE_PARAR = 8  # nenhuma lista demora mais que isso para parar; evita ficar preso se algo se mexer sem fim
# paciência para PC lento, gasta só quando a lista demora: com o jogo em 1 núcleo, ela levou até 3 s para chegar
TENTATIVAS_LISTA, TENTATIVAS_LISTA_NOVA = 60, 200
SEGUNDOS_SERVIDOR = 40  # quanto esperar a resposta do jogo antes de parar: com internet ruim, o Loading fica até ela voltar
SEGUNDOS_POR_CLIQUE = 0.8  # janela de confirmação ainda aberta depois disso: o clique não valeu
LIMIAR_LOJA = 0.75
LIMIAR_TOPO = 0.75
LIMIAR_BOTAO_ABERTO = 0.9
LIMIAR_BOTAO_DIALOGO = 0.85
# no jogo real, a janela só aceitou o clique em 8 de 8 vezes a partir de 50 ms depois de aparecer
ESPERA_BOTAO = 0.12
LIMIAR_RENOVAR_ATIVO = 0.15
LIMIAR_BOTAO_ATIVO = 0.10
LIMIAR_LISTA_PARADA = 1.5
LIMIAR_LISTA_OUTRA = 0.75  # em 1.786 comparações reais, a mesma lista deu 0,81 ou mais; uma lista nova, 0,69 ou menos
FRACAO_TELA_CLARA = 0.85  # abaixo disso a tela ainda está escurecida por uma janela
SEGUNDOS_MOUSE_PARADO = 2

VK_F8 = 0x77
PW_CAPTURA_CLIENTE = 3
MOUSE_MOVE, MOUSE_DOWN, MOUSE_UP = 0x0001, 0x0002, 0x0004
MOUSE_VIRTUAL, MOUSE_ABSOLUTO = 0x4000, 0x8000
GA_RAIZ = 2
SW_RESTAURAR = 9
SWP_SEM_ORDEM, SWP_SEM_ATIVAR = 0x0004, 0x0010
PROCESSO_SO_CONSULTA = 0x1000
TOKEN_CONSULTA = 0x0008
TOKEN_ELEVACAO = 20

# com os tipos declarados, para os handles de 64 bits não serem cortados; separado de ctypes.windll para não mexer no resto
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_advapi32.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
_advapi32.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))


@dataclass(frozen=True)
class Item:
    chave: str
    arquivo: str
    preco: int
    quantidade: int  # unidades que vêm em cada compra
    padrao: bool = True  # comprado sem precisar pedir na linha de comando
    limiar: float = LIMIAR_ITEM  # nota mínima do ícone
    limiar_preco: Optional[float] = None  # nota mínima do preço na lista; sem ela, o item não tem segunda via
    limite_sem_ver: Optional[int] = None  # listas seguidas sem ver o item antes de parar e avisar; bem acima das fases ruins da loja

    @property
    def nome(self):
        return t(f"item_{self.chave}")


ITENS = (
    # nas telas reais, o preço diferente mais parecido deu 0,73 com o 184,000 e 0,90 com o 280,000 (era 380,000)
    Item("marca", "marca_paginas.png", 184_000, 5, limiar=LIMIAR_ITEM_VALIOSO, limiar_preco=0.85, limite_sem_ver=300),
    Item("medalha", "medalha_mistica.png", 280_000, 50, limiar=LIMIAR_ITEM_VALIOSO, limiar_preco=0.93, limite_sem_ver=600),
    Item("amizade", "pontos_amizade.png", 18_000, 50, padrao=False),
)


@dataclass(frozen=True)
class Limites:
    """Quando parar: o primeiro limite atingido encerra, e o que ficar vazio não limita."""
    pedras: Optional[int] = None
    ouro: Optional[int] = None
    unidades: dict = field(default_factory=dict)  # Item -> quantas unidades comprar

    @property
    def renovacoes(self):
        return None if self.pedras is None else self.pedras // CUSTO_RENOVACAO


class Parada(Exception):
    """Motivo para encerrar o bot sem gastar mais nada. O texto segue o idioma escolhido."""

    def __init__(self, chave, **dados):
        super().__init__(chave)
        self.chave = chave
        self.dados = dados

    def __str__(self):
        return t(self.chave, **self.dados)


class ParadaPedida(Parada):
    """O próprio usuário pediu para parar."""


def log(mensagem):
    agora = datetime.now()
    print(f"{agora:%H:%M:%S} {mensagem}", flush=True)
    try:
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"{agora:%Y-%m-%d %H:%M:%S} {mensagem}\n")
    except OSError:
        pass  # sem permissão de escrita na pasta: o histórico não pode derrubar o bot


def mascara_verde(imagem):
    hsv = cv2.cvtColor(imagem, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (35, 80, 70), (90, 255, 255))


def fracao_verde(quadro, regiao):
    x1, y1, x2, y2 = regiao
    return float((mascara_verde(quadro[y1:y2, x1:x2]) > 0).mean())


_modelos_em_escala = {}


def modelo_em_escala(modelo, escala):
    if escala == 1.0:
        return modelo
    chave = (id(modelo), escala)
    if chave not in _modelos_em_escala:
        _modelos_em_escala[chave] = cv2.resize(modelo, None, fx=escala, fy=escala)
    return _modelos_em_escala[chave]


def melhor_encaixe(quadro, regiao, modelo, escalas=(1.0,)):
    """Devolve (nota, x do centro, y do centro) do melhor encaixe do modelo na região."""
    x1, y1, x2, y2 = regiao
    recorte = quadro[y1:y2, x1:x2]
    melhor = (-1.0, 0, 0)
    for escala in escalas:
        m = modelo_em_escala(modelo, escala)
        resultado = cv2.matchTemplate(recorte, m, cv2.TM_CCOEFF_NORMED)
        _, nota, _, (px, py) = cv2.minMaxLoc(resultado)
        if nota > melhor[0]:
            melhor = (nota, x1 + px + m.shape[1] // 2, y1 + py + m.shape[0] // 2)
        if nota >= NOTA_CERTEZA or nota < NOTA_DESCARTE:
            break
    return melhor


def localizar_item(quadro, modelo, limiar=LIMIAR_ITEM):
    nota, x, y = melhor_encaixe(quadro, COLUNA_ICONES, modelo, ESCALAS)
    return (x, y) if nota >= limiar else None


def linhas_de_preco(quadro, moeda):
    """Devolve o y do centro de cada moeda visível na coluna de preços."""
    x1, y1, x2, y2 = REGIAO_MOEDAS
    resultado = cv2.matchTemplate(quadro[y1:y2, x1:x2], moeda, cv2.TM_CCOEFF_NORMED)
    linhas = []
    while True:
        _, nota, _, (_, py) = cv2.minMaxLoc(resultado)
        if nota < LIMIAR_TOPO:
            return sorted(linhas)
        linhas.append(y1 + py + moeda.shape[0] // 2)
        resultado[max(0, py - DISTANCIA_LINHAS):py + DISTANCIA_LINHAS, :] = -1


def localizar_por_preco(quadro, moeda, modelo, limiar):
    """Procura a linha com o preço do item e devolve o y onde fica o ícone dela, ou None."""
    x1, x2 = PRECO_X
    for y in linhas_de_preco(quadro, moeda):
        regiao = quadro[max(0, y - PRECO_ACIMA):y + PRECO_ABAIXO, x1:x2]
        if regiao.shape[0] < modelo.shape[0]:
            continue
        if cv2.minMaxLoc(cv2.matchTemplate(regiao, modelo, cv2.TM_CCOEFF_NORMED))[1] >= limiar:
            return y + DY_ICONE_MOEDA
    return None


def botao_comprar_ativo(quadro, y_icone):
    y = y_icone + DY_COMPRAR
    return fracao_verde(quadro, (1475, y - 30, 1720, y + 30)) >= LIMIAR_BOTAO_ATIVO


def lista_diferenca(a, b):
    x1, y1, x2, y2 = REGIAO_LISTA
    return float(cv2.absdiff(a[y1:y2, x1:x2], b[y1:y2, x1:x2]).mean())


def lista_semelhanca(a, b):
    """Nota da linha que mais mudou. Parecida apesar do brilho: a tela escurecendo por causa de uma janela não conta como lista nova."""
    x1, x2 = X_ICONE_E_NOME
    notas = []
    for y1, y2 in FAIXAS_DAS_LINHAS:
        pa = cv2.cvtColor(a[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        pb = cv2.cvtColor(b[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        notas.append(float(cv2.matchTemplate(pb, pa, cv2.TM_CCOEFF_NORMED)[0, 0]))
    return min(notas)


def _processo_como_admin(processo):
    """True se o processo roda como administrador, False se não, None se o Windows não deixar saber."""
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(processo, TOKEN_CONSULTA, ctypes.byref(token)):
        return None
    try:
        elevado, tamanho = wintypes.DWORD(), wintypes.DWORD()
        if not _advapi32.GetTokenInformation(token, TOKEN_ELEVACAO, ctypes.byref(elevado), ctypes.sizeof(elevado), ctypes.byref(tamanho)):
            return None
        return bool(elevado.value)
    finally:
        _kernel32.CloseHandle(token)


def bot_como_admin():
    return bool(_processo_como_admin(_kernel32.GetCurrentProcess()))


def janela_como_admin(hwnd):
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    processo = _kernel32.OpenProcess(PROCESSO_SO_CONSULTA, False, pid.value)
    if not processo:
        return None
    try:
        return _processo_como_admin(processo)
    finally:
        _kernel32.CloseHandle(processo)


def jogo_precisa_admin(hwnd=None):
    """O STOVE abre o jogo como administrador, e o Windows não deixa um programa comum ver nem clicar nele."""
    hwnd = hwnd or ctypes.windll.user32.FindWindowW(None, TITULO_JANELA)
    return bool(hwnd) and janela_como_admin(hwnd) is True and not bot_como_admin()


class InfoMonitor(ctypes.Structure):
    _fields_ = [("tamanho", wintypes.DWORD), ("monitor", wintypes.RECT), ("util", wintypes.RECT), ("opcoes", wintypes.DWORD)]


def areas_do_monitor(hwnd):
    """Devolve a área útil (sem a barra de tarefas) e a área total do monitor onde a janela está."""
    user32 = ctypes.windll.user32
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, ctypes.POINTER(InfoMonitor))
    info = InfoMonitor(ctypes.sizeof(InfoMonitor))
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
    util, monitor = info.util, info.monitor
    return (util.left, util.top, util.right, util.bottom), (monitor.left, monitor.top, monitor.right, monitor.bottom)


def janela_ajustada(janela, cliente, util, monitor):
    """Calcula onde a janela do jogo deve ficar para a área do jogo ser 16:9 e caber na tela.

    Recebe retângulos (esquerda, topo, direita, base) e devolve (x, y, largura, altura), ou None se já estiver boa.
    """
    cx1, cy1, cx2, cy2 = cliente
    ax1, ay1, ax2, ay2 = util
    largura, altura = cx2 - cx1, cy2 - cy1
    em_16_9 = largura > 0 and altura > 0 and abs(largura / altura - PROPORCAO) <= TOLERANCIA_PROPORCAO
    tela_cheia = cliente == monitor  # a barra de tarefas fica atrás do jogo e não atrapalha
    cabe = cx1 >= ax1 - FOLGA_TELA and cy1 >= ay1 - FOLGA_TELA and cx2 <= ax2 + FOLGA_TELA and cy2 <= ay2 + FOLGA_TELA
    if em_16_9 and altura >= ALTURA_MINIMA and (cabe or tela_cheia):
        return None

    jx1, jy1, jx2, jy2 = janela
    borda_x, borda_y = jx2 - jx1 - largura, jy2 - jy1 - altura
    maximo_a = min(ay2 - ay1 - borda_y, round((ax2 - ax1 - borda_x) / PROPORCAO))
    nova_a = min(altura, round(largura / PROPORCAO)) if largura > 0 and altura > 0 else maximo_a
    nova_a = min(max(nova_a, ALTURA_MINIMA), maximo_a)
    nova_l = round(nova_a * PROPORCAO)
    total_l, total_a = nova_l + borda_x, nova_a + borda_y
    return max(ax1, min(jx1, ax2 - total_l)), max(ay1, min(jy1, ay2 - total_a)), total_l, total_a


class Janela:
    """Enxerga e clica na janela do jogo."""

    def __init__(self, parar=None):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.parar = parar  # threading.Event opcional, usado pela interface
        self.pausado = None  # texto que explica a pausa atual
        self.ajustou = False
        self.cursor_do_bot = None
        self.hwnd = self.user32.FindWindowW(None, TITULO_JANELA)
        if not self.hwnd:
            raise Parada("nao_achei_jogo")
        if jogo_precisa_admin(self.hwnd):
            raise Parada("precisa_admin")
        self.user32.GetAsyncKeyState(VK_F8)

    def aberta(self):
        return bool(self.user32.IsWindow(self.hwnd))

    def _area_cliente(self):
        if not self.aberta():
            raise Parada("jogo_fechado")
        retangulo = wintypes.RECT()
        origem = wintypes.POINT(0, 0)
        self.user32.GetClientRect(self.hwnd, ctypes.byref(retangulo))
        self.user32.ClientToScreen(self.hwnd, ctypes.byref(origem))
        return origem.x, origem.y, retangulo.right, retangulo.bottom

    def ajustar_janela(self):
        """Deixa a área do jogo em 16:9 e inteira na tela. Mexe só na janela do jogo, nunca na resolução do Windows."""
        if self.user32.IsIconic(self.hwnd) or self.user32.IsZoomed(self.hwnd):
            self.user32.ShowWindow(self.hwnd, SW_RESTAURAR)
            self.esperar(1)
        util, monitor = areas_do_monitor(self.hwnd)
        x, y, largura, altura = self._area_cliente()
        ret = wintypes.RECT()
        self.user32.GetWindowRect(self.hwnd, ctypes.byref(ret))
        novo = janela_ajustada((ret.left, ret.top, ret.right, ret.bottom), (x, y, x + largura, y + altura), util, monitor)
        if novo is None:
            return
        self.user32.SetWindowPos(self.hwnd, 0, *novo, SWP_SEM_ORDEM | SWP_SEM_ATIVAR)
        for _ in range(12):  # o jogo leva um instante para redesenhar no tamanho novo
            self.esperar(0.25)
            _, _, largura, altura = self._area_cliente()
            if largura and altura and abs(largura / altura - PROPORCAO) <= TOLERANCIA_PROPORCAO:
                self.esperar(1)
                self.ajustou = True
                log(t("log_janela", largura=largura, altura=altura))
                return
        raise Parada("nao_16_9", largura=largura, altura=altura)

    def capturar(self):
        while True:
            _, _, largura, altura = self._area_cliente()
            if largura and altura and not self.user32.IsIconic(self.hwnd):
                break
            self.pausado = "pausado"
            self.esperar(0.5)
        self.pausado = None
        if abs(largura / altura - PROPORCAO) > TOLERANCIA_PROPORCAO:
            raise Parada("nao_16_9", largura=largura, altura=altura)
        dc = self.user32.GetDC(self.hwnd)
        memoria = self.gdi32.CreateCompatibleDC(dc)
        bitmap = self.gdi32.CreateCompatibleBitmap(dc, largura, altura)
        anterior = self.gdi32.SelectObject(memoria, bitmap)
        self.user32.PrintWindow(self.hwnd, memoria, PW_CAPTURA_CLIENTE)
        self.gdi32.SelectObject(memoria, anterior)  # o bitmap não pode estar selecionado para ser lido e apagado
        cabecalho = wintypes.DWORD * 10
        info = cabecalho(40, largura, wintypes.DWORD(-altura & 0xFFFFFFFF).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
        dados = ctypes.create_string_buffer(largura * altura * 4)
        self.gdi32.GetDIBits(memoria, bitmap, 0, altura, dados, info, 0)
        self.gdi32.DeleteObject(bitmap)
        self.gdi32.DeleteDC(memoria)
        self.user32.ReleaseDC(self.hwnd, dc)
        quadro = np.frombuffer(dados, np.uint8).reshape(altura, largura, 4)[:, :, :3]
        if (largura, altura) != BASE:
            return cv2.resize(quadro, BASE, interpolation=cv2.INTER_AREA)
        return quadro.copy()

    def esperar(self, segundos):
        fim = time.monotonic() + segundos
        while True:
            if self.user32.GetAsyncKeyState(VK_F8) & 0x8001:
                raise ParadaPedida("parou_f8")
            if self.parar and self.parar.is_set():
                raise ParadaPedida("parou_botao")
            restante = fim - time.monotonic()
            if restante <= 0:
                return
            time.sleep(min(restante, 0.05))

    def trazer_para_frente(self):
        self.user32.SetForegroundWindow(self.hwnd)

    def _aguardar_foco(self):
        avisou = False
        while self.user32.GetForegroundWindow() != self.hwnd:
            if not avisou:
                log(t("log_pausado"))
                avisou = True
                self.pausado = "pausado"
            self.esperar(0.2)
        if avisou:
            self.esperar(1)
            self.pausado = None

    def _cursor(self):
        ponto = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(ponto))
        return ponto.x, ponto.y

    def _aguardar_mouse(self):
        """Se a pessoa mexeu no mouse, espera ele ficar parado para o clique não disputar com ela."""
        atual = self._cursor()
        if self.cursor_do_bot is None or max(abs(atual[0] - self.cursor_do_bot[0]), abs(atual[1] - self.cursor_do_bot[1])) <= 2:
            return
        log(t("log_mouse"))
        self.pausado = "pausado_mouse"
        parado_desde = time.monotonic()
        while time.monotonic() - parado_desde < SEGUNDOS_MOUSE_PARADO:
            self.esperar(0.1)
            agora = self._cursor()
            if agora != atual:
                atual, parado_desde = agora, time.monotonic()
        self.cursor_do_bot = atual
        self.pausado = None

    def _para_tela(self, x, y):
        esquerda, topo, largura, altura = self._area_cliente()
        return esquerda + round(x * largura / BASE[0]), topo + round(y * altura / BASE[1])

    def _mover(self, x, y, botao=0):
        """Move o mouse e, se pedido, aperta ou solta no mesmo evento, para o clique cair sempre no ponto certo."""
        vx, vy, vl, va = (self.user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))
        nx = round((x - vx) * 65535 / (vl - 1))
        ny = round((y - vy) * 65535 / (va - 1))
        self.user32.mouse_event(MOUSE_MOVE | MOUSE_ABSOLUTO | MOUSE_VIRTUAL | botao, nx, ny, 0, 0)

    def _preparar_ponto(self, x, y):
        """Só libera o clique com o jogo na frente, o mouse livre e o jogo mesmo sob o ponto."""
        self._aguardar_foco()
        self._aguardar_mouse()
        self._aguardar_foco()
        tx, ty = self._para_tela(x, y)
        sob_o_ponto = self.user32.WindowFromPoint(wintypes.POINT(tx, ty))
        if self.user32.GetAncestor(sob_o_ponto, GA_RAIZ) != self.hwnd:
            raise Parada("cobrindo")
        return tx, ty

    def clicar(self, x, y):
        tx, ty = self._preparar_ponto(x, y)
        self._mover(tx, ty)
        time.sleep(0.05)
        self._mover(tx, ty, MOUSE_DOWN)
        time.sleep(0.06)
        self._mover(tx, ty, MOUSE_UP)
        self.cursor_do_bot = self._cursor()

    def arrastar(self, x, y1, y2, lentidao=0):
        """lentidao 0 é o arrasto rápido; um jogo lento pode não perceber esse, e as outras dão mais tempo a ele."""
        inicio = self._preparar_ponto(x, y1)
        fim = self._preparar_ponto(x, y2)
        passos = PASSOS_ARRASTO * (1 + 2 * lentidao)
        self._mover(*inicio)
        time.sleep(0.03)
        self._mover(*inicio, MOUSE_DOWN)
        try:
            for passo in range(1, passos + 1):
                self._mover(inicio[0], inicio[1] + (fim[1] - inicio[1]) * passo // passos)
                time.sleep(TEMPO_PASSO)
        finally:
            self._mover(*fim, MOUSE_UP)
            self.cursor_do_bot = self._cursor()


class Bot:
    def __init__(self, janela, modelos, telas, itens=ITENS):
        self.j = janela
        self.modelos = modelos
        self.telas = telas
        self.itens = tuple(itens)
        self.limites = Limites()
        self.renovacoes = 0
        self.compras = Counter()
        self.fim = None  # o que encerrou: "pedras", "ouro" ou o Item cuja meta foi atingida
        self.verde_livre = 0.0
        self.lista_nova = False  # a lista aberta antes do início pode ter itens já comprados; uma recém-renovada, não
        self.nao_vistos = []  # itens que a última lista não mostrou
        self.listas_sem_ver = Counter()

    # ---------- o que está na tela ----------

    def achar_item(self, quadro, item):
        """Procura o item pelo ícone e, se não achar, pelo preço. Devolve o y do ícone, ou None."""
        achado = localizar_item(quadro, self.modelos[item], item.limiar)
        if achado is not None:
            return achado[1]
        if item.limiar_preco is None:
            return None
        return localizar_por_preco(quadro, self.telas["topo"], self.telas[f"preco_{item.chave}"], item.limiar_preco)

    def janela_mostra(self, quadro, item):
        """A janela de compra é mesmo deste item? Vale o ícone ou o preço."""
        if melhor_encaixe(quadro, REGIAO_ICONE_DIALOGO, self.modelos[item], ESCALAS)[0] >= item.limiar:
            return True
        if item.limiar_preco is None:
            return False
        return melhor_encaixe(quadro, REGIAO_PRECO_JANELA, self.telas[f"janela_preco_{item.chave}"])[0] >= LIMIAR_PRECO_JANELA

    def esta_na_loja(self, quadro):
        nota, _, _ = melhor_encaixe(quadro, REGIAO_LOJA, self.telas["loja"])
        return nota >= LIMIAR_LOJA and fracao_verde(quadro, FAIXA_RENOVAR) >= LIMIAR_RENOVAR_ATIVO

    def esta_livre(self, quadro):
        """Na loja e já sem o escurecimento que uma janela deixa enquanto fecha."""
        verde = fracao_verde(quadro, FAIXA_RENOVAR)
        return self.esta_na_loja(quadro) and verde >= FRACAO_TELA_CLARA * self.verde_livre

    def tem_moeda(self, quadro, regiao):
        return melhor_encaixe(quadro, regiao, self.telas["topo"], ESCALAS)[0] >= LIMIAR_TOPO

    def esta_no_topo(self, quadro):
        return self.tem_moeda(quadro, REGIAO_MOEDA_TOPO)

    def esta_no_fim(self, quadro):
        return self.tem_moeda(quadro, REGIAO_MOEDA_FIM)

    def lista_nova_pronta(self, quadro):
        return self.esta_no_topo(quadro) and self.tem_moeda(quadro, REGIAO_MOEDA_LINHA4)

    def quadro_parado(self, pronto=None, tentativas=60):
        """Espera a lista parar. Devolve o quadro e se ela chegou mesmo aonde devia.

        Sem `pronto`, exige dois pares de quadros iguais: no alto do quique a lista para por um instante.
        """
        pares = 1 if pronto else 2
        anterior = self.j.capturar()
        iguais = 0
        for _ in range(tentativas):
            self.j.esperar(0.02)
            atual = self.j.capturar()
            iguais = iguais + 1 if lista_diferenca(anterior, atual) < LIMIAR_LISTA_PARADA else 0
            if iguais >= pares and (pronto is None or pronto(atual)):
                return atual, True
            anterior = atual
        return anterior, False

    def quadro_estavel(self):
        return self.quadro_parado()[0]

    def quadro_firme(self):
        """Espera a lista ficar parada por um tempo: num jogo com poucos quadros por segundo, dois quadros iguais não provam nada."""
        quadro = self.j.capturar()
        inicio = parada_desde = time.monotonic()
        while True:
            self.j.esperar(0.02)
            novo = self.j.capturar()
            agora = time.monotonic()
            if lista_diferenca(quadro, novo) >= LIMIAR_LISTA_PARADA:
                parada_desde = agora
            quadro = novo
            if agora - parada_desde >= SEGUNDOS_FIRME or agora - inicio >= SEGUNDOS_ATE_PARAR:
                return quadro

    def exigir_loja(self, quadro):
        if quadro.std() < 2:  # imagem de uma cor só: a captura não está enxergando o jogo
            raise Parada("tela_preta")
        if not self.esta_na_loja(quadro):
            raise Parada("loja_fechada")
        self.verde_livre = fracao_verde(quadro, FAIXA_RENOVAR)

    # ---------- limites ----------

    def meta_de_item_atingida(self):
        for item, unidades in self.limites.unidades.items():
            if self.compras[item] * item.quantidade >= unidades:
                return item
        return None

    def limite_atingido(self):
        """Confere, antes de gastar mais, se algum limite já impede continuar."""
        limites = self.limites
        item = self.meta_de_item_atingida()
        if item is not None:
            return item
        # sem ouro para o item mais barato, renovar só gastaria Pedras Celestes à toa
        if limites.ouro is not None and limites.ouro - self.ouro_gasto() < min(i.preco for i in self.itens):
            return "ouro"
        if limites.pedras is not None and (self.renovacoes + 1) * CUSTO_RENOVACAO > limites.pedras:
            return "pedras"
        return None

    # ---------- janelas de confirmação ----------

    def abrir_dialogo(self, ponto, modelo, deslocamento, acao):
        """Clica e espera a janela de confirmação terminar de abrir.

        O jogo às vezes ignora um clique. Repetir é seguro: só o botão de confirmação gasta algo.
        """
        for tentativa in range(3):
            if tentativa:
                log(t("clicando_de_novo", acao=acao))
            self.j.clicar(*ponto)
            for _ in range(30):  # cerca de 1,5 s; ela costuma aparecer em 350 ms
                self.j.esperar(0.01)
                if melhor_encaixe(self.j.capturar(), REGIAO_DIALOGO, modelo, ESCALAS)[0] >= LIMIAR_BOTAO_ABERTO:
                    self.j.esperar(ESPERA_BOTAO)  # clique durante a animação de abertura é ignorado
                    quadro = self.j.capturar()
                    nota, x, y = melhor_encaixe(quadro, REGIAO_DIALOGO, modelo, ESCALAS)
                    if nota >= LIMIAR_BOTAO_DIALOGO:
                        return (x + deslocamento, y), quadro
        raise Parada("sem_confirmacao", acao=acao)

    def confirmar(self, botao, modelo, acao):
        """Clica em confirmar e espera a tela liberar. A janela fecha em 200 ms; se seguir aberta, o clique não valeu.

        Com a janela já fechada, é o jogo esperando o servidor: clicar de novo não adianta, e internet lenta pede paciência.
        """
        self.j.clicar(*botao)
        cliques, neutros = 1, 0
        inicio = ultimo = time.monotonic()
        while time.monotonic() - inicio < SEGUNDOS_SERVIDOR:
            self.j.esperar(0.01)
            quadro = self.j.capturar()
            if self.esta_livre(quadro):
                return
            if time.monotonic() - ultimo < SEGUNDOS_POR_CLIQUE:
                continue
            if melhor_encaixe(quadro, REGIAO_DIALOGO, modelo, ESCALAS)[0] >= LIMIAR_BOTAO_DIALOGO:
                if cliques == 3:
                    break
                cliques += 1
                log(t("clicando_de_novo", acao=acao))
                self.j.clicar(*botao)
            elif neutros < 2:
                neutros += 1
                self.j.clicar(*PONTO_NEUTRO)  # fecha aviso de item recebido, se houver
            ultimo = time.monotonic()
        else:
            raise Parada("sem_resposta")
        raise Parada("janela_aberta", acao=acao)

    def comprar(self, item, y_icone):
        acao = t("acao_compra", item=item.nome)
        botao, quadro = self.abrir_dialogo((X_COMPRAR, y_icone + DY_COMPRAR), self.telas["comprar"], DX_COMPRAR, acao)
        if not self.janela_mostra(quadro, item):
            raise Parada("outro_item", item=item.nome)
        self.confirmar(botao, self.telas["comprar"], acao)
        inicio = time.monotonic()
        tentativa = 0
        while time.monotonic() - inicio < SEGUNDOS_SERVIDOR:
            tentativa += 1
            self.j.esperar(0.02)
            quadro = self.j.capturar()
            if self.esta_livre(quadro):
                if not botao_comprar_ativo(quadro, y_icone):  # a lista não anda com a compra: basta ver o botão apagar
                    self.compras[item] += 1
                    log(t("log_comprei", item=item.nome, total=self.compras[item]))
                    return
            elif tentativa in (40, 80):
                self.j.clicar(*PONTO_NEUTRO)  # fecha aviso de item recebido, se houver
        raise Parada("compra_sem_confirmar", item=item.nome)

    # ---------- lista ----------

    def ir_para_o_topo(self, quadro):
        """Só a lista que já estava aberta pode estar rolada: depois de renovar, o jogo volta ao topo sozinho."""
        for _ in range(3):
            if self.esta_no_topo(quadro):
                break
            self.j.arrastar(ARRASTO_X, ARRASTO_ALTO, ARRASTO_BAIXO)
            quadro, _ = self.quadro_parado(self.esta_no_topo, TENTATIVAS_LISTA)
        return quadro

    def descer_lista(self):
        """Desce e confere pela moeda da última linha. Se não chegar, tenta de novo, cada vez mais devagar."""
        for tentativa in range(3):
            if tentativa:
                log(t("log_redescida"))
            self.j.arrastar(ARRASTO_X, ARRASTO_BAIXO, ARRASTO_ALTO, tentativa)
            depois, chegou = self.quadro_parado(self.esta_no_fim, TENTATIVAS_LISTA)
            if chegou:
                return depois
        return depois

    def varrer_lista(self, quadro):
        """Olha o topo e o fim da lista, compra o que estiver marcado e devolve o último quadro."""
        faltam = self.nao_vistos = list(self.itens)
        for vista, segundos in enumerate((SEGUNDOS_OLHANDO_TOPO, SEGUNDOS_OLHANDO_FIM)):
            self.exigir_loja(quadro)
            quadro = self.comprar_o_que_aparecer(quadro, faltam, segundos)
            if self.fim is not None or not faltam or vista == 1:
                return quadro
            quadro = self.descer_lista()
        return quadro

    def comprar_o_que_aparecer(self, quadro, faltam, segundos):
        """Olha a lista por um instante, não só um quadro: num PC lento, parte da linha pode chegar depois do resto."""
        inicio = time.monotonic()
        prazo = inicio + segundos
        while True:
            for item in list(faltam):
                y = self.achar_item(quadro, item)
                if y is None or y + DY_COMPRAR > LIMITE_Y_BOTAO:
                    continue
                quadro = self.quadro_firme()  # a lista pode estar terminando de parar, e o clique precisa da posição final
                y = self.achar_item(quadro, item) or y
                faltam.remove(item)
                # numa lista recém-renovada nada pode estar comprado: botão apagado aí é só leitura errada
                if not self.lista_nova and not botao_comprar_ativo(quadro, y):
                    continue
                if self.limites.ouro is not None and self.ouro_gasto() + item.preco > self.limites.ouro:
                    self.fim = "ouro"
                    return quadro
                self.comprar(item, y)
                self.fim = self.meta_de_item_atingida()
                if self.fim is not None:
                    return quadro
                quadro = self.quadro_firme()  # o aviso da compra cobre a 1ª linha por um instante
            agora = time.monotonic()
            if not faltam or agora >= prazo or agora - inicio >= SEGUNDOS_ATE_PARAR:
                return quadro
            self.j.esperar(0.02)
            novo = self.j.capturar()
            if lista_diferenca(quadro, novo) >= LIMIAR_LISTA_PARADA:  # ainda andando: o tempo de olhar recomeça
                prazo = time.monotonic() + segundos
            quadro = novo

    def conferir_itens_vistos(self):
        """Último alarme: tempo demais sem ver um item pode ser o bot deixando de reconhecê-lo. Para antes de gastar mais."""
        for item in self.itens:
            self.listas_sem_ver[item] = self.listas_sem_ver[item] + 1 if item in self.nao_vistos else 0
            if item.limite_sem_ver is not None and self.listas_sem_ver[item] >= item.limite_sem_ver:
                raise Parada("sem_item", item=item.nome, n=self.listas_sem_ver[item])

    def renovar(self, antes):
        self.exigir_loja(antes)
        acao = t("acao_renovacao")
        botao, _ = self.abrir_dialogo(BOTAO_RENOVAR, self.telas["confirmar"], DX_CONFIRMAR, acao)
        self.confirmar(botao, self.telas["confirmar"], acao)
        inicio = time.monotonic()
        while time.monotonic() - inicio < SEGUNDOS_SERVIDOR:
            self.j.esperar(0.01)
            quadro = self.j.capturar()
            if self.esta_livre(quadro) and lista_semelhanca(antes, quadro) < LIMIAR_LISTA_OUTRA:
                self.renovacoes += 1
                self.lista_nova = True
                # as linhas novas entram deslizando, com uma pausa que parece a lista parada
                return self.quadro_parado(self.lista_nova_pronta, TENTATIVAS_LISTA_NOVA)[0]
        raise Parada("lista_igual")

    def rodar(self, limites):
        self.limites = limites
        quadro = self.quadro_estavel()
        self.exigir_loja(quadro)
        quadro = self.varrer_lista(self.ir_para_o_topo(quadro))
        while self.fim is None:
            self.fim = self.limite_atingido()
            if self.fim is not None:
                break
            self.conferir_itens_vistos()
            quadro = self.renovar(quadro)
            if limites.renovacoes is None:
                log(t("log_renovacao_livre", n=self.renovacoes))
            else:
                log(t("log_renovacao", n=self.renovacoes, total=limites.renovacoes))
            quadro = self.varrer_lista(quadro)

    def ouro_gasto(self):
        # percorre a lista fixa de itens, não o Counter: a interface lê isto enquanto o bot pode estar acrescentando uma chave
        return sum(item.preco * self.compras[item] for item in self.itens)

    def resumo(self):
        linhas = [t("resumo_renovacoes", n=self.renovacoes, pedras=self.renovacoes * CUSTO_RENOVACAO)]
        linhas += [f"{item.nome}: {self.compras[item]}" for item in self.itens]
        linhas.append(t("resumo_ouro", ouro=formatar(self.ouro_gasto())))
        return linhas


def ler_imagem(caminho):
    """Lê pelo Python porque cv2.imread falha em pastas com acento no Windows."""
    try:
        return cv2.imdecode(np.frombuffer(caminho.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        raise Parada("falta_arquivo", nome=caminho.name) from None


def carregar_modelos():
    modelos = {item: ler_imagem(PASTA_MODELOS / item.arquivo) for item in ITENS}
    telas = {
        "loja": ler_imagem(PASTA_MODELOS / "loja_renovar.png"),
        "topo": ler_imagem(PASTA_MODELOS / "moeda_topo.png"),
        "confirmar": ler_imagem(PASTA_MODELOS / "dialogo_confirmar.png"),
        "comprar": ler_imagem(PASTA_MODELOS / "dialogo_comprar.png"),
    }
    for item in ITENS:
        if item.limiar_preco is not None:
            telas[f"preco_{item.chave}"] = ler_imagem(PASTA_MODELOS / f"preco_{item.chave}.png")
            telas[f"janela_preco_{item.chave}"] = ler_imagem(PASTA_MODELOS / f"janela_preco_{item.chave}.png")
    return modelos, telas


def salvar_captura(quadro, nome):
    """Grava pelo Python pelo mesmo motivo de ler_imagem. Sem permissão na pasta, só avisa."""
    caminho = PASTA_CAPTURAS / f"{nome}_{datetime.now():%Y%m%d_%H%M%S}.png"
    try:
        PASTA_CAPTURAS.mkdir(exist_ok=True)
        caminho.write_bytes(cv2.imencode(".png", quadro)[1].tobytes())
    except OSError as erro:
        log(t("log_nao_salvei", nome=caminho.name, erro=erro))
    return caminho


def testar(janela, bot):
    quadro = janela.capturar()
    print(t("teste_loja", resposta=t("sim" if bot.esta_na_loja(quadro) else "nao")))
    marcado = quadro.copy()
    for item, modelo in bot.modelos.items():
        nota, x, y = melhor_encaixe(quadro, COLUNA_ICONES, modelo, ESCALAS)
        if nota < item.limiar:
            print(t("teste_sem_item", item=item.nome, nota=nota))
            continue
        ativo = botao_comprar_ativo(quadro, y)
        print(t("teste_item", item=item.nome, y=y, nota=nota, estado=t("ativo" if ativo else "inativo")))
        cv2.circle(marcado, (X_COMPRAR, y + DY_COMPRAR), 18, (0, 0, 255), 3)
    print(t("teste_imagem", caminho=salvar_captura(marcado, "teste")))


def executar(janela, bot, limites):
    """Roda do começo ao fim e devolve a Parada que interrompeu, ou None se chegou a um limite."""
    motivo = None
    try:
        log(t("log_inicio"))
        janela.trazer_para_frente()
        janela.ajustar_janela()
        janela.esperar(3)
        salvar_captura(janela.capturar()[:ALTURA_SALDO], "saldo_inicio")
        bot.rodar(limites)
        salvar_captura(janela.capturar()[:ALTURA_SALDO], "saldo_fim")
        log(t("log_terminei"))
    except ParadaPedida as erro:
        motivo = erro
        log(t("log_parei", motivo=erro))
    except Parada as erro:
        motivo = erro
        log(t("log_parei", motivo=erro))
        try:
            log(t("log_tela", caminho=salvar_captura(janela.capturar(), "parada")))
        except Parada:
            pass
    finally:
        for linha in bot.resumo():
            log(linha)
    return motivo


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--renovacoes", type=int, help="quantas vezes renovar a loja")
    parser.add_argument("--testar", action="store_true", help="só olha a tela, não clica em nada")
    parser.add_argument("--amizade", action="store_true", help="também compra Pontos de Amizade")
    args = parser.parse_args()

    try:
        janela = Janela()
        itens = [item for item in ITENS if item.padrao or args.amizade]
        bot = Bot(janela, *carregar_modelos(), itens)
        if args.testar:
            testar(janela, bot)
            return
        total = args.renovacoes
        if total is None:
            total = int(input(t("pergunta")))
        if total < 0:
            raise Parada("negativo")
        executar(janela, bot, Limites(pedras=total * CUSTO_RENOVACAO))
    except Parada as motivo:
        log(t("log_parei", motivo=motivo))


if __name__ == "__main__":
    main()
