# Guia de segurança do Cofre

Um gerenciador local criptografado reduz muito o risco, mas não o elimina. Este guia diz o que o aplicativo faz sozinho, o que depende de você e como aumentar ainda mais a segurança.

## O que o aplicativo faz por você

| Proteção | Como |
|---|---|
| Dados cifrados em disco | AES-256-GCM; a chave vem da senha mestra com Argon2id (64 MiB, 3 iterações, 4 pistas) e nunca é gravada |
| Adulteração detectada | Qualquer byte alterado no arquivo impede a abertura |
| Nada legível no arquivo | Serviços, usuários e senhas ficam todos dentro do conteúdo cifrado |
| Sem rede | O aplicativo não tem nenhuma função de rede; um teste automatizado bloqueia sockets durante o fluxo completo |
| Bloqueio automático | Após 5 min sem mouse ou teclado no aplicativo, ele fecha diálogos abertos, limpa a área de transferência e bloqueia |
| Área de transferência | A senha copiada é apagada em 30 s, ao bloquear e ao sair, sem destruir o que você copiou depois |
| Gravação segura | Arquivo temporário, `fsync`, troca atômica e cópia anterior em `.bak`; permissão `0600` no Linux |

## O que ele não protege

- **Malware ou keylogger no computador**, principalmente com o cofre aberto. Quem controla a máquina vê o que você vê.
- **Senha mestra fraca ou reutilizada.** Ela é a única barreira contra quem copiar o arquivo.
- **Senha mestra esquecida.** Não existe recuperação, por projeto.
- **Memória.** Em Python, senhas já usadas não são apagadas da memória na hora; o bloqueio descarta as referências, mas não sobrescreve os bytes.
- **Gerenciadores de área de transferência que ignoram a marcação de conteúdo sensível** podem guardar a senha copiada.

## Como aumentar ainda mais a segurança

### 1. Senha mestra
- Use uma frase longa e única, com 4 a 6 palavras sem relação entre si. O mínimo do aplicativo é 12 caracteres; mais é melhor.
- Nunca a reutilize em outro serviço e não a guarde no mesmo lugar que o backup. Uma cópia em papel, em local físico seguro, é aceitável.

### 2. Autenticação em dois fatores (2FA)
- **Um código TOTP dentro do próprio cofre não protegeria o arquivo.** O segredo ficaria na mesma máquina, e quem copia o arquivo ataca a criptografia diretamente, sem passar por tela alguma. Por isso o aplicativo não tem esse recurso.
- **Onde o 2FA realmente ajuda:** nas contas que você guarda (e-mail, banco, GitHub). Mesmo que uma senha vaze, ela não basta para entrar. Prefira chave de segurança física (FIDO2) ou aplicativo autenticador; evite SMS.
- **Guarde os códigos de recuperação e o aplicativo autenticador fora do cofre.** Juntos no mesmo lugar, os dois fatores viram um só.
- **Melhoria futura:** um segundo fator que participe da derivação da chave (arquivo-chave ou chave FIDO2 com `hmac-secret`). O formato do arquivo é versionado e permite isso, mas não está nesta versão.

### 3. Backups criptografados
- **Exportar backup** copia o arquivo já cifrado; ele usa a mesma senha mestra e pode ir para a nuvem ou para um pendrive sem nova criptografia.
- **Regra 3-2-1:** 3 cópias, em 2 tipos de mídia, com 1 fora de casa.
- **O `.bak` automático não é um backup.** Ele protege contra gravação interrompida, mas fica na mesma pasta e se perde junto com o disco.
- **Teste a restauração de vez em quando.** Backup nunca testado não é backup. Em "Restaurar backup", o aplicativo valida a senha antes de substituir o cofre, e o cofre anterior fica no `.bak`.
- Exporte de novo depois de mudanças importantes; o backup é uma foto do momento.
- Uma entrada excluída continua cifrada no `.bak` e em backups antigos até serem sobrescritos.

### 4. Firewall
O firewall não impede o roubo do arquivo local; ele dificulta a invasão da máquina e a saída de dados.
- **Entrada:** mantenha o padrão de negar o que chega e abra só o necessário (`firewalld` no Fedora, Windows Defender Firewall).
- **Saída, como reforço opcional:** como o aplicativo não precisa de rede, você pode bloqueá-la.
  - **Windows** (PowerShell como administrador):
    ```powershell
    New-NetFirewallRule -DisplayName "Cofre sem rede" -Direction Outbound -Action Block -Program "C:\caminho\cofre.exe"
    ```
  - **Linux:** execute sem acesso à rede com `unshare -rn ./cofre`. Testado em sessão Wayland, onde o aplicativo abre normalmente; em sessões X11 o isolamento pode impedir a conexão com a tela, então teste antes de depender disso.

### 5. Atualizações
- **Do aplicativo:** o executável traz sua própria criptografia (OpenSSL) e o Qt embutidos, então atualizações do sistema **não** corrigem falhas nessas partes. Instale as novas versões do Cofre quando forem publicadas. O projeto fixa as dependências com hash e as audita com `pip-audit` a cada alteração.
- **Do sistema:** mantenha o sistema operacional e o navegador em dia. É por eles que a maioria dos ataques chega.
- **Atualizar nunca exige enviar o cofre a lugar nenhum.** O aplicativo não verifica atualizações sozinho, para continuar sem rede.

### 6. O ambiente
- Criptografe o disco (LUKS no Linux, BitLocker no Windows): protege também os rastros que o aplicativo não controla, como arquivos temporários e memória em disco.
- Bloqueie a tela do sistema ao se afastar. O bloqueio automático do Cofre só enxerga a atividade dentro dele.
- Use uma conta de usuário sem privilégios de administrador no dia a dia.

## Verificar o download

Cada versão publicada traz um arquivo `SHA256SUMS`. Antes de executar, confira:

```bash
sha256sum -c SHA256SUMS            # Linux
Get-FileHash cofre.exe -Algorithm SHA256   # Windows: compare com o valor do arquivo
```

Para conferir que o pacote funciona na sua máquina sem abrir a interface:

```bash
./cofre --self-test && echo ok     # código de saída 0 = tudo certo
```

O executável para Windows **não é assinado**, então o SmartScreen pode exibir um aviso. Um certificado de assinatura de código é pago e fica como decisão futura.
