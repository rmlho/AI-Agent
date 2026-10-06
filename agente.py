import os
import json
import time
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
chave_google_maps = os.environ.get("GOOGLE_API_KEY")
chave_gemini = os.environ.get("GEMINI_API_KEY")

if not chave_gemini:
    raise SystemExit("GEMINI_API_KEY não encontrada no .env")

client_ia = genai.Client(api_key=chave_gemini)

MODELO = "gemini-3.8-flash"
URL_PLACES = "https://places.googleapis.com/v1/places:searchText"

# Só pedimos os campos que usamos (a cobrança depende dos campos pedidos).
FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.rating",
    "places.websiteUri",
    "nextPageToken",  # necessário para paginar
])

DADOS_MOCKADOS = {
    "places": [
        {
            "displayName": {"text": "Padaria Pão Quente"},
            "formattedAddress": "Rua João Pessoa, 123, Centro, Campina Grande - PB",
            "nationalPhoneNumber": "(83) 98888-1111",
            "rating": 4.5,
            "websiteUri": "https://www.padariapaoquente.com.br",
        },
        {
            "displayName": {"text": "Lanchonete do Zé"},
            "formattedAddress": "Av. Floriano Peixoto, 456, São José, Campina Grande - PB",
            "nationalPhoneNumber": "(83) 99999-2222",
            "rating": 4.8,
        },
        {
            "displayName": {"text": "Restaurante Sabor da Terra"},
            "formattedAddress": "Rua Marquês do Herval, 789, Centro, Campina Grande - PB",
            "nationalPhoneNumber": "(83) 97777-3333",
            "rating": 4.2,
            "websiteUri": "",
        },
    ]
}


def buscar_lugares(consulta, max_paginas=3):
    """Busca na Places API (New) via Text Search, com paginação.
    Sem GOOGLE_API_KEY, usa os dados mockados."""
    if not chave_google_maps:
        print("Sem GOOGLE_API_KEY, usando dados mockados.\n")
        return DADOS_MOCKADOS

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": chave_google_maps,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    corpo = {
        "textQuery": consulta,
        "languageCode": "pt-BR",
        "regionCode": "BR",
        "pageSize": 20,  # máximo por página
    }

    todos = []
    for _ in range(max_paginas):
        resp = requests.post(URL_PLACES, headers=headers, json=corpo, timeout=15)
        resp.raise_for_status()
        dados = resp.json()
        todos.extend(dados.get("places", []))

        token = dados.get("nextPageToken")
        if not token:
            break
        corpo["pageToken"] = token

    return {"places": todos}


def buscar_lojas_sem_site(dados):
    lojas_filtradas = []
    for lugar in dados.get("places", []):
        if not lugar.get("websiteUri"):
            lojas_filtradas.append({
                "nome": lugar.get("displayName", {}).get("text", "Sem nome"),
                "endereco": lugar.get("formattedAddress", "Sem endereço"),
                "telefone": lugar.get("nationalPhoneNumber", "Sem telefone"),
                "nota": lugar.get("rating", "Sem nota"),
            })
    return lojas_filtradas


def gerar_relatorio_com_ia(lojas, tentativas=4):
    dados_texto = json.dumps(lojas, indent=2, ensure_ascii=False)
    prompt = f"""
    Você é um assistente de prospecção de clientes especializado em desenvolvimento web.
    Você recebeu a seguinte lista de lojas locais em Campina Grande que NÃO têm website:
    {dados_texto}

    Sua tarefa é escrever um pequeno relatório executivo com:
    1. Uma breve saudação inicial para mim.
    2. A lista das lojas formatada com bullets, destacando os pontos fortes
       (ex: notas altas) como argumento para vender um site.
    3. Uma sugestão de estratégia comercial direta de como eu, estudante de
       Ciência da Computação, posso abordá-los e convencê-los do valor de um site.
    """

    for i in range(tentativas):
        try:
            response = client_ia.models.generate_content(
                model=MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            return response.text
        except Exception as e:
            erro = str(e)
            temporario = "503" in erro or "429" in erro
            if temporario and i < tentativas - 1:
                espera = 2 ** (i + 1)  # 2s, 4s, 8s
                print(f"Modelo ocupado, tentando de novo em {espera}s...")
                time.sleep(espera)
            else:
                return f"Erro ao gerar relatório: {e}"


if __name__ == "__main__":
    print("Buscando estabelecimentos...\n")
    try:
        dados = buscar_lugares("restaurantes e lanchonetes em Campina Grande, PB")
    except requests.HTTPError as e:
        raise SystemExit(f"Erro na Places API: {e.response.status_code} {e.response.text}")

    lojas = buscar_lojas_sem_site(dados)
    print(f"{len(lojas)} lojas sem site encontradas.\n")

    if lojas:
        print("=" * 60)
        print(gerar_relatorio_com_ia(lojas))
        print("=" * 60)