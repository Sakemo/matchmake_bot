# Tinder Bot - Discord Matchmaking Bot

## Visão Geral
O **Tinder Bot** é um bot de matchmaking para servidores do Discord, permitindo que usuários encontrem parceiros compatíveis com base em um sistema de perguntas e testes. Administradores podem configurar perguntas e definir regras de compatibilidade para melhorar a precisão das combinações.

## Instalação
Para adicionar o bot ao seu servidor, clique no link abaixo:

[Instalar Tinder Bot](https://discord.com/oauth2/authorize?client_id=1335015453633941658)

## Configuração
1. **Adicione o bot ao seu servidor.**
2. **Dê permissões administrativas se desejar configurar perguntas e compatibilidades.**
3. **Utilize os comandos abaixo para configurar e usar o bot.**

## Comandos Principais

### Comandos de Administração
Esses comandos são acessíveis apenas por administradores.

- `/tutorial_admin` - Exibe um tutorial sobre os comandos administrativos.
- `/add_question` - Adiciona uma nova pergunta ao sistema de matchmaking.
- `/delete_question` - Remove uma pergunta existente.
- `/edit_question` - Edita o texto de uma pergunta existente.
- `/current_form` - Exibe a lista atual de perguntas cadastradas.
- `/add_role_compatibility` - Define a compatibilidade entre dois cargos.
- `/register_gender_role` - Registra um cargo representando um gênero.
- `/register_orientation_role` - Registra um cargo representando uma orientação sexual.

### Comandos de Usuário

- `/register_match` - Registra suas respostas para o matchmaking.
- `/find_match` - Busca um usuário compatível dentro do servidor.

## Como Funciona o Matchmaking
1. **Os administradores definem perguntas personalizadas** para entender melhor as preferências dos usuários.
2. **Os usuários respondem ao questionário** utilizando o comando `/register_match`.
3. **O bot cruza as respostas e os cargos de compatibilidade**, identificando pares ideais com base nos critérios estabelecidos.
4. **Os usuários podem procurar um match** usando `/find_match`, e o bot sugerirá uma pessoa compatível dentro do servidor.

## Tecnologia Utilizada
- **Linguagem:** Python
- **Bibliotecas:** discord.py, SQLite
- **Armazena perguntas e respostas no banco de dados SQLite.**
- **Utiliza um sistema de pontuação para medir compatibilidade.**

## Contribuição
Se quiser contribuir, faça um fork do repositório e envie um pull request. Sugestões de melhorias são bem-vindas!

## Licença
Este projeto está sob a licença MIT.
