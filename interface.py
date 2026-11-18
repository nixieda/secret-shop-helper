"""Interface gráfica do bot da Loja Secreta. O bot roda numa linha de execução separada."""
import ctypes
import json
import math
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import traceback
from ctypes import wintypes
from datetime import date
from pathlib import Path

import bot_loja_secreta as bot
import idiomas
import tema as T
import totais
from idiomas import formatar, t

PASTA_VISUAL = bot.PASTA_RECURSOS / "visual"
ARQUIVO_CONFIG = bot.PASTA / "config.json"
OPCOES_LIMITE = ("pedras", "ouro", "medalha", "marca")
LIMITES_PADRAO = {"pedras": "300", "ouro": "", "medalha": "", "marca": ""}
ITEM_DO_CAMPO = {"marca": bot.ITENS[0], "medalha": bot.ITENS[1]}
ICONE_DO_CAMPO = {"pedras": "gema", "ouro": "moeda", "medalha": "campo_medalha", "marca": "campo_marca"}
SEGUNDOS_POR_RENOVACAO = 4  # medido no jogo real
SEGUNDOS_COM_AMIZADE = 6  # Pontos de Amizade aparece na maioria das listas, e cada compra leva cerca de 2,6 s
PEDRAS_PARA_AGRADECER = 1000  # a janela de resultado, com o convite para apoiar, só aparece depois de sessões longas
SEGUNDOS_ENTRE_GRAVACOES = 20  # o histórico total é gravado durante a sessão, para não se perder se o PC desligar
ARG_REABERTO = "--reaberto"
NOME_TRAVA = "EpicSevenSecretShopHelper"

FONTE_NOME = ("Segoe UI Semibold", -15)
FONTE_DETALHE = ("Segoe UI", -12)
FONTE_PRECO = ("Segoe UI Semibold", -14)
FONTE_CAMPO = ("Segoe UI Semibold", -17)
FONTE_OPCAO = ("Segoe UI Semibold", -13)
FONTE_VALOR = ("Segoe UI Semibold", -20)
FONTE_CONTAGEM = ("Segoe UI Semibold", -18)
FONTE_CELULA = ("Segoe UI", -11)
FONTE_STATUS = ("Segoe UI", -13)
FONTE_TEXTO = ("Segoe UI", -14)
FONTE_BOTAO = ("Segoe UI Semibold", -14)
FONTE_CHAVE = ("Consolas", -14)
FONTE_DESTAQUE = ("Segoe UI Semibold", -26)
FONTE_AGRADECER = ("Segoe UI Semibold", -15)


def duracao(segundos):
    minutos = round(segundos / 60)
    if minutos < 1:
        return t("menos_de_1")
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60:02d} min"


def estimativa(segundos):
    return duracao(segundos) if segundos < 30 else t("cerca_de", tempo=duracao(segundos))


def limite_valido(texto):
    return texto == "" or (texto.isascii() and texto.isdigit() and len(texto) <= 10)


def renovacoes_por_extenso(total):
    return t("uma_renovacao" if total == 1 else "n_renovacoes", n=formatar(total))


def compras_por_extenso(total):
    return t("uma_compra" if total == 1 else "n_compras", n=formatar(total))


def posicao_ao_lado(jogo, area, tamanho):
    """Devolve (x, y) para a interface ficar ao lado do jogo, ou None se não couber."""
    jx1, jy1, jx2, _ = jogo
    ax1, ay1, ax2, ay2 = area
    largura, altura = tamanho
    y = max(min(jy1, ay2 - altura), ay1)
    if jx1 - largura - 12 >= ax1:
        return jx1 - largura - 12, y
    if jx2 + 12 + largura <= ax2:
        return jx2 + 12, y
    return None


