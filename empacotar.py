"""Gera dist/SecretShop.zip, que roda em outros PCs sem instalar Python.

Precisa do PyInstaller só aqui:  pip install pyinstaller
Usa uma pasta (--onedir) e não comprime com UPX, o que costuma gerar menos alarme falso de antivírus.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOME = "SecretShop"
# a versão vem de bot_loja_secreta.py, lida como texto para não precisar carregar o OpenCV aqui
_versao = re.search(r'^VERSAO = "(\d+)\.(\d+)\.(\d+)"$', (RAIZ / "bot_loja_secreta.py").read_text(encoding="utf-8"), re.M)
VERSAO = tuple(int(n) for n in _versao.groups()) + (0,)
DESCRICAO = "Epic Seven Secret Shop Auto Refresh"

INFO_VERSAO = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={VERSAO}, prodvers={VERSAO}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', '{DESCRICAO}'),
      StringStruct('FileVersion', '{".".join(map(str, VERSAO))}'),
      StringStruct('InternalName', '{NOME}'),
      StringStruct('OriginalFilename', '{NOME}.exe'),
      StringStruct('ProductName', 'Secret Shop Auto Refresh'),
      StringStruct('ProductVersion', '{".".join(map(str, VERSAO))}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


# O programa não usa rede, vídeo nem fusos horários: menos arquivos, menos para o antivírus examinar.
MODULOS_FORA = ("ssl", "_ssl", "_hashlib", "socket", "_socket", "asyncio", "http", "ftplib", "smtplib", "xmlrpc",
                "multiprocessing", "concurrent", "unittest", "doctest", "pydoc", "pdb")
ARQUIVOS_FORA = ("_tcl_data/tzdata", "_tcl_data/msgs", "_tk_data/msgs", "_tk_data/demos", "cv2/opencv_videoio_ffmpeg*.dll")
# o numpy depende desta DLL do Visual C++, que um PC sem o pacote do Visual C++ pode não ter
DLL_VISUAL_C = Path(os.environ["SystemRoot"]) / "System32" / "concrt140.dll"


def remover_sobras(internos):
    for padrao in ARQUIVOS_FORA:
        for caminho in internos.glob(padrao):
            if caminho.is_dir():
                shutil.rmtree(caminho)
            else:
                caminho.unlink()


def main():
    destino = RAIZ / "dist"
    with tempfile.TemporaryDirectory(prefix="secretshop_") as trabalho:
        versao = Path(trabalho) / "versao.txt"
        versao.write_text(INFO_VERSAO, encoding="utf-8")
        comando = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir", "--noupx",
            "--name", NOME, "--icon", str(RAIZ / "visual" / "icone.ico"), "--version-file", str(versao),
            "--add-data", f"{RAIZ / 'modelos'};modelos", "--add-data", f"{RAIZ / 'visual' / '*.png'};visual",
            "--add-binary", f"{DLL_VISUAL_C};.",
            "--distpath", str(destino), "--workpath", trabalho, "--specpath", trabalho,
        ]
        for modulo in MODULOS_FORA:
            comando += ["--exclude-module", modulo]
        subprocess.run([*comando, str(RAIZ / "interface.py")], check=True, cwd=RAIZ)

    pasta = destino / NOME
    remover_sobras(pasta / "_internal")
    shutil.copy(RAIZ / "LEIA-ME.txt", pasta / "README.txt")
    arquivo = destino / f"{NOME}.zip"
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED) as pacote:
        for caminho in sorted(pasta.rglob("*")):
            if caminho.is_file():
                pacote.write(caminho, Path(NOME) / caminho.relative_to(pasta))
    print(f"Pacote: {arquivo} ({arquivo.stat().st_size / 1024 / 1024:.0f} MB)")


if __name__ == "__main__":
    main()
