# Arquitetura do Cofre

Gerenciador de senhas desktop para Windows e Linux. Guarda contas e senhas em um único arquivo local criptografado e gera senhas fortes. Não usa rede.

## Modelo de ameaças

**Protege contra:**
- roubo ou cópia do arquivo do cofre, do disco ou de um backup;
- adulteração do arquivo, detectada ao abrir.

**Não protege contra:**
- malware ou keylogger na máquina, principalmente com o cofre aberto;
- senha mestra fraca ou reutilizada.

**Limites conhecidos:**
- `lock()` descarta as referências à chave e aos dados, mas não apaga a memória. `str` e `bytes` são imutáveis em Python, então os valores permanecem até serem sobrescritos. O bloqueio automático reduz essa janela.
- O tamanho do arquivo revela aproximadamente o volume de dados guardados. Não há preenchimento (padding).
- Uma entrada excluída permanece cifrada no `.bak` até a gravação seguinte.
- A senha copiada fica na área de transferência por até 30 s. As marcações de conteúdo sensível só são obedecidas por gerenciadores que seguem a convenção (KDE Klipper no Linux; histórico e nuvem do Windows). Qualquer outro pode guardar a senha.
- Revelar mostra a senha em um diálogo modal. O bloqueio automático (F4) precisará fechá-lo.

## Camadas

```
ui  ->  services  ->  storage  ->  crypto
           |             |
           +--> domain <-+
```

| Camada | Responsabilidade | Módulo |
|---|---|---|
| `domain` | Entidades, regras de negócio, gerador de senhas | `domain/models.py`, `domain/passwords.py` |
| `crypto` | Argon2id e AES-256-GCM | `crypto/vault_crypto.py` |
| `storage` | Formato binário, gravação atômica, `.bak` | `storage/vault_file.py` |
| `services` | Casos de uso, estado do cofre aberto | `services/vault_service.py` |
| `ui` | Telas em PySide6; operações lentas fora da thread da interface | `ui/` |

Só `ui/` importa Qt, e o núcleo não importa rede nem logging. `tests/test_architecture.py` verifica essas regras.

## Formato do arquivo

Big-endian. Cabeçalho de 46 bytes, autenticado por inteiro como AAD.

| Campo | Tamanho | Valor |
|---|---|---|
| magic | 4 | `COFR` |
| versão | 2 | `1` |
| memória (KiB) | 4 | `65536` |
| iterações | 4 | `3` |
| pistas | 4 | `4` |
| salt | 16 | aleatório, fixo durante a vida do cofre |
| nonce | 12 | aleatório, novo a cada gravação |
| ciphertext + tag | variável | JSON em UTF-8 cifrado, tag de 16 bytes |

Conteúdo decifrado:

```json
{"entries": [{"service": "...", "username": "...", "password": "..."}]}
```

## Decisões

| Decisão | Motivo |
|---|---|
| Argon2id pelo `cryptography` | Resistente a GPU, sem dependência extra |
| Cifrar o JSON inteiro | Oculta também os nomes de serviços e usuários |
| Limites de KDF validados antes de derivar | O cabeçalho só é autenticado depois de derivar a chave; sem limites, um arquivo adulterado poderia esgotar a memória |
| Normalização NFKC da senha mestra | O mesmo texto pode chegar em bytes diferentes em cada sistema, e o cofre precisa abrir nos dois |
| Chave derivada mantida em memória com o cofre aberto | Gravar não exige redigitar a senha nem repetir o Argon2id |
| `Vault` imutável, trocado após gravar | Falha de disco não deixa a tela mostrando uma entrada não salva |
| Mesma mensagem para senha errada e arquivo inválido | O GCM não distingue os dois casos, e a mensagem não dá pistas |
| `(serviço, usuário)` único, sem diferenciar maiúsculas | "GitHub" e "github" são o mesmo serviço |
| Sorteio com rejeição no gerador | Garante as classes de caracteres sem introduzir viés |

## Regras de negócio

| # | Regra | Onde |
|---|---|---|
| RN1 | Serviço e senha obrigatórios; usuário obrigatório, salvo conta explicitamente sem usuário (`None`); par (serviço, usuário) único, e só uma conta sem usuário por serviço | `domain/models.py` |
| RN2 | Senha mestra com 12+ caracteres, confirmação e ciência de que não há recuperação | `domain/passwords.py`, `services/vault_service.py` |
| RN3 | Gerador com `secrets`: padrão 20, faixa 12 a 64, ao menos um de cada classe | `domain/passwords.py` |
| RN4 | Senhas ocultas por padrão; revelar é ação explícita por entrada | `ui/main_view.py`, `ui/reveal_dialog.py` |
| RN5 | Área de transferência limpa após 30 s, se o conteúdo não mudou; também ao bloquear e ao sair | `ui/clipboard.py` |
| RN6 | Bloqueio após 5 min de inatividade | `ui/` (F4) |
| RN7 | Excluir exige confirmação | `services/vault_service.py` |
| RN8 | Segredos fora de logs, mensagens de erro e `repr` | todas as camadas |

## Plano do MVP

| Feature | Entrega | Situação |
|---|---|---|
| Núcleo | Regras, criptografia, arquivo | Concluída |
| F1 | Criar e desbloquear o cofre | Concluída |
| F2 | Cadastrar e listar, com gerador | Concluída |
| F2.1 | Conta sem usuário (checkbox no cadastro) | Concluída |
| F3 | Revelar, copiar com limpeza, excluir | Concluída |
| F4 | Bloqueio automático | Próxima |
| F5 | Exportar e restaurar backup | Planejada |
| F6 | Executáveis, CI, `pip-audit`, `docs/SEGURANCA.md` | Planejada |

## Desenvolvimento

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
```

No Windows, os executáveis ficam em `.venv\Scripts\`.
