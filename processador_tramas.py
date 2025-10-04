import re
import csv
import os
from collections import defaultdict
import requests
from requests.auth import HTTPBasicAuth
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv  # <- carrega variáveis de ambiente de um .env local

# Carrega variáveis do arquivo .env (se existir)
load_dotenv()

# Variáveis de ambiente
usuario = os.getenv("APP_USERNAME")
senha = os.getenv("APP_PASSWORD")
SITE_BASE_URL = os.getenv("APP_SITE_URL", "https://tramasgrao.solinftec.com/Netzero_Farm/SNS_Tramas")

# Parâmetros
pasta_saida = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
caracteres_alvo = {'A', 'B', 'C', 'D', 'E', 'F', '8', '9'}

# Função para imprimir texto em verde
def print_green(text):
    print(f"\033[92m{text}\033[0m")

def solicitar_base():
    while True:
        base = input("Digite o número da base (ex: 299): ").strip()
        if not base.isdigit():
            print("Número da base inválido. A base deve ser um número.\n")
        else:
            return base

def solicitar_data():
    while True:
        try:
            ano = input("Digite o ano (ex: 2025): ").strip()
            mes = input("Digite o mês (ex: 04): ").strip()
            dia = input("Digite o dia (ex: 11): ").strip()
            data_digitada = datetime.strptime(f"{ano}-{mes}-{dia}", "%Y-%m-%d").date()
            hoje = datetime.now().date()
            if hoje - timedelta(days=4) <= data_digitada <= hoje:
                return ano, mes, dia
            else:
                print("A data deve ser entre hoje e até 4 dias atrás (ex: se hoje é dia 15, pode digitar 15, 14, 13, 12, 11).\n")
        except ValueError:
            print("Data inválida. Tente novamente.\n")

def processar_tramas(base_alvo, ano, mes, dia):
    # Garante que credenciais e URL foram configurados
    if not usuario or not senha or not SITE_BASE_URL:
        print("❌ Erro: Defina APP_USERNAME, APP_PASSWORD e APP_SITE_URL no .env ou variáveis de ambiente.")
        return

    # Três formatos possíveis de arquivo
    arquivos_entrada = [
        f"{SITE_BASE_URL}/GPRS_{ano}_{mes}_{dia}_00_00_00.txt",
        f"{SITE_BASE_URL}/GPRS_{ano}_{mes}_{dia}_00_00_01.txt",
        f"{SITE_BASE_URL}/GPRS_{ano}_{mes}_{dia}.txt"
    ]
    
    # Nomes dos arquivos de saída
    arquivo_saida_geral = os.path.join(pasta_saida, f"saida_horario_campo_{ano}_{mes}_{dia}.csv")
    arquivo_saida_filtrado = os.path.join(pasta_saida, f"saida_filtrados_AF89_{ano}_{mes}_{dia}.csv")
    
    saida_geral = []
    saida_filtrada = []
    contagem = defaultdict(int)
    houve_desconexao = False

    try:
        response = None
        for url in arquivos_entrada:
            response = requests.get(url, auth=HTTPBasicAuth(usuario, senha))
            if response.status_code == 200:
                break  # Achou um válido, sai do loop

        if not response or response.status_code != 200:
            print(f"\nErro ao acessar os arquivos: {', '.join(arquivos_entrada)}. Código: {response.status_code}\n")
            return

        linhas = response.text.splitlines()
        encontrou_base = False
        filtro_base = f"122,00,122{base_alvo}"

        for linha in linhas:
            if filtro_base in linha:
                encontrou_base = True
                match_hora = re.search(r"\d{2}:\d{2}:\d{2}", linha)
                partes = linha.split(",")
                if len(partes) > 10:
                    campo = partes[10].strip()
                    if match_hora:
                        horario = match_hora.group(0)
                        data_completa = f"{ano}-{mes}-{dia}"
                        saida_geral.append([data_completa, horario, campo])
                        if len(campo) >= 2:
                            penultimo = campo[-2].upper()
                            if penultimo in caracteres_alvo:
                                contagem[penultimo] += 1
                                saida_filtrada.append([data_completa, horario, campo])
                                houve_desconexao = True  # Marca que houve desconexão

        if not encontrou_base:
            print("\nNúmero de base não encontrado no arquivo.\n")
            return

        if not houve_desconexao:
            print_green("Não houve desconexão (nenhuma linha com A-F ou 8/9 no penúltimo dígito).")
            return

        # Salva arquivo geral
        if saida_geral:
            with open(arquivo_saida_geral, "w", newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Data", "Horário", "Campo"])
                writer.writerows(saida_geral)
            print(f"Arquivo geral salvo em: {arquivo_saida_geral}")

        # Salva arquivo filtrado
        if saida_filtrada:
            with open(arquivo_saida_filtrado, "w", newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Data", "Horário", "Campo"])
                writer.writerows(saida_filtrada)
            print(f"Arquivo filtrado salvo em: {arquivo_saida_filtrado}")

        # Mostra contagem
        print("\nContagem dos caracteres A-F, 8 e 9 como penúltimo dígito no campo 10:")
        for char in sorted(caracteres_alvo):
            print(f"{char}: {contagem[char]}")

    except Exception as e:
        print(f"\nErro ao processar arquivo: {str(e)}\n")

if __name__ == "__main__":
    while True:
        print("=== PROCESSADOR DE TRAMAS ===\n")
        base = solicitar_base()
        ano, mes, dia = solicitar_data()
        processar_tramas(base, ano, mes, dia)
        print("\n--- Processamento finalizado ---\n")
        input("Pressione Enter para reiniciar ou feche a janela para sair.\n")
