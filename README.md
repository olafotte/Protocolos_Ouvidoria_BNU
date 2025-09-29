# Get Protocolos Enhanced

Este projeto é um sistema completo para extração (scraping), armazenamento, visualização e deploy de dados de protocolos do portal de serviços da prefeitura de Blumenau.

## Descrição Geral

O sistema é composto por várias partes que trabalham em conjunto:

1.  **Scraper (`enhanced_protocol_scraper.py`):** Um robô que utiliza Selenium para navegar no portal de serviços, buscar protocolos de forma incremental e salvar o conteúdo em um banco de dados local.
2.  **Banco de Dados:** Um banco de dados SQLite (`protocols.db`) que armazena de forma persistente todos os dados extraídos.
3.  **Aplicações de Visualização:** Duas aplicações web construídas com Flask que permitem visualizar e filtrar os dados dos protocolos.
4.  **Scripts de Deploy:** Ferramentas para facilitar o upload do banco de dados atualizado para um servidor web (PythonAnywhere) e recarregar a aplicação.

## Funcionalidades Principais

- **Scraping Inteligente:** O robô sabe quais protocolos já foram baixados e busca apenas os novos, otimizando o tempo de execução.
- **Busca Binária:** Determina o número do último protocolo do ano corrente de forma eficiente através de uma busca binária.
- **Armazenamento Persistente:** Os dados são salvos em um banco de dados SQLite, permitindo consultas e análises futuras sem a necessidade de raspar os dados novamente.
- **Geração de Resumo:** Ao final da execução, o scraper gera um arquivo `Update.txt` com um resumo dos novos protocolos encontrados que correspondem a uma lista de palavras-chave de interesse.
- **Visualização Web Interativa:**
    - Uma interface web (`app.py`) para consultar, pesquisar e filtrar todos os protocolos no banco de dados.
    - A busca é feita no lado do servidor para maior performance.
    - Permite filtrar por status (arquivado/não arquivado), por palavras-chave específicas e por texto livre.
    - Destaque em amarelo das palavras buscadas.
- **Deploy Simplificado:** Um script (`deploy_db.py`) automatiza o processo de enviar o banco de dados local para o servidor PythonAnywhere e recarregar a aplicação web.
- **Configuração Centralizada:** As principais variáveis do projeto, como URLs, palavras-chave e credenciais (em um arquivo separado), são gerenciadas através de arquivos de configuração (`config.json`, `deploy_config.json`).

## Tecnologias Utilizadas

- **Python 3**
- **Selenium:** Para automação do navegador e scraping.
- **Flask:** Para criar as aplicações web de visualização.
- **SQLite:** Para o armazenamento dos dados.
- **Requests:** Para interagir com a API do PythonAnywhere.
- **TQDM:** Para exibir barras de progresso durante o scraping.

## Estrutura de Arquivos

```
.
├── .gitignore             # Arquivos e pastas a serem ignorados pelo Git.
├── app.py                 # Aplicação web principal (sem filtro padrão).
├── config.json            # Arquivo de configuração principal (URLs, palavras-chave).
├── deploy_config.json     # Arquivo de configuração do deploy (credenciais).
├── deploy_db.py           # Script para upload do BD e reload da aplicação.
├── enhanced_protocol_scraper.py # Script principal que faz o scraping.
├── LICENSE                # Licença do projeto.
├── protocols.db           # Banco de dados SQLite.
├── README.md              # Este arquivo.
├── requirements.txt       # Dependências do projeto Python.
├── Update.txt             # Resumo dos novos protocolos encontrados.
├── visualization.py       # Aplicação web secundária (com filtro padrão).
├── wsgi.py                # Ponto de entrada para o servidor web (PythonAnywhere).
├── static/                # Arquivos estáticos para as aplicações web (CSS, JS).
└── templates/             # Templates HTML para as aplicações web.
```

## Guia de Instalação e Uso

### 1. Instalação

Clone o repositório, crie um ambiente virtual e instale as dependências.

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd Get_Protocolos_enchanced

# Crie e ative um ambiente virtual
python -m venv venv
# No Windows
.\venv\Scripts\activate
# No Linux/macOS
# source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### 2. Configuração

- **`config.json`:** Verifique se as URLs e as listas `lista_original` e `familias` estão de acordo com suas necessidades.
- **`deploy_config.json`:** Se for usar o deploy para o PythonAnywhere, renomeie `deploy_config.json.example` para `deploy_config.json` e preencha com seu `username`, `api_token` e `webapp_domain`.

### 3. Executando o Scraper

Use o `enhanced_protocol_scraper.py` com a ação `scrape` para buscar novos protocolos. Ele irá gerar o `protocols.db` e o `Update.txt`.

```bash
# Execute o scraper
python enhanced_protocol_scraper.py scrape
```

Outras ações disponíveis são `init_db` (para criar o banco de dados) e `analyze` (para verificar falhas na sequência de protocolos).

### 4. Visualizando os Dados

Você pode executar duas aplicações web diferentes:

- **Aplicação Principal (Recomendado):**
  ```bash
  python app.py
  ```
  Acesse `http://127.0.0.1:5000` no seu navegador. Esta versão é mais rápida e completa.

- **Aplicação Secundária:**
  ```bash
  python visualization.py
  ```
  Acesse `http://127.0.0.1:5000`. Esta versão filtra os protocolos por padrão.

### 5. Deploy para PythonAnywhere

Após configurar o `deploy_config.json`, execute o script de deploy para enviar o banco de dados atualizado e recarregar sua aplicação web.

```bash
python deploy_db.py
```

## Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.