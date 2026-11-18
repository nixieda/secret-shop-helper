"""Cores e posições da interface, compartilhadas com visual/gerar_visual.py."""

LARGURA, ALTURA = 480, 786

# Paleta inspirada na Salome: preto de catedral, cera vermelha, ouro velho, cabelo prateado.
FUNDO = "#0E0A0B"
CAMPO = "#0C0809"
PRATA = "#ECEAF0"
CINZA = "#A79C96"
CINZA_ESCURO = "#6F645F"
OURO = "#C8A46E"
OURO_CLARO = "#F0CE8E"
OURO_ESCURO = "#7A6244"
SANGUE_CLARO = "#E8506A"

PAINEL_X1, PAINEL_X2 = 20, 460
IDIOMA_RET = (390, 12, 460, 38)
AJUDA_RET = (20, 12, 46, 38)  # o "?" que abre o apoio ao projeto, espelhando o seletor de idioma
MAIS_RET = (414, 557, 446, 579)  # os três pontinhos no título do progresso, que abrem o histórico total
FIM_LINHA_PROGRESSO = 404  # a linha do título do progresso para antes dos três pontinhos

ITENS_Y = (126, 348)
PRIMEIRA_LINHA_Y = 160
ALTURA_LINHA = 60
CHECK_X = 46
ICONE_X = 98
NOME_X = 134
PRECO_X = 444

PARADA_Y = (358, 476)
SELETOR_LIMITE = (36, 392, 256, 428)  # o botão com as opções de limite
CAMPO_LIMITE = (264, 392, 444, 428)
ALTURA_OPCAO = 34
LEGENDA_Y = 452

BOTAO_RET = (20, 486, 460, 538)
BOTAO_ALTURA_IMAGEM = 52

PROGRESSO_Y = (548, 774)
ROTULO_Y = 595
VALOR_Y = 616
COLUNAS_X = (36, 178, 318)
CELULA_Y = 668
BARRA_RET = (36, 711, 444, 719)
STATUS_Y = 747

# Janelinhas que abrem por cima da principal. Todas têm a mesma largura; as posições são dentro de cada uma.
JANELINHA_LARGURA = 440
JANELINHA_X1, JANELINHA_X2 = 30, 410  # onde o texto começa e termina
JANELINHA_TITULO_Y = 38
COLUNAS_JANELINHA = (30, 172, 314)  # o mesmo espaço entre colunas do progresso, para os nomes caberem
BOTAO_GRANDE = (200, 38)
BOTAO_PEQUENO = (140, 38)
LADO_QR = 212  # a caixa branca do QR Code do Pix
JANELINHAS = {
    "apoio_pt": {"altura": 566, "texto_y": 62, "botao_y": 146, "pix_y": 214, "qr_y": 228, "chave_y": 456, "copiar_y": 472, "rodape_y": 538},
    "apoio_en": {"altura": 242, "texto_y": 62, "botao_y": 146, "rodape_y": 214},
    # resultado: um "Parabéns!" discreto, o que foi comprado em destaque e o convite para apoiar numa caixa
    "fim": {"altura": 474, "enfeite_y": 34, "titulo_y": 94, "subtitulo_y": 118, "itens_y": 138, "gastos_y": 274,
            "caixa": (34, 302, 406, 396), "botao_y": 416},
    "historico": {"altura": 344, "texto_y": 62, "rotulo_y": 102, "valor_y": 124, "linhas_y": (152, 222), "celula_y": 187, "nota_y": 238,
                  "botao_y": 284},
    "admin": {"altura": 286, "texto_y": 62, "botao_y": 224},
}
