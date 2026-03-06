import os
import pdfplumber
import re
from github import Github
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Pega o token das configurações do Render (mais seguro)
GITHUB_TOKEN = os.getenv("GIT_TOKEN")
REPO_NAME = "MarcalDevPRF/prf-limite-lc"
FILE_PATH = "dados.csv"

@app.route('/upload_pdf', methods=['POST'])
def upload():
    file = request.files['file']
    file.save("temp.pdf")
    with pdfplumber.open("temp.pdf") as pdf:
        texto = pdf.pages[0].extract_text()
        dados = {}
        try:
            dados['nome'] = re.search(r"Nome Completo:\n\s*(.*)", texto).group(1).strip()
            dados['matricula'] = re.search(r"Matrícula:\n\s*([\d.]+)", texto).group(1).strip()
            dados['processo'] = re.search(r"SEI\s*(\d{5}\.\d{6}/\d{4}-\d{2})", texto).group(1).strip()
            datas = re.findall(r"(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})", texto)
            if datas:
                dados['inicio'] = datas[0][0]
                dados['fim'] = datas[0][1]
        except: pass
    return jsonify(dados)

@app.route('/validar_e_salvar', methods=['POST'])
def validar_e_salvar():
    d = request.json
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    contents = repo.get_contents(FILE_PATH)
    csv_texto = contents.decoded_content.decode('utf-8')
    
    # Lógica de 5% (mesma que usamos antes)
    limite = max(1, int(float(d['efetivo']) * 0.05))
    linhas = csv_texto.strip().split('\n')
    conflitos = 0
    
    for linha in linhas[1:]:
        cols = linha.split(',')
        if cols[3] == d['unidade']:
            ini_b = datetime.strptime(cols[1], '%d/%m/%Y')
            fim_b = datetime.strptime(cols[2], '%d/%m/%Y')
            if datetime.strptime(d['inicio'], '%d/%m/%Y') <= fim_b and datetime.strptime(d['fim'], '%d/%m/%Y') >= ini_b:
                conflitos += 1

    if conflitos >= limite:
        return jsonify({"status": "erro", "mensagem": f"Limite excedido! ({conflitos} pessoas)"}), 400

    # Atualiza o arquivo no GitHub
    novo_conteudo = csv_texto + f"\n{d['processo']},{d['inicio']},{d['fim']},{d['unidade']}"
    repo.update_file(contents.path, "Update LC via App", novo_conteudo, contents.sha)
    
    return jsonify({"status": "sucesso", "mensagem": "Salvo com sucesso no GitHub!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))