"""Envia para a API todos os PDFs de uma pasta e acompanha a indexação.

Arquivos com o mesmo nome de um manual já cadastrado são pulados.
Exige um usuário administrador; a senha é pedida sem aparecer na tela.

Uso (na pasta backend):
    .venv\\Scripts\\python scripts\\importar_manuais.py ..\\manuais-para-importar --usuario gabriel
    .venv\\Scripts\\python scripts\\importar_manuais.py C:\\manuais --usuario gabriel --api http://servidor:8000
"""

import argparse
import getpass
import sys
import time
from pathlib import Path
from typing import Any

import httpx

POLL_INTERVAL_SECONDS = 3
MAX_WAIT_SECONDS = 15 * 60


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa os PDFs de uma pasta para a API.")
    parser.add_argument("pasta", type=Path, help="Pasta com os PDFs")
    parser.add_argument("--api", default="http://localhost:8000", help="Endereço da API")
    parser.add_argument("--usuario", required=True, help="Login de um administrador")
    args = parser.parse_args()

    folder: Path = args.pasta
    if not folder.is_dir():
        print(f"Pasta não encontrada: {folder}")
        return 1
    pdfs = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"Nenhum PDF em {folder.resolve()}")
        return 0

    with httpx.Client(base_url=args.api, timeout=120) as client:
        # O cookie de sessão devolvido pelo login fica guardado no próprio client.
        response = client.post(
            "/api/v1/auth/login",
            json={"username": args.usuario, "password": getpass.getpass("Senha: ")},
        )
        if response.status_code != httpx.codes.OK:
            print(f"Login recusado: {_detail(response)}")
            return 1
        if response.json()["must_change_password"]:
            print("Troque sua senha provisória no sistema antes de importar.")
            return 1

        existing = {m["file_name"] for m in _get_json(client, "/api/v1/manuals")}
        sent: dict[str, str] = {}
        for pdf in pdfs:
            if pdf.name in existing:
                print(f"[pulado]   {pdf.name}: já cadastrado")
                continue
            with pdf.open("rb") as file:
                response = client.post(
                    "/api/v1/manuals", files={"file": (pdf.name, file, "application/pdf")}
                )
            if response.status_code == httpx.codes.ACCEPTED:
                sent[response.json()["id"]] = pdf.name
                print(f"[enviado]  {pdf.name}: indexando...")
            else:
                print(f"[recusado] {pdf.name}: {_detail(response)} (HTTP {response.status_code})")

        failures = _wait_for_indexing(client, sent)

    print(f"\nConcluído: {len(sent) - failures} indexado(s), {failures} falha(s).")
    return 1 if failures else 0


def _wait_for_indexing(client: httpx.Client, sent: dict[str, str]) -> int:
    pending = dict(sent)
    failures = 0
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while pending and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        for manual_id, name in list(pending.items()):
            manual = _get_json(client, f"/api/v1/manuals/{manual_id}")
            if manual["status"] == "indexed":
                pages, chunks = manual["page_count"], manual["chunk_count"]
                print(f"[ok]       {name}: {pages} páginas, {chunks} trechos")
            elif manual["status"] == "failed":
                print(f"[falhou]   {name}: {manual['failure_reason']}")
                failures += 1
            else:
                continue
            del pending[manual_id]
    for name in pending.values():
        print(f"[aguarde]  {name}: ainda processando; acompanhe pelo GET /api/v1/manuals")
    return failures


def _get_json(client: httpx.Client, path: str) -> Any:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", ""))
    except ValueError:
        return response.text[:200]


if __name__ == "__main__":
    sys.exit(main())