def retangulos_do_jogo():
    """Devolve o retângulo da janela do jogo e a área útil do monitor dela, ou (None, None)."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, bot.TITULO_JANELA)
    if not hwnd or user32.IsIconic(hwnd):
        return None, None
    janela = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(janela))
    return (janela.left, janela.top, janela.right, janela.bottom), bot.areas_do_monitor(hwnd)[0]


def pintar_barra_de_titulo(janela):
    hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())

    def cor_do_windows(cor):
        r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
        return r | g << 8 | b << 16
    atributos = ((20, 1), (35, cor_do_windows(T.FUNDO)), (36, cor_do_windows(T.PRATA)), (34, cor_do_windows(T.OURO_ESCURO)))
    for atributo, valor in atributos:
        dado = ctypes.c_int(valor)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(dado), ctypes.sizeof(dado))


def abrir_link(endereco):
    """Abre no navegador padrão. O programa em si não acessa a internet."""
    try:
        os.startfile(endereco)
    except OSError:
        pass


def reabrir_como_admin():
    """Pede ao Windows para abrir outra cópia como administrador. Devolve False se a pessoa recusar."""
    shell32 = ctypes.WinDLL("shell32")
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    shell32.ShellExecuteW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int)
    if getattr(sys, "frozen", False):
        programa, parametros = sys.executable, ARG_REABERTO
    else:
        sem_console = Path(sys.executable).with_name("pythonw.exe")
        programa = str(sem_console if sem_console.exists() else sys.executable)
        parametros = f'"{Path(__file__).resolve()}" {ARG_REABERTO}'
    resultado = shell32.ShellExecuteW(None, "runas", programa, parametros, str(bot.PASTA), 1)
    return (resultado or 0) > 32


class Janelinha(tk.Toplevel):
    """Janela pequena com o visual do painel, aberta por cima da principal."""

    def __init__(self, app, chave, titulo, no_topo=False, modal=False):
        super().__init__(app)
        self.withdraw()
        self.app, self.chave, self.no_topo, self.modal = app, chave, no_topo, modal
        self.title(titulo)
        self.resizable(False, False)
        self.configure(bg=T.FUNDO)
        self.transient(app)
        self.medidas = T.JANELINHAS.get(chave) or T.JANELINHAS[f"{chave}_{idiomas.atual()}"]
        fundo = app.foto(f"janela_{chave}_{idiomas.atual()}")
        self.c = tk.Canvas(self, width=fundo.width(), height=fundo.height(), bd=0, highlightthickness=0, bg=T.FUNDO)
        self.c.pack()
        self.c.create_image(0, 0, anchor="nw", image=fundo)
        self.alvos = []  # (retângulo, função que pinta o estado, ação)
        self.sob = self.apertado = None
        self.c.bind("<Motion>", self._ao_mover)
        self.c.bind("<Leave>", self._ao_sair)
        self.c.bind("<ButtonPress-1>", self._ao_pressionar)
        self.c.bind("<ButtonRelease-1>", self._ao_soltar)
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.bind("<Escape>", lambda _: self.fechar())

    def mostrar(self):
        """Centraliza sobre a janela principal, sem passar da área útil do monitor dela."""
        self.update_idletasks()
        pintar_barra_de_titulo(self)
        largura, altura = self.c.winfo_reqwidth() + 16, self.c.winfo_reqheight() + 39
        ax1, ay1, ax2, ay2 = bot.areas_do_monitor(ctypes.windll.user32.GetParent(self.app.winfo_id()))[0]
        x = self.app.winfo_rootx() + (T.LARGURA - largura) // 2
        y = self.app.winfo_rooty() + max((T.ALTURA - altura) // 2 - 40, 0)
        x = max(ax1, min(x, ax2 - largura))
        y = max(ay1, min(y, ay2 - altura))
        self.geometry(f"+{x}+{y}")
        if self.no_topo:
            self.attributes("-topmost", True)
        self.deiconify()
        self.lift()
        self.focus_force()
        if self.modal:
            self.grab_set()

    def fechar(self):
        if self.app.janelinhas.get(self.chave) is self:
            del self.app.janelinhas[self.chave]
        self.destroy()

    def texto(self, x, y, texto, cor=T.PRATA, fonte=FONTE_TEXTO, ancora="nw", largura=None, alinhar="left"):
        return self.c.create_text(x, y, text=texto, fill=cor, font=fonte, anchor=ancora, width=largura, justify=alinhar)

    def paragrafo(self, y, texto, cor=T.PRATA, fonte=FONTE_TEXTO):
        return self.texto(T.JANELINHA_X1, y, texto, cor, fonte, largura=T.JANELINHA_X2 - T.JANELINHA_X1)

    def botao(self, x, y, estilo, tamanho, texto, acao):
        """Botão desenhado: a imagem de cada estado e o texto por cima. Devolve o texto, para poder trocá-lo."""
        w, h = T.BOTAO_GRANDE if tamanho == "grande" else T.BOTAO_PEQUENO
        nome = f"bt_{estilo}_{tamanho}"
        imagem = self.c.create_image(x, y, anchor="nw", image=self.app.foto(f"{nome}_normal"))
        rotulo = self.c.create_text(x + w / 2, y + h / 2, text=texto, font=FONTE_BOTAO, fill="#FCF8FE" if estilo == "roxo" else T.PRATA)

        def pintar(estado):
            self.c.itemconfigure(imagem, image=self.app.foto(f"{nome}_{estado}"))
            self.c.coords(rotulo, x + w / 2, y + h / 2 + (1 if estado == "pressionado" else 0))
        self.alvos.append(((x, y, x + w, y + h), pintar, acao))
        return rotulo

    def link(self, y, texto, acao):
        item = self.texto(T.JANELINHA_LARGURA / 2, y, texto, T.CINZA, FONTE_DETALHE, ancora="center")
        self.alvos.append((self.c.bbox(item), lambda estado: self.c.itemconfigure(item, fill=T.CINZA if estado == "normal" else T.OURO_CLARO), acao))

    def _alvo(self, x, y):
        for alvo in self.alvos:
            x1, y1, x2, y2 = alvo[0]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return alvo
        return None

    def _pintar(self):
        for alvo in self.alvos:
            if alvo is not self.sob:
                alvo[1]("normal")
            else:
                alvo[1]("pressionado" if alvo is self.apertado else "foco")
        self.c.configure(cursor="hand2" if self.sob else "")

    def _ao_mover(self, evento):
        alvo = self._alvo(evento.x, evento.y)
        if alvo is not self.sob:
            self.sob = alvo
            self._pintar()

    def _ao_sair(self, _):
        self.sob = None
        self._pintar()

    def _ao_pressionar(self, evento):
        self.apertado = self._alvo(evento.x, evento.y)
        self._pintar()

    def _ao_soltar(self, evento):
        alvo = self._alvo(evento.x, evento.y)
        apertado, self.apertado = self.apertado, None
        self._pintar()
        if alvo is not None and alvo is apertado:
            alvo[2]()  # pode fechar a janela: nada depois disso


class App(tk.Tk):
    def __init__(self, criar_janela=bot.Janela):
        super().__init__()
        self.withdraw()
        self.criar_janela = criar_janela
        self.resizable(False, False)
        self.configure(bg=T.FUNDO)
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.fotos = {}
        self.modelos, self.telas = bot.carregar_modelos()

        config = self._ler_config()
        idiomas.definir(config.get("idioma") if config.get("idioma") in idiomas.IDIOMAS else idiomas.PADRAO)
        marcados = config.get("itens")
        self.marcados = {}
        for item in bot.ITENS:
            if isinstance(marcados, list):
                # versões anteriores guardavam o nome em português
                self.marcados[item] = item.chave in marcados or idiomas.TEXTOS["pt"][f"item_{item.chave}"] in marcados
            else:
                self.marcados[item] = item.padrao
        self.limites_txt = {chave: tk.StringVar(value=valor) for chave, valor in self._limites_salvos(config).items()}
        self.limite_tipo = config.get("limite_tipo") if config.get("limite_tipo") in OPCOES_LIMITE else OPCOES_LIMITE[0]
        self.menu_aberto = False

        self.rodando = False
        self.mensagem_final = None
        self.sob = None
        self.pressionado = None
        self.limites_atuais = bot.Limites()
        self.inicio = 0.0
        self.quadro_chama = 0
        self.fim_do_aviso = 0.0
        self.item_do_aviso = None
        self.bot_atual = None
        self.janela_atual = None
        self.resultado = None
        self.trabalho = None
        self.pedido_parada = threading.Event()
        self.realces = {}
        self.vistos = {}
        self.barra_pintada = 0
        self.janelinhas = {}
        self.totais_base = None  # o histórico total do começo da sessão; None fora de uma sessão
        self.totais_gravados = None
        self.ultima_gravacao = 0.0
        self.fechando = False

        self.c = tk.Canvas(self, width=T.LARGURA, height=T.ALTURA, bd=0, highlightthickness=0, bg=T.FUNDO)
        self.c.pack()
        self.fundo = self.c.create_image(0, 0, anchor="nw")
        self.seletor = self.c.create_image(T.IDIOMA_RET[0], T.IDIOMA_RET[1], anchor="nw")
        self.ajuda = self.c.create_image(T.AJUDA_RET[0], T.AJUDA_RET[1], anchor="nw")
        self._montar_itens()
        self._montar_limites()
        self.botao = self.c.create_image(T.BOTAO_RET[0], T.BOTAO_RET[1], anchor="nw")
        self._montar_progresso()
        self.mais = self.c.create_image(T.MAIS_RET[0], T.MAIS_RET[1], anchor="nw")
        self._montar_menu()

        self.c.bind("<Motion>", self._ao_mover)
        self.c.bind("<Leave>", self._ao_sair)
        self.c.bind("<ButtonPress-1>", self._ao_pressionar)
        self.c.bind("<ButtonRelease-1>", self._ao_soltar)
        for variavel in self.limites_txt.values():
            variavel.trace_add("write", lambda *_: self._ao_mudar_opcoes())

        self.iconphoto(True, self.foto("icone"))
        self._aplicar_idioma()
        self.update_idletasks()
        self._pintar_barra_de_titulo()
        self._posicao_inicial()
        self.deiconify()

    # ---------- montagem ----------

    def foto(self, nome):
        if nome not in self.fotos:
            self.fotos[nome] = tk.PhotoImage(file=str(PASTA_VISUAL / f"{nome}.png"))
        return self.fotos[nome]

    def _pintar_barra_de_titulo(self):
        pintar_barra_de_titulo(self)

    def _montar_itens(self):
        self.linhas = {}
        for numero, item in enumerate(bot.ITENS):
            topo = T.PRIMEIRA_LINHA_Y + numero * T.ALTURA_LINHA
            meio = topo + T.ALTURA_LINHA // 2
            self.linhas[item] = {
                "realce": self.c.create_image(T.PAINEL_X1 + 8, topo + 3, anchor="nw", image=self.foto("linha_realce"), state="hidden"),
                "caixa": self.c.create_image(T.CHECK_X, meio),
                "icone": self.c.create_image(T.ICONE_X, meio),
                "nome": self.c.create_text(T.NOME_X, meio - 10, anchor="w", font=FONTE_NOME),
                "detalhe": self.c.create_text(T.NOME_X, meio + 11, anchor="w", font=FONTE_DETALHE),
                "preco": self.c.create_text(T.PRECO_X, meio, anchor="e", font=FONTE_PRECO),
                "moeda": self.c.create_image(0, meio, image=self.foto("moeda")),
                "meio": meio,
            }

    def _montar_limites(self):
        sx1, sy1, sx2, sy2 = T.SELETOR_LIMITE
        meio = (sy1 + sy2) // 2
        self.limite_botao = self.c.create_image(sx1, sy1, anchor="nw")
        self.limite_icone = self.c.create_image(sx1 + 19, meio)
        self.limite_nome = self.c.create_text(sx1 + 36, meio, anchor="w", font=FONTE_OPCAO, fill=T.PRATA)

        x1, y1, x2, y2 = T.CAMPO_LIMITE
        self.campo_foco = self.c.create_image((x1 + x2) // 2, (y1 + y2) // 2, image=self.foto("campo_foco"), state="hidden")
        self.entrada = tk.Entry(
            self, textvariable=self.limites_txt[self.limite_tipo], bd=0, relief="flat", highlightthickness=0, font=FONTE_CAMPO,
            bg=T.CAMPO, fg=T.PRATA, insertbackground=T.OURO_CLARO, selectbackground="#3A2A5C", selectforeground=T.PRATA,
            disabledbackground=T.CAMPO, disabledforeground=T.CINZA, validate="key", validatecommand=(self.register(limite_valido), "%P"))
        self.c.create_window(x1 + 12, (y1 + y2) // 2, anchor="w", window=self.entrada, width=x2 - x1 - 24, height=26)
        self.entrada.bind("<FocusIn>", self._ao_focar_campo)
        self.entrada.bind("<FocusOut>", lambda _: self.c.itemconfigure(self.campo_foco, state="hidden"))
        self.legenda = self.c.create_text(T.COLUNAS_X[0], T.LEGENDA_Y, anchor="w", width=T.PRECO_X - T.COLUNAS_X[0], font=FONTE_DETALHE)

    def _montar_menu(self):
        """Fica sobre o resto da janela, por isso é montado por último."""
        x1, _, x2, y2 = T.SELETOR_LIMITE
        topo = y2 + 2
        self.c.create_image(x1, topo, anchor="nw", image=self.foto("menu_limite"), tags="menu")
        self.menu_realce = self.c.create_image(x1 + 4, topo + 4, anchor="nw", image=self.foto("menu_realce"), tags="menu")
        self.menu_marca = self.c.create_image(x2 - 18, topo, image=self.foto("menu_marca"), tags="menu")
        self.menu_textos = {}
        for numero, chave in enumerate(OPCOES_LIMITE):
            meio = topo + 4 + numero * T.ALTURA_OPCAO + T.ALTURA_OPCAO // 2
            self.c.create_image(x1 + 19, meio, image=self.foto(ICONE_DO_CAMPO[chave]), tags="menu")
            self.menu_textos[chave] = self.c.create_text(x1 + 36, meio, anchor="w", font=FONTE_OPCAO, fill=T.PRATA, tags="menu")
        self.c.itemconfigure("menu", state="hidden")

    def _opcao_em(self, x, y):
        x1, _, x2, y2 = T.SELETOR_LIMITE
        numero = (y - (y2 + 6)) // T.ALTURA_OPCAO
        if x1 <= x <= x2 and 0 <= numero < len(OPCOES_LIMITE):
            return OPCOES_LIMITE[numero]
        return None

    def _abrir_menu(self):
        self.menu_aberto = True
        self.c.itemconfigure("menu", state="normal")
        self.c.tag_raise("menu")
        _, _, _, y2 = T.SELETOR_LIMITE
        indice = OPCOES_LIMITE.index(self.limite_tipo)
        self.c.coords(self.menu_marca, T.SELETOR_LIMITE[2] - 18, y2 + 6 + indice * T.ALTURA_OPCAO + T.ALTURA_OPCAO // 2)
        self._realcar_opcao(self.limite_tipo)
        self._repintar_seletor()

    def _fechar_menu(self):
        self.menu_aberto = False
        self.c.itemconfigure("menu", state="hidden")
        self._repintar_seletor()

    def _realcar_opcao(self, chave):
        if chave is None:
            self.c.itemconfigure(self.menu_realce, state="hidden")
            return
        _, _, _, y2 = T.SELETOR_LIMITE
        self.c.coords(self.menu_realce, T.SELETOR_LIMITE[0] + 4, y2 + 6 + OPCOES_LIMITE.index(chave) * T.ALTURA_OPCAO)
        self.c.itemconfigure(self.menu_realce, state="normal")

    def _escolher_limite(self, chave):
        self.limite_tipo = chave
        self.entrada.configure(textvariable=self.limites_txt[chave])
        self._fechar_menu()
        self._mostrar_limite_escolhido()
        self._ao_mudar_opcoes()
        self._salvar_config()
        self.entrada.focus_set()  # pronto para digitar o valor da opção escolhida
        self.entrada.selection_range(0, "end")
        self.entrada.icursor("end")

    def _mostrar_limite_escolhido(self):
        self.c.itemconfigure(self.limite_icone, image=self.foto(ICONE_DO_CAMPO[self.limite_tipo]))
        self.c.itemconfigure(self.limite_nome, text=t(f"limite_{self.limite_tipo}"))

    def _repintar_seletor(self):
        if self.rodando:
            estado = "travado"
        elif self.menu_aberto or self.sob == "limite":
            estado = "foco"
        else:
            estado = "normal"
        self.c.itemconfigure(self.limite_botao, image=self.foto(f"limite_{estado}"))

    def _ao_focar_campo(self, _):
        if self.menu_aberto:
            self._fechar_menu()
        self.c.itemconfigure(self.campo_foco, state="normal")

    def _montar_progresso(self):
        def valor(coluna):
            return self.c.create_text(T.COLUNAS_X[coluna], T.VALOR_Y, anchor="w", font=FONTE_VALOR, fill=T.PRATA)
        self.valor_renovacoes = valor(0)
        self.valor_gemas = valor(1)
        self.valor_ouro = valor(2)

        self.celulas = {}
        for x, item in zip(T.COLUNAS_X, bot.ITENS):
            texto_x = x + 46
            self.celulas[item] = {
                "icone": self.c.create_image(x + 19, T.CELULA_Y),
                "contagem": self.c.create_text(texto_x, T.CELULA_Y - 13, anchor="w", font=FONTE_CONTAGEM),
                "nome": self.c.create_text(texto_x, T.CELULA_Y + 5, anchor="w", font=FONTE_CELULA),
                "compras": self.c.create_text(texto_x, T.CELULA_Y + 19, anchor="w", font=FONTE_CELULA),
            }

        x1, y1, x2, y2 = T.BARRA_RET
        self.barra_largura, self.barra_altura = x2 - x1, y2 - y1
        self.barra_foto = tk.PhotoImage(width=self.barra_largura, height=self.barra_altura)
        self.c.create_image(x1, y1, anchor="nw", image=self.barra_foto)
        self.chama = self.c.create_image(x1, (y1 + y2) // 2 + 12, anchor="s", image=self.foto("chama_0"), state="hidden")

        self.status = self.c.create_text(T.COLUNAS_X[0], T.STATUS_Y, anchor="w", font=FONTE_STATUS)
        self.tempo = self.c.create_text(T.BARRA_RET[2], T.STATUS_Y, anchor="e", justify="right", font=FONTE_DETALHE, fill=T.CINZA, state="hidden")

    def _posicao_inicial(self):
        x = (self.winfo_screenwidth() - T.LARGURA) // 2
        y = max((self.winfo_screenheight() - T.ALTURA) // 2 - 30, 0)
        self.geometry(f"+{x}+{y}")
        self.posicionar()

    def posicionar(self):
        jogo, area = retangulos_do_jogo()
        ponto = posicao_ao_lado(jogo, area, (T.LARGURA + 16, T.ALTURA + 39)) if jogo else None
        if ponto:
            self.geometry(f"+{ponto[0]}+{ponto[1]}")

    def _afastar_do_jogo(self):
        """O jogo vai para a frente ao começar; se estiver cobrindo a interface, tenta tirá-la de baixo."""
        jogo, _ = retangulos_do_jogo()
        if not jogo:
            return
        x1, y1 = self.winfo_rootx(), self.winfo_rooty()
        x2, y2 = x1 + T.LARGURA, y1 + T.ALTURA
        if x1 < jogo[2] and jogo[0] < x2 and y1 < jogo[3] and jogo[1] < y2:
            self.posicionar()

    # ---------- configuração ----------

    def _ler_config(self):
        try:
            config = json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
            return config if isinstance(config, dict) else {}
        except (OSError, ValueError):
            return {}

    def _limites_salvos(self, config):
        salvos = config.get("limites")
        if not isinstance(salvos, dict):
            # versões anteriores só tinham o limite de Pedras Celestes
            salvos = {"pedras": config["limite"]} if "limite" in config else {}
        limites = {}
        for chave, padrao in LIMITES_PADRAO.items():
            valor = str(salvos.get(chave, padrao))
            limites[chave] = valor if limite_valido(valor) else padrao
        return limites

    def _salvar_config(self):
        config = {
            "itens": [item.chave for item in bot.ITENS if self.marcados[item]],
            "limite_tipo": self.limite_tipo,
            "limites": {chave: variavel.get() for chave, variavel in self.limites_txt.items()},
            "idioma": idiomas.atual(),
        }
        try:
            ARQUIVO_CONFIG.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ---------- idioma ----------

    def _trocar_idioma(self, idioma):
        if idioma != idiomas.atual():
            for janela in list(self.janelinhas.values()):  # os textos delas ficariam no idioma antigo
                janela.fechar()
            idiomas.definir(idioma)
            self._aplicar_idioma()
            self._salvar_config()

    def _aplicar_idioma(self):
        self.title(t("titulo"))
        self.c.itemconfigure(self.fundo, image=self.foto(f"fundo_{idiomas.atual()}"))
        self.c.itemconfigure(self.seletor, image=self.foto(f"idioma_{idiomas.atual()}"))
        medida = tkfont.Font(font=FONTE_PRECO)
        for item, linha in self.linhas.items():
            preco = formatar(item.preco)
            self.c.itemconfigure(linha["nome"], text=item.nome)
            self.c.itemconfigure(linha["detalhe"], text=t("por_compra", n=item.quantidade, unidade=t(f"unid_{item.chave}")))
            self.c.itemconfigure(linha["preco"], text=preco)
            self.c.coords(linha["moeda"], T.PRECO_X - medida.measure(preco) - 15, linha["meio"])
            self.c.itemconfigure(self.celulas[item]["nome"], text=t(f"curto_{item.chave}"))
        for chave, texto in self.menu_textos.items():
            self.c.itemconfigure(texto, text=t(f"limite_{chave}"))
        self._mostrar_limite_escolhido()
        self._atualizar_legenda()
        self._mostrar_contadores()
        self._repintar()
        if self.rodando:
            self._mostrar_status_rodando()

    # ---------- opções ----------

    def _ler_limites(self):
        """Só a opção escolhida no menu vale."""
        texto = self.limites_txt[self.limite_tipo].get()
        valor = int(texto) if texto else None
        if self.limite_tipo == "pedras":
            return bot.Limites(pedras=valor)
        if self.limite_tipo == "ouro":
            return bot.Limites(ouro=valor or None)
        return bot.Limites(unidades={ITEM_DO_CAMPO[self.limite_tipo]: valor} if valor else {})

    def _problema_para_iniciar(self):
        """Explica o que impede de começar, ou devolve None."""
        limites = self._ler_limites()
        marcados = [item for item in bot.ITENS if self.marcados[item]]
        if not marcados:
            return t("marque_item")
        if limites.pedras is None and limites.ouro is None and not limites.unidades:
            return t("digite_limite")
        for item in limites.unidades:
            if not self.marcados[item]:
                return t("marque_para_limite", item=item.nome)
        menor_preco = min(item.preco for item in marcados)
        if limites.ouro is not None and limites.ouro < menor_preco:
            return t("ouro_pouco", preco=formatar(menor_preco))
        return None

    def _pode_iniciar(self):
        return self._problema_para_iniciar() is None

    def _atualizar_legenda(self):
        limites = self._ler_limites()
        cor = T.OURO_CLARO
        if limites.pedras is not None:
            cor = T.CINZA
            if limites.renovacoes == 0:
                texto = t("legenda_zero")
            else:
                por_renovacao = SEGUNDOS_COM_AMIZADE if self.marcados[bot.ITENS[2]] else SEGUNDOS_POR_RENOVACAO
                texto = t("legenda", renovacoes=renovacoes_por_extenso(limites.renovacoes), tempo=estimativa(limites.renovacoes * por_renovacao))
        elif limites.ouro is not None:
            texto = t("legenda_ouro", ouro=formatar(limites.ouro)) + "\n" + t("legenda_sem_pedras")
        elif limites.unidades:
            item, n = next(iter(limites.unidades.items()))
            compras = compras_por_extenso(math.ceil(n / item.quantidade))
            texto = t("legenda_item", unidades=formatar(n), unidade=t(f"unid_{item.chave}"), compras=compras) + "\n" + t("legenda_sem_pedras")
        else:
            texto = t("legenda_vazia")
        self.c.itemconfigure(self.legenda, text=texto, fill=cor)

    def _ao_mudar_opcoes(self):
        self.mensagem_final = None
        self._atualizar_legenda()
        self._repintar()

    def _alternar(self, item):
        self.marcados[item] = not self.marcados[item]
        self._ao_mudar_opcoes()

    # ---------- desenho dos estados ----------

    def _repintar(self):
        self._repintar_itens()
        self._repintar_botao()
        self._repintar_celulas()
        self._repintar_atalhos()
        if not self.rodando:
            self._mostrar_status_parado()

    def _repintar_atalhos(self):
        self.c.itemconfigure(self.ajuda, image=self.foto("ajuda_foco" if self.sob == "ajuda" else "ajuda_normal"))
        self.c.itemconfigure(self.mais, image=self.foto("mais_foco" if self.sob == "mais" else "mais_normal"))

    def _repintar_itens(self):
        for item, linha in self.linhas.items():
            marcado = self.marcados[item]
            foco = self.sob == item and not self.rodando
            if self.rodando:
                caixa = "caixa_travada" if marcado else "caixa_travada_vazia"
            else:
                caixa = ("caixa_marcada" if marcado else "caixa_vazia") + ("_foco" if foco else "")
            self.c.itemconfigure(linha["caixa"], image=self.foto(caixa))
            self.c.itemconfigure(linha["icone"], image=self.foto(f"item_{item.chave}" + ("" if marcado else "_apagado")))
            self.c.itemconfigure(linha["realce"], state="normal" if foco else "hidden")
            self.c.itemconfigure(linha["nome"], fill=T.PRATA if marcado else T.CINZA)
            self.c.itemconfigure(linha["detalhe"], fill=T.CINZA if marcado else T.CINZA_ESCURO)
            self.c.itemconfigure(linha["preco"], fill=T.OURO_CLARO if marcado else T.CINZA_ESCURO)
        self.entrada.configure(state="disabled" if self.rodando else "normal")
        self._repintar_seletor()

    def _repintar_botao(self):
        if self.rodando:
            base = "parar"
            ativo = True
        else:
            base = "iniciar"
            ativo = self._pode_iniciar()
        if not ativo:
            estado = "inativo"
        elif self.pressionado == "botao" and self.sob == "botao":
            estado = "pressionado"
        elif self.sob == "botao":
            estado = "foco"
        else:
            estado = "normal"
        self.c.itemconfigure(self.botao, image=self.foto(f"{base}_{estado}_{idiomas.atual()}"))

    def _repintar_celulas(self):
        for item, celula in self.celulas.items():
            ligado = self.marcados[item]
            self.c.itemconfigure(celula["icone"], image=self.foto(f"mini_{item.chave}" + ("" if ligado else "_apagado")))
            if celula["contagem"] not in self.realces:
                self.c.itemconfigure(celula["contagem"], fill=T.PRATA if ligado else T.CINZA_ESCURO)
            self.c.itemconfigure(celula["nome"], fill=T.CINZA if ligado else T.CINZA_ESCURO)
            self.c.itemconfigure(celula["compras"], fill=T.CINZA if ligado else T.CINZA_ESCURO)

    def _escrever_status(self, texto, cor=T.CINZA, largura=None):
        largura = largura or T.BARRA_RET[2] - T.COLUNAS_X[0]
        self.c.itemconfigure(self.status, text=texto, fill=cor, width=largura)

    def _mostrar_status_parado(self):
        problema = self._problema_para_iniciar()
        if self.mensagem_final:
            texto, cor = self.mensagem_final
            self._escrever_status(texto(), cor)
        elif problema:
            self._escrever_status(problema, T.OURO_CLARO)
        else:
            self._escrever_status(t("dica"))

    # ---------- mouse ----------

    def _alvo(self, x, y):
        if self.menu_aberto:
            return self._opcao_em(x, y) or "fora_do_menu"
        x1, y1, x2, y2 = T.SELETOR_LIMITE
        if x1 <= x <= x2 and y1 <= y <= y2:
            return "limite"
        x1, y1, x2, y2 = T.IDIOMA_RET
        if x1 <= x <= x2 and y1 <= y <= y2:
            return idiomas.IDIOMAS[0] if x < (x1 + x2) / 2 else idiomas.IDIOMAS[1]
        for nome, (x1, y1, x2, y2) in (("ajuda", T.AJUDA_RET), ("mais", T.MAIS_RET)):
            if x1 <= x <= x2 and y1 <= y <= y2:
                return nome
        x1, y1, x2, y2 = T.BOTAO_RET
        if x1 <= x <= x2 and y1 <= y <= y2:
            return "botao"
        for numero, item in enumerate(bot.ITENS):
            topo = T.PRIMEIRA_LINHA_Y + numero * T.ALTURA_LINHA
            if T.PAINEL_X1 + 8 <= x <= T.PAINEL_X2 - 8 and topo <= y < topo + T.ALTURA_LINHA:
                return item
        return None

    def _clicavel(self, alvo):
        if alvo in idiomas.IDIOMAS or alvo in OPCOES_LIMITE or alvo in ("ajuda", "mais"):
            return True
        if alvo == "limite":
            return not self.rodando
        if alvo == "fora_do_menu":
            return False
        if alvo == "botao":
            return self.rodando or self._pode_iniciar()
        return alvo is not None and not self.rodando

    def _ao_mover(self, evento):
        alvo = self._alvo(evento.x, evento.y)
        if alvo != self.sob:
            self.sob = alvo
            self.c.configure(cursor="hand2" if self._clicavel(alvo) else "")
            if self.menu_aberto:
                self._realcar_opcao(alvo if alvo in OPCOES_LIMITE else None)
            self._repintar_itens()
            self._repintar_botao()
            self._repintar_atalhos()

    def _ao_sair(self, _):
        self.sob = None
        self.c.configure(cursor="")
        if self.menu_aberto:
            self._realcar_opcao(None)
        self._repintar_itens()
        self._repintar_botao()
        self._repintar_atalhos()

    def _ao_pressionar(self, evento):
        self.c.focus_set()
        self.pressionado = self._alvo(evento.x, evento.y)
        self._repintar_botao()

    def _ao_soltar(self, evento):
        alvo = self._alvo(evento.x, evento.y)
        apertado, self.pressionado = self.pressionado, None
        if self.menu_aberto:  # com o menu aberto, um clique fora só fecha o menu
            if alvo in OPCOES_LIMITE and alvo == apertado:
                self._escolher_limite(alvo)
            else:
                self._fechar_menu()
            return
        if alvo is not None and alvo == apertado and self._clicavel(alvo):
            if alvo == "limite":
                self._abrir_menu()
            elif alvo in idiomas.IDIOMAS:
                self._trocar_idioma(alvo)
            elif alvo == "ajuda":
                self.abrir_apoio()
            elif alvo == "mais":
                self.abrir_historico()
            elif alvo != "botao":
                self._alternar(alvo)
            elif self.rodando:
                self.pedido_parada.set()
            else:
                self._iniciar()
        self._repintar_botao()

    # ---------- execução ----------

    def _iniciar(self):
        self._fechar_menu()
        if bot.jogo_precisa_admin():
            self.abrir_admin()
            return
        itens = tuple(item for item in bot.ITENS if self.marcados[item])
        self.limites_atuais = self._ler_limites()
        self._salvar_config()
        self.pedido_parada = threading.Event()
        self.bot_atual = self.janela_atual = self.resultado = None
        self.totais_base = self.totais_gravados = totais.carregar()
        self.ultima_gravacao = time.monotonic()
        self.inicio = time.monotonic()
        self.fim_do_aviso = 0.0
        self.vistos = {}
        self.rodando = True
        self.mensagem_final = None
        self._afastar_do_jogo()
        self._mostrar_contadores()
        self.c.itemconfigure(self.chama, state="normal")
        self.c.itemconfigure(self.tempo, state="normal", text="")
        self._repintar()
        self.trabalho = threading.Thread(target=self._trabalhar, args=(itens, self.limites_atuais), daemon=True)
        self.trabalho.start()
        self._acompanhar()

    def _trabalhar(self, itens, limites):
        try:
            self.janela_atual = self.criar_janela(self.pedido_parada)
            self.bot_atual = bot.Bot(self.janela_atual, self.modelos, self.telas, itens)
            self.resultado = bot.executar(self.janela_atual, self.bot_atual, limites)
        except bot.Parada as erro:
            bot.log(t("log_parei", motivo=erro))
            self.resultado = erro
        except Exception:
            bot.log(traceback.format_exc())
            self.resultado = bot.Parada("erro_inesperado")

    def _pintar_barra(self, fracao):
        largura = round(self.barra_largura * fracao)
        if largura == self.barra_pintada:
            return
        self.barra_pintada = largura
        self.barra_foto.blank()
        if largura > 0:
            self.barra_foto.tk.call(self.barra_foto.name, "copy", self.foto("barra_cheia").name, "-from", 0, 0, largura, self.barra_altura)
        self.c.coords(self.chama, T.BARRA_RET[0] + largura, (T.BARRA_RET[1] + T.BARRA_RET[3]) // 2 + 12)

    def _realcar(self, item_canvas, cor_normal=T.PRATA):
        if item_canvas in self.realces:
            self.after_cancel(self.realces[item_canvas])
        self.c.itemconfigure(item_canvas, fill=T.OURO_CLARO)

        def apagar():
            del self.realces[item_canvas]
            self.c.itemconfigure(item_canvas, fill=cor_normal)
        self.realces[item_canvas] = self.after(1600, apagar)

    def _subiu(self, chave, valor):
        """Diz se o número cresceu desde a última vez, para só então destacar."""
        antes = self.vistos.get(chave, 0)
        self.vistos[chave] = valor
        return valor > antes

    def _fracao_do_progresso(self, feitas, ouro, atual):
        """A barra acompanha o limite que está mais perto de ser atingido."""
        limites = self.limites_atuais
        fracoes = [0.0]
        if limites.renovacoes:
            fracoes.append(feitas / limites.renovacoes)
        if limites.ouro:
            fracoes.append(ouro / limites.ouro)
        if atual is not None:
            for item, unidades in limites.unidades.items():
                fracoes.append(atual.compras[item] * item.quantidade / unidades)
        return min(max(fracoes), 1.0)

    def _mostrar_contadores(self):
        atual = self.bot_atual
        feitas = atual.renovacoes if atual else 0
        ouro = atual.ouro_gasto() if atual else 0
        total = self.limites_atuais.renovacoes
        renovacoes = formatar(feitas) if total is None else f"{formatar(feitas)} / {formatar(total)}"
        self.c.itemconfigure(self.valor_renovacoes, text=renovacoes)
        self.c.itemconfigure(self.valor_gemas, text=formatar(feitas * bot.CUSTO_RENOVACAO))
        self.c.itemconfigure(self.valor_ouro, text=formatar(ouro))
        if self._subiu("ouro", ouro):
            self._realcar(self.valor_ouro)
        for item, celula in self.celulas.items():
            compras = atual.compras[item] if atual else 0
            self.c.itemconfigure(celula["contagem"], text=formatar(compras * item.quantidade))
            self.c.itemconfigure(celula["compras"], text=compras_por_extenso(compras))
            if self._subiu(item, compras):
                self.fim_do_aviso = time.monotonic() + 4
                self.item_do_aviso = item
                self._realcar(celula["contagem"])
        self._pintar_barra(self._fracao_do_progresso(feitas, ouro, atual))

    def _mostrar_status_rodando(self):
        agora = time.monotonic()
        janela, atual = self.janela_atual, self.bot_atual
        feitas = atual.renovacoes if atual else 0
        total = self.limites_atuais.renovacoes
        passou = agora - self.inicio
        tempo = f"{int(passou // 60):02d}:{int(passou % 60):02d}"
        if feitas and total:
            tempo += "\n" + t("faltam", tempo=duracao(passou / feitas * (total - feitas)))
        self.c.itemconfigure(self.tempo, text=tempo)

        largura = T.BARRA_RET[2] - T.COLUNAS_X[0] - 112
        if self.pedido_parada.is_set():
            self._escrever_status(t("parando"), T.OURO_CLARO, largura)
        elif janela is not None and janela.pausado:
            self._escrever_status(t(janela.pausado), T.OURO_CLARO, largura)
        elif agora < self.fim_do_aviso:
            self._escrever_status(t("comprei_item", item=self.item_do_aviso.nome), T.OURO_CLARO, largura)
        elif atual is None or (feitas == 0 and passou < 4):
            self._escrever_status(t("comecando"), T.PRATA, largura)
        elif total == 0:
            self._escrever_status(t("olhando"), T.PRATA, largura)
        elif total is None:
            self._escrever_status(t("rodando_livre", n=formatar(feitas + 1)), T.PRATA, largura)
        else:
            numero = feitas + 1 if feitas < total else feitas
            self._escrever_status(t("rodando", n=formatar(numero), total=formatar(total)), T.PRATA, largura)

    def _animar_chama(self):
        self.quadro_chama = (self.quadro_chama + 1) % 4
        self.c.itemconfigure(self.chama, image=self.foto(f"chama_{self.quadro_chama}"))

    def _acompanhar(self):
        if self.janela_atual is not None and self.janela_atual.ajustou:
            self.janela_atual.ajustou = False
            self._afastar_do_jogo()  # a janela do jogo mudou de tamanho e pode ter coberto a interface
        self._mostrar_contadores()
        self._mostrar_status_rodando()
        self._animar_chama()
        if time.monotonic() - self.ultima_gravacao >= SEGUNDOS_ENTRE_GRAVACOES:
            self._gravar_totais()
        if self.trabalho.is_alive():
            self.after(120, self._acompanhar)
        else:
            self._terminou()

    def _terminou(self):
        self._mostrar_contadores()
        self._gravar_totais()
        self.totais_base = None
        self.rodando = False
        self.c.itemconfigure(self.chama, state="hidden")
        self.c.itemconfigure(self.tempo, state="hidden")
        segundos = time.monotonic() - self.inicio
        resultado, atual = self.resultado, self.bot_atual
        fim = atual.fim if atual else None
        # os textos são funções para acompanhar uma troca de idioma depois do fim
        if resultado is None and fim == "ouro":
            self.mensagem_final = (lambda: t("fim_ouro", tempo=duracao(segundos)), T.PRATA)
        elif resultado is None and isinstance(fim, bot.Item):
            self.mensagem_final = (lambda: t("fim_item", item=fim.nome, tempo=duracao(segundos)), T.PRATA)
        elif resultado is None and atual.renovacoes == 0:
            self.mensagem_final = (lambda: t("fim_sem_renovar"), T.PRATA)
        elif resultado is None:
            self.mensagem_final = (lambda: t("fim", renovacoes=renovacoes_por_extenso(atual.renovacoes), tempo=duracao(segundos)), T.PRATA)
        elif isinstance(resultado, bot.ParadaPedida):
            self.mensagem_final = (lambda: t("fim_pedido", motivo=resultado, tempo=duracao(segundos)), T.PRATA)
        elif atual is not None and resultado.chave != "erro_inesperado":
            self.mensagem_final = (lambda: t("fim_erro", motivo=resultado), T.SANGUE_CLARO)
        else:
            self.mensagem_final = (lambda: str(resultado), T.SANGUE_CLARO)
        if self.fechando:
            return
        self._repintar()
        self.deiconify()
        self.lift()
        terminou_bem = resultado is None or isinstance(resultado, bot.ParadaPedida)
        if atual is not None and terminou_bem and atual.renovacoes * bot.CUSTO_RENOVACAO >= PEDRAS_PARA_AGRADECER:
            compras = {item: atual.compras[item] for item in bot.ITENS}
            marcados = dict(self.marcados)
            self.after(300, lambda: self.abrir_fim(segundos, atual.renovacoes, compras, marcados))

    # ---------- histórico total ----------

    def _sessao_atual(self):
        """O que a sessão em andamento soma ao histórico. Uma sessão que não renovou nem comprou não conta."""
        sessao = totais.vazio()
        atual = self.bot_atual
        if atual is None:
            return sessao
        compras = {item: atual.compras[item] for item in bot.ITENS}
        if not atual.renovacoes and not any(compras.values()):
            return sessao
        sessao.update(desde=date.today().isoformat(), sessoes=1, segundos=round(time.monotonic() - self.inicio),
                      renovacoes=atual.renovacoes, pedras=atual.renovacoes * bot.CUSTO_RENOVACAO,
                      ouro=sum(item.preco * n for item, n in compras.items()))
        for item, n in compras.items():
            sessao["itens"][item.chave] = {"compras": n, "unidades": n * item.quantidade}
        return sessao

    def _totais_agora(self):
        if self.totais_base is None:
            return totais.carregar()
        return totais.somar(self.totais_base, self._sessao_atual())

    def _gravar_totais(self):
        self.ultima_gravacao = time.monotonic()
        if self.totais_base is None:
            return
        dados = self._totais_agora()
        if dados != self.totais_gravados and totais.salvar(dados):
            self.totais_gravados = dados

    # ---------- janelinhas ----------

    def _trazer_janelinha(self, chave):
        janela = self.janelinhas.get(chave)
        if janela is None or not janela.winfo_exists():
            return False
        janela.deiconify()
        janela.lift()
        janela.focus_force()
        return True

    def _nova_janelinha(self, chave, titulo, **opcoes):
        antiga = self.janelinhas.get(chave)
        if antiga is not None and antiga.winfo_exists():
            antiga.fechar()
        janela = self.janelinhas[chave] = Janelinha(self, chave, titulo, **opcoes)
        return janela

    def _preencher_colunas(self, janela, renovacoes, ouro, compras, unidades, apagados=()):
        """As mesmas colunas do progresso: renovações, Pedras e ouro, e embaixo o que foi comprado."""
        m = janela.medidas
        for x, valor in zip(T.COLUNAS_JANELINHA, (renovacoes, renovacoes * bot.CUSTO_RENOVACAO, ouro)):
            janela.texto(x, m["valor_y"], formatar(valor), fonte=FONTE_VALOR, ancora="w")
        for x, item in zip(T.COLUNAS_JANELINHA, bot.ITENS):
            apagado = item in apagados
            janela.c.create_image(x + 19, m["celula_y"], image=self.foto(f"mini_{item.chave}" + ("_apagado" if apagado else "")))
            cor, cor_detalhe = (T.CINZA_ESCURO, T.CINZA_ESCURO) if apagado else (T.PRATA, T.CINZA)
            janela.texto(x + 46, m["celula_y"] - 13, formatar(unidades[item]), cor, FONTE_CONTAGEM, ancora="w")
            janela.texto(x + 46, m["celula_y"] + 5, t(f"curto_{item.chave}"), cor_detalhe, FONTE_CELULA, ancora="w")
            janela.texto(x + 46, m["celula_y"] + 19, compras_por_extenso(compras[item]), cor_detalhe, FONTE_CELULA, ancora="w")

    def abrir_apoio(self):
        if self._trazer_janelinha("apoio"):
            return
        janela = self._nova_janelinha("apoio", t("janela_apoio"))
        m = janela.medidas
        meio = T.JANELINHA_LARGURA // 2
        janela.paragrafo(m["texto_y"], t("apoio_texto"))
        janela.botao(meio - T.BOTAO_GRANDE[0] // 2, m["botao_y"], "roxo", "grande", t("bt_kofi"), lambda: abrir_link(bot.KOFI))
        if "qr_y" in m:  # o Pix só aparece em português
            janela.texto(meio, m["chave_y"], bot.CHAVE_PIX, fonte=FONTE_CHAVE, ancora="center")
            rotulo = janela.botao(meio - T.BOTAO_PEQUENO[0] // 2, m["copiar_y"], "prata", "pequeno", t("bt_copiar"),
                                  lambda: self._copiar_pix(janela, rotulo))
        janela.link(m["rodape_y"], t("rodape", versao=bot.VERSAO, projeto=bot.PROJETO), lambda: abrir_link(f"https://{bot.PROJETO}"))
        janela.mostrar()

    def _copiar_pix(self, janela, rotulo):
        self.clipboard_clear()
        self.clipboard_append(bot.CHAVE_PIX)
        janela.c.itemconfigure(rotulo, text=t("copiada"))
        janela.after(1800, lambda: janela.winfo_exists() and janela.c.itemconfigure(rotulo, text=t("bt_copiar")))

    def abrir_historico(self):
        if self._trazer_janelinha("historico"):
            return
        janela = self._nova_janelinha("historico", t("janela_historico"))
        m = janela.medidas
        janela.paragrafo(m["nota_y"], t("historico_nota"), T.CINZA, FONTE_DETALHE)
        janela.botao((T.JANELINHA_LARGURA - T.BOTAO_PEQUENO[0]) // 2, m["botao_y"], "prata", "pequeno", t("bt_fechar"), janela.fechar)
        dinamicos = []

        def preencher():
            if not janela.winfo_exists():
                return
            for item in dinamicos:
                janela.c.delete(item)
            antes = set(janela.c.find_all())
            dados = self._totais_agora()
            if dados["sessoes"]:
                try:
                    data = date.fromisoformat(dados["desde"]).strftime(t("formato_data"))
                except (TypeError, ValueError):
                    data = str(dados["desde"])
                n = dados["sessoes"]
                sessoes = t("uma_sessao" if n == 1 else "n_sessoes", n=formatar(n))
                resumo = t("historico_resumo", data=data, sessoes=sessoes, tempo=duracao(dados["segundos"]))
            else:
                resumo = t("historico_vazio")
            janela.paragrafo(m["texto_y"], resumo, T.CINZA)
            compras = {item: dados["itens"][item.chave]["compras"] for item in bot.ITENS}
            unidades = {item: dados["itens"][item.chave]["unidades"] for item in bot.ITENS}
            self._preencher_colunas(janela, dados["renovacoes"], dados["ouro"], compras, unidades,
                                    apagados=[item for item in bot.ITENS if not compras[item]])
            dinamicos[:] = [item for item in janela.c.find_all() if item not in antes]
            if self.rodando:
                janela.after(1000, preencher)
        preencher()
        janela.mostrar()

    def abrir_fim(self, segundos, renovacoes, compras, marcados):
        """O fim de uma sessão longa: o que o bot conseguiu, em destaque, e o convite para apoiar."""
        janela = self._nova_janelinha("fim", t("janela_fim"), no_topo=True)
        m = janela.medidas
        meio = T.JANELINHA_LARGURA // 2
        janela.texto(meio, m["subtitulo_y"], t("parabens_sub", tempo=duracao(segundos)), ancora="center")
        mostrar = [item for item in bot.ITENS if marcados[item] or compras[item]]
        passo = 124 if len(mostrar) == 3 else 150
        topo = m["itens_y"]
        for numero, item in enumerate(mostrar):
            x = meio + (numero - (len(mostrar) - 1) / 2) * passo
            comprou = compras[item] > 0
            janela.c.create_image(x, topo + 27, image=self.foto(f"item_{item.chave}" + ("" if comprou else "_apagado")))
            janela.texto(x, topo + 76, formatar(compras[item] * item.quantidade), T.OURO_CLARO if comprou else T.CINZA_ESCURO,
                         FONTE_DESTAQUE, ancora="center")
            janela.texto(x, topo + 100, t(f"curto_{item.chave}"), T.PRATA if comprou else T.CINZA_ESCURO, FONTE_DETALHE, ancora="center")
            janela.texto(x, topo + 116, compras_por_extenso(compras[item]), T.CINZA if comprou else T.CINZA_ESCURO, FONTE_CELULA,
                         ancora="center")
        ouro = sum(item.preco * n for item, n in compras.items())
        gastos = t("parabens_gastos", renovacoes=renovacoes_por_extenso(renovacoes), pedras=formatar(renovacoes * bot.CUSTO_RENOVACAO),
                   ouro=formatar(ouro))
        janela.texto(meio, m["gastos_y"], gastos, T.CINZA, FONTE_DETALHE, ancora="center")
        x1, y1, x2, y2 = m["caixa"]
        janela.texto(meio, (y1 + y2) // 2 + 5, t("agradecer"), T.OURO_CLARO, FONTE_AGRADECER, ancora="center", largura=x2 - x1 - 40,
                     alinhar="center")
        x = (T.JANELINHA_LARGURA - 2 * T.BOTAO_PEQUENO[0] - 10) // 2

        def apoiar():
            janela.fechar()
            self.abrir_apoio()
        janela.botao(x, m["botao_y"], "roxo", "pequeno", t("bt_apoiar"), apoiar)
        janela.botao(x + T.BOTAO_PEQUENO[0] + 10, m["botao_y"], "prata", "pequeno", t("bt_fechar"), janela.fechar)
        janela.mostrar()

    def abrir_admin(self):
        if self._trazer_janelinha("admin"):
            return
        janela = self._nova_janelinha("admin", t("janela_admin"), modal=True)
        m = janela.medidas
        janela.paragrafo(m["texto_y"], t("admin_texto"))
        x = (T.JANELINHA_LARGURA - T.BOTAO_GRANDE[0] - T.BOTAO_PEQUENO[0] - 10) // 2
        janela.botao(x, m["botao_y"], "roxo", "grande", t("bt_reabrir"), lambda: self._reabrir_como_admin(janela))
        janela.botao(x + T.BOTAO_GRANDE[0] + 10, m["botao_y"], "prata", "pequeno", t("bt_cancelar"), janela.fechar)
        janela.mostrar()

    def _reabrir_como_admin(self, janela):
        self._salvar_config()  # a cópia nova abre com as mesmas escolhas
        if reabrir_como_admin():
            self.fechando = True
            self.destroy()  # a cópia nova espera esta fechar
            return
        janela.fechar()
        self.mensagem_final = (lambda: t("admin_recusado"), T.OURO_CLARO)
        self._repintar()

    def _fechar(self):
        self.fechando = True
        self._salvar_config()
        if self.trabalho is not None and self.trabalho.is_alive():
            self.pedido_parada.set()
            self.withdraw()
            self.after(100, self._fechar)
            return
        self.destroy()

    def report_callback_exception(self, tipo, valor, rastro):
        bot.log("".join(traceback.format_exception(tipo, valor, rastro)))


def ja_esta_aberto(esperar=0.0):
    """Duas cópias disputariam o mouse e gastariam em dobro; a segunda só traz a primeira para a frente.

    Reaberta como administrador, a cópia nova espera um pouco a antiga terminar de fechar.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    prazo = time.monotonic() + esperar
    while True:
        trava = kernel32.CreateMutexW(None, False, NOME_TRAVA)  # o Windows solta quando o programa fecha
        # 183: já existe; 5: existe, mas foi criada por uma cópia aberta como administrador
        if ctypes.get_last_error() not in (183, 5):
            return False
        if trava:
            kernel32.CloseHandle(trava)  # segurar esta referência manteria a trava viva depois que a outra cópia fechar
        if time.monotonic() >= prazo:
            break
        time.sleep(0.2)
    for idioma in idiomas.IDIOMAS:
        janela = ctypes.windll.user32.FindWindowW(None, idiomas.TEXTOS[idioma]["titulo"])
        if janela:
            ctypes.windll.user32.ShowWindow(janela, 9)
            ctypes.windll.user32.SetForegroundWindow(janela)
    return True


def main():
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("epicseven.lojasecreta.bot")
    if ja_esta_aberto(esperar=8 if ARG_REABERTO in sys.argv else 0):
        return
    try:
        App().mainloop()
    except Exception as erro:  # sem console, o erro precisa aparecer em uma janela
        bot.log(traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(None, f"{t('abrir_erro')}\n\n{erro}", "Epic Seven", 0x10)


if __name__ == "__main__":
    main()
