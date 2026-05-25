# Arbitralis - PoC de Webhook Nao-Bloqueante

PoC de API em FastAPI para receber webhooks de negociacao via WhatsApp sem bloquear a resposta HTTP enquanto o processamento do LLM acontece.

## Objetivo

Resolver o problema de timeout do webhook desacoplando o recebimento da mensagem do processamento do LLM.

## Como funciona

1. `POST /webhook` recebe o payload e retorna `202 Accepted` imediatamente.
2. A mensagem entra em uma fila em memoria.
3. Um worker assincromo consome a fila, chama um LLM simulado (com latencia e falha ocasional) e dispara a resposta final via um gateway mock.

## Endpoints

- `POST /webhook`
  - Exemplo de payload:

    ```json
    {
      "user_id": "5511999999999",
      "message": "Quero renegociar minha divida"
    }
    ```

  - Retorno: `202 Accepted`
- `GET /messages/{message_id}`
  - Consulta status do processamento (`queued`, `processing`, `sent`, `failed`)
- `GET /outbound-mock`
  - Mostra envios simulados de resposta ao usuario

## Rodando localmente

Requisitos:

- Python 3.11+

Instalacao:

```bash
pip install -r requirements.txt
```

Executar API:

```bash
uvicorn app.main:app --reload --port 8000
```

## Executando testes

```bash
pytest -q
```

Os testes cobrem:

- resposta nao-bloqueante mesmo com LLM lento
- fluxo de sucesso com envio no mock outbound
- fluxo de erro com falha do LLM.
