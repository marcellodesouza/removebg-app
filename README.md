# Remove Background App

App desktop para **GNU/Linux** que remove o fundo de imagens usando inteligência artificial — tudo processado localmente, sem enviar seus dados para nenhum servidor.

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Platform](https://img.shields.io/badge/platform-GNU%2FLinux-orange) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Download

Baixe o AppImage na página de [Releases](../../releases) — sem instalação, só dar permissão e executar:

```bash
chmod +x RemoveBackground.AppImage
./RemoveBackground.AppImage
```

> Na primeira execução, o modelo padrão (U2Net, ~170 MB) será baixado automaticamente.

---

## O que é o rembg?

[rembg](https://github.com/danielgatis/rembg) é uma biblioteca Python de código aberto que remove o fundo de imagens usando redes neurais. Por baixo, usa o [ONNX Runtime](https://onnxruntime.ai/) para rodar os modelos de IA de forma eficiente na CPU, sem precisar de GPU.

Este app é uma interface gráfica para o rembg, com suporte a múltiplos modelos, download sob demanda e funcionamento 100% offline após o primeiro uso.

---

## Modelos de IA disponíveis

Cada modelo foi treinado com um propósito diferente. Todos são baixados sob demanda e ficam salvos em `~/.local/share/removebg/models/` para uso offline.

| Modelo | Tamanho | Melhor para |
|--------|---------|-------------|
| **U2Net** *(padrão)* | ~170 MB | Uso geral: produtos, objetos, animais, pessoas |
| **U2Net Humano** | ~170 MB | Retratos e fotos de pessoas — bordas mais limpas |
| **IS-Net (alta qualidade)** | ~170 MB | Cabelos finos, pelos, detalhes complexos — mais lento |
| **IS-Net Anime** | ~170 MB | Ilustrações, manga e arte digital — não funciona em fotos |
| **BiRefNet** | ~200 MB | Melhor qualidade disponível — uso profissional, mais lento |

**Como escolher:** para a maioria dos casos o U2Net já é suficiente. Use o IS-Net ou BiRefNet quando a qualidade do recorte for crítica (ex: cabelos soltos, bordas complexas).

---

## Funcionalidades

- Interface dark mode com zoom e pan nas imagens
- Seleção de modelo com download automático e confirmação
- **Recorte automático** — após remover o fundo, a imagem é cortada rente ao objeto automaticamente
- **Recorte manual** — desenhe um retângulo diretamente sobre o resultado para definir a área de corte
- Salvar resultado como PNG com transparência
- Copiar resultado para a área de transferência (para colar direto no GIMP, Canva, Photoshop etc.)
- Funciona 100% offline após o download dos modelos
- Log de debug em `~/removebg-debug.log`

---

## Como usar

1. Clique em **Abrir Imagem** e selecione o arquivo (JPG, PNG, WEBP, BMP ou TIFF)
2. Clique em **Remover Fundo** — o processamento acontece localmente
3. O resultado aparece no painel direito já com **recorte automático** aplicado
4. Se quiser ajustar o recorte, use a barra que aparece abaixo dos painéis:
   - **Auto** — recorta rente ao objeto detectado
   - **Desenhar área** — clique e arraste para definir manualmente a região
   - **Resetar** — volta para a imagem completa sem recorte
5. Use **Salvar PNG** para salvar no computador ou **Copiar** para colar direto no seu editor

---

## Rodar sem compilar (modo desenvolvimento)

### Pré-requisitos

- Python 3.8 ou superior
- `pip`
- `xclip` (para o botão Copiar)

```bash
sudo apt install python3 python3-pip python3-venv xclip
```

### Passos

```bash
# Clone o repositório
git clone https://github.com/SEU_USUARIO/removebg-app.git
cd removebg-app

# Crie e ative um ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale as dependências
pip install customtkinter pillow rembg[cpu] onnxruntime

# Execute
python3 app.py
```

---

## Compilar o AppImage

### Pré-requisitos para build

- GNU/Linux x86_64
- Python 3.8+ com `pip` e `venv`
- `wget` ou `curl`
- `xclip` (runtime, não build)
- Conexão com internet (para baixar dependências e o `appimagetool`)

```bash
sudo apt install python3 python3-pip python3-venv wget
```

### Gerar o AppImage

```bash
git clone https://github.com/SEU_USUARIO/removebg-app.git
cd removebg-app

chmod +x build_appimage.sh
./build_appimage.sh
```

O script irá:
1. Criar um ambiente virtual isolado em `build_tmp/`
2. Instalar todas as dependências Python
3. Empacotar tudo com PyInstaller
4. Baixar o `appimagetool` e gerar o `RemoveBackground.AppImage`

O AppImage final terá entre **130–150 MB**. Os modelos de IA **não são embutidos** no AppImage — são baixados na primeira execução de cada modelo, mantendo o arquivo de distribuição leve.

### Estrutura do projeto

```
removebg-app/
├── app.py               # Código principal (UI + lógica)
├── build_appimage.sh    # Script de build
├── icon.png             # Ícone do app (gerado automaticamente se ausente)
└── README.md
```

---

## Compatibilidade

| Sistema | Suporte |
|---------|---------|
| GNU/Linux x86_64 | ✅ Suportado |
| Windows | ❌ Não suportado |
| macOS | ❌ Não suportado |

---

## Tecnologias utilizadas

- [rembg](https://github.com/danielgatis/rembg) — remoção de fundo com IA
- [ONNX Runtime](https://onnxruntime.ai/) — inferência dos modelos na CPU
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — interface gráfica dark mode
- [Pillow](https://python-pillow.org/) — manipulação de imagens
- [PyInstaller](https://pyinstaller.org/) — empacotamento
- [appimagetool](https://appimage.github.io/) — geração do AppImage
