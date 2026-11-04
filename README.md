# Cofre

Gerenciador de senhas local para Windows e Linux. Guarda contas e senhas em um único arquivo criptografado, gera senhas fortes e não usa rede.

> "Cofre" é um nome provisório.

## O que faz

- Cria o cofre protegido por uma **senha mestra** (sem recuperação: se esquecer, os dados se perdem).
- **Cadastra** contas (serviço, usuário e senha), com **gerador de senha forte** configurável ou senha própria. A conta pode não ter usuário.
- **Lista, revela, copia e exclui** entradas. A senha copiada é apagada da área de transferência em 30 s.
- **Bloqueia sozinho** após 5 minutos de inatividade.
- **Exporta e restaura backups** criptografados.

Tudo fica cifrado localmente (AES-256-GCM, chave derivada com Argon2id). Detalhes em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) e dicas de uso seguro em [`docs/SEGURANCA.md`](docs/SEGURANCA.md).

## Usar

### Executável

Baixe o executável da sua plataforma na página de versões, confira o `SHA256SUMS` e execute. Não precisa instalar Python. Veja [Verificar o download](docs/SEGURANCA.md#verificar-o-download).

### A partir do código

Requer Python 3.12 ou superior.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/cofre
```

No Windows, os comandos ficam em `.venv\Scripts\`.

O cofre é gravado na pasta de dados do aplicativo do seu usuário (`~/.local/share/Cofre/vault.cofre` no Linux, `%APPDATA%\Cofre\vault.cofre` no Windows). Para experimentar sem tocar nos seus dados:

```bash
XDG_DATA_HOME=/tmp/cofre-teste .venv/bin/cofre     # Linux
```

## Desenvolver

```bash
.venv/bin/pytest          # testes (a interface roda em modo offscreen)
.venv/bin/ruff check .    # lint
```

### Gerar o executável

O PyInstaller não gera binários para outro sistema: construa em cada plataforma de destino (o fluxo do GitHub Actions faz isso para Linux e Windows).

```bash
.venv/bin/pip install -e ".[build]"
.venv/bin/pyinstaller packaging/cofre.spec --noconfirm --distpath dist --workpath build
dist/cofre --self-test && echo ok
.venv/bin/python scripts/checksums.py dist
```

### Dependências

`requirements.in` lista as dependências diretas, e `requirements.lock` traz as versões exatas com hashes. Para atualizar:

```bash
pip install pip-tools pip-audit
pip-compile --generate-hashes --allow-unsafe --strip-extras --output-file requirements.lock requirements.in
pip-audit --require-hashes -r requirements.lock
```

## Estado do projeto

| Item | Situação |
|---|---|
| Funcionalidades do MVP | Prontas |
| Testes automatizados | Passam no Linux |
| Executável Linux | Gerado e testado |
| Windows | **Ainda não testado**: o fluxo de CI está escrito, mas nunca foi executado |
| Assinatura de código | Não há |
