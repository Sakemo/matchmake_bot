import discord
from discord.ext import commands
import json
import re
import database as db  # Certifique-se de que seu módulo "database" já tenha as tabelas necessárias

# SETUP
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

###############################
# Funções de carregamento e parse
###############################

def load_questions():
    """Carrega as perguntas gerais do banco de dados."""
    db.cursor.execute("SELECT * FROM questions")
    rows = db.cursor.fetchall()
    questions = []
    for row in rows:
        q = {
            "key": row[0],
            "question": row[1],
            "type": row[2],
            "match_type": row[3],
            "weight": row[4]
        }
        if row[2] == "choice" and row[5]:
            q["choices"] = row[5].split(",")
        questions.append(q)
    return questions

def parse_bdsm_test(input_text):
    """Extrai os dados do BDSMTest a partir de um texto formatado."""
    results = {}
    lines = input_text.strip().split("\n")
    for line in lines:
        match = re.match(r"(\d+)%\s+(.+)", line)
        if match:
            percentage = int(match.group(1))
            category = match.group(2).strip()
            results[category] = percentage
    return results

###############################
# Cálculo de Compatibilidade
###############################

def calc_match(user_answers, other_answers, questions):
    """
    Calcula a compatibilidade baseada nas respostas gerais.
    """
    score_total = 0
    score_max = 0
    for q in questions:
        key = q["key"]
        weight = q["weight"]
        score_max += weight * 100
        a = user_answers.get(key)
        b = other_answers.get(key)
        if a is None or b is None:
            continue

        if q["match_type"] == "similarity":
            if a == b:
                score_total += weight * 100
        elif q["match_type"] == "complementary":
            if q["type"] == "choice":
                if a != b:
                    score_total += weight * 100
            elif q["type"] == "number":
                try:
                    a_num = float(a)
                    b_num = float(b)
                    diff = abs(a_num - b_num)
                    score_total += weight * (100 - min(diff, 100))
                except ValueError:
                    pass
    return (score_total / score_max) * 100 if score_max else 0

def calc_bdsm_compatibility(user_test: dict, other_test: dict):
    """
    Calcula a compatibilidade dos resultados do BDSMTest.org considerando pares complementares.
    """
    complementary_pairs = {
        "Dominant": "Submissive",
        "Submissive": "Dominant",
        "Sadist": "Masochist",
        "Masochist": "Sadist",
        "Brat tamer": "Brat",
        "Brat": "Brat tamer",
        "Daddy/Mommy": "Slave",
        "Slave": "Daddy/Mommy",
        "Primal (Hunter)": "Primal (Presa)",
        "Primal (Presa)": "Primal (Hunter)"
    }
    score = 0
    count = 0
    for key, comp in complementary_pairs.items():
        if key in user_test and comp in other_test:
            score += (user_test[key] + other_test[comp]) / 2
            count += 1
    # Tratamento especial para Switch
    if "Switch" in user_test and "Switch" in other_test:
        score += min(user_test["Switch"], other_test["Switch"])
        count += 1
    return score / count if count > 0 else 0

def calcular_role_compatibilidade(member_a: discord.Member, member_b: discord.Member):
    """
    Calcula um bônus de compatibilidade com base nos cargos dos membros.
    """
    total_bonus = 0
    for role_a in member_a.roles:
        for role_b in member_b.roles:
            db.cursor.execute("SELECT score FROM role_compatibility WHERE role_from = ? AND role_to = ?",
                              (str(role_a.id), str(role_b.id)))
            row = db.cursor.fetchone()
            if row:
                total_bonus += row[0]
    return total_bonus

def calc_total_match_full(user_answers, other_answers, questions, user_test, other_test, member_user, member_candidate):
    """
    Calcula a compatibilidade total com os pesos:
      - 50% das respostas gerais,
      - 30% do BDSMTest,
      - 20% dos bônus de cargos.
    """
    base_score = calc_match(user_answers, other_answers, questions)
    bdsm_score = calc_bdsm_compatibility(user_test, other_test)
    bonus = calcular_role_compatibilidade(member_user, member_candidate)
    total = base_score * 0.5 + bdsm_score * 0.3 + bonus * 0.2
    return min(max(total, 0), 100)

###############################
# Eventos e Comandos do Bot
###############################

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Bot logado como {bot.user} (ID: {bot.user.id})')

# Evento para erros de permissão
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("Você não possui permissão para executar este comando.", ephemeral=True)
    else:
        await interaction.response.send_message("Ocorreu um erro inesperado.", ephemeral=True)

###############################
# Comandos Administrativos
###############################

# Tutorial interativo para administradores
@bot.tree.command(name="tutorial_admin", description="Tutorial interativo de comandos administrativos.")
async def tutorial_admin(interaction: discord.Interaction):
    tutorial_text = (
        "**Tutorial de Administração do Matchmaking Bot**\n\n"
        "1. **/add_question**: Adiciona uma nova pergunta. Informe chave, texto (máx. 45 caracteres), tipo, match_type, peso e, se necessário, as opções separadas por vírgula.\n"
        "2. **/delete_question**: Remove uma pergunta existente, informando a chave.\n"
        "3. **/edit_question**: Edita o texto de uma pergunta.\n"
        "4. **/add_role_compatibility**: Define a compatibilidade entre dois cargos.\n"
        "5. **/register_gender_role** e **/register_orientation_role**: Registre cargos que representam gêneros e orientações sexuais.\n"
        "\nUtilize os comandos com atenção e verifique as respostas do bot para confirmar suas ações."
    )
    await interaction.response.send_message(tutorial_text, ephemeral=True)

# Comando para adicionar nova pergunta (Admin) com autocomplete para q_type e match_type
@bot.tree.command(name="add_question", description="Adiciona uma nova pergunta ao matchmaking (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(
    key="Chave única da pergunta",
    question="Texto da pergunta (máximo 45 caracteres)",
    q_type="Tipo da pergunta",
    match_type="Tipo de compatibilidade",
    weight="Peso da pergunta",
    choices="Opções separadas por vírgula (se aplicável)"
)
@discord.app_commands.choices(
    q_type=[
        discord.app_commands.Choice(name="choice", value="choice"),
        discord.app_commands.Choice(name="number", value="number")
    ],
    match_type=[
        discord.app_commands.Choice(name="similarity", value="similarity"),
        discord.app_commands.Choice(name="complementary", value="complementary")
    ]
)
async def add_question(interaction: discord.Interaction, key: str, question: str, q_type: str, match_type: str, weight: float, choices: str = ""):
    if len(question) > 45:
        await interaction.response.send_message("A pergunta não pode ultrapassar 45 caracteres!", ephemeral=True)
        return
    try:
        db.cursor.execute(
            "INSERT INTO questions (key, question, type, match_type, weight, choices) VALUES (?, ?, ?, ?, ?, ?)",
            (key, question, q_type, match_type, weight, choices)
        )
        db.conn.commit()
        await interaction.response.send_message(f"Pergunta adicionada com sucesso: {question}", ephemeral=True)
    except db.sqlite3.IntegrityError:
        await interaction.response.send_message("Já existe uma pergunta com essa chave!", ephemeral=True)

# Comando para apagar uma pergunta (Admin)
@bot.tree.command(name="delete_question", description="Apaga uma pergunta do matchmaking (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(key="Chave da pergunta a ser apagada")
async def delete_question(interaction: discord.Interaction, key: str):
    db.cursor.execute("SELECT * FROM questions WHERE key = ?", (key,))
    row = db.cursor.fetchone()
    if not row:
        await interaction.response.send_message("Pergunta não encontrada!", ephemeral=True)
        return
    db.cursor.execute("DELETE FROM questions WHERE key = ?", (key,))
    db.conn.commit()
    await interaction.response.send_message("Pergunta apagada com sucesso!", ephemeral=True)

# Comando para editar pergunta (Admin)
@bot.tree.command(name="edit_question", description="Edita o texto de uma pergunta do matchmaking (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(key="Chave da pergunta a ser editada", new_question="Novo texto da pergunta (máximo 45 caracteres)")
async def edit_question(interaction: discord.Interaction, key: str, new_question: str):
    if len(new_question) > 45:
        await interaction.response.send_message("O novo texto não pode ultrapassar 45 caracteres!", ephemeral=True)
        return
    db.cursor.execute("SELECT * FROM questions WHERE key = ?", (key,))
    row = db.cursor.fetchone()
    if not row:
        await interaction.response.send_message("Pergunta não encontrada!", ephemeral=True)
        return
    db.cursor.execute("UPDATE questions SET question = ? WHERE key = ?", (new_question, key))
    db.conn.commit()
    await interaction.response.send_message("Pergunta atualizada com sucesso!", ephemeral=True)

# Comando para listar perguntas (Admin ou Usuário)
@bot.tree.command(name="current_form", description="Exibe a lista atual de perguntas do matchmaking.")
async def current_form(interaction: discord.Interaction):
    questions = load_questions()
    if not questions:
        await interaction.response.send_message("Nenhuma pergunta cadastrada!", ephemeral=True)
        return
    desc = "\n".join([f"**{q['key']}**: {q['question']}" for q in questions])
    embed = discord.Embed(title="Perguntas Atuais", description=desc, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Comando para adicionar/editar compatibilidade entre cargos (Admin)
@bot.tree.command(name="add_role_compatibility", description="Define pontuação de compatibilidade entre cargos (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(role_from="Cargo de origem", role_to="Cargo de destino", score="Pontuação de compatibilidade")
async def add_role_compatibility(interaction: discord.Interaction, role_from: discord.Role, role_to: discord.Role, score: float):
    try:
        db.cursor.execute(
            "INSERT OR REPLACE INTO role_compatibility (role_from, role_to, score) VALUES (?, ?, ?)",
            (str(role_from.id), str(role_to.id), score)
        )
        db.conn.commit()
        await interaction.response.send_message(
            f"Compatibilidade entre **{role_from.name}** e **{role_to.name}** definida como {score}.",
            ephemeral=True
        )
    except Exception:
        await interaction.response.send_message("Erro ao definir compatibilidade de cargos.", ephemeral=True)

# Comandos para registrar cargos de gênero e orientação (Admin)
@bot.tree.command(name="register_gender_role", description="Registra um cargo representando um gênero (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(role="Cargo a ser registrado", gender="Gênero a ser associado ao cargo")
@discord.app_commands.choices(gender=[
    discord.app_commands.Choice(name="Masculino", value="Masculino"),
    discord.app_commands.Choice(name="Feminino", value="Feminino"),
    discord.app_commands.Choice(name="Não Binário", value="Não Binário")
])
async def register_gender_role(interaction: discord.Interaction, role: discord.Role, gender: str):
    try:
        db.cursor.execute("INSERT OR REPLACE INTO gender_roles (role_id, gender) VALUES (?, ?)", (str(role.id), gender))
        db.conn.commit()
        await interaction.response.send_message(f"Cargo **{role.name}** registrado como **{gender}**.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Erro ao registrar o cargo de gênero.", ephemeral=True)

@bot.tree.command(name="register_orientation_role", description="Registra um cargo representando uma orientação sexual (Admin)")
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(role="Cargo a ser registrado", orientation="Orientação sexual a ser associada ao cargo")
@discord.app_commands.choices(orientation=[
    discord.app_commands.Choice(name="Heterossexual", value="Heterossexual"),
    discord.app_commands.Choice(name="Homossexual", value="Homossexual"),
    discord.app_commands.Choice(name="Bissexual", value="Bissexual"),
    discord.app_commands.Choice(name="Assexual", value="Assexual")
])
async def register_orientation_role(interaction: discord.Interaction, role: discord.Role, orientation: str):
    try:
        db.cursor.execute("INSERT OR REPLACE INTO orientation_roles (role_id, orientation) VALUES (?, ?)", (str(role.id), orientation))
        db.conn.commit()
        await interaction.response.send_message(f"Cargo **{role.name}** registrado como **{orientation}**.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Erro ao registrar o cargo de orientação.", ephemeral=True)

###############################
# Modais e Comandos de Respostas Gerais
###############################

def create_match_modal(questions):
    """Modal dinâmico para registrar respostas gerais."""
    class MatchModal(discord.ui.Modal, title="Registro de Matchmaking"):
        def __init__(self):
            super().__init__()
            self.answers = {}
            for q in questions:
                self.add_item(
                    discord.ui.TextInput(
                        label=q["question"][:45],
                        placeholder="Digite aqui sua resposta...",
                        custom_id=q["key"],
                        required=True
                    )
                )

        async def on_submit(self, interaction: discord.Interaction):
            for item in self.children:
                self.answers[item.custom_id] = item.value
            db.cursor.execute(
                "REPLACE INTO responses (user_id, answers) VALUES (?, ?)",
                (str(interaction.user.id), json.dumps(self.answers))
            )
            db.conn.commit()
            await interaction.response.send_message("Respostas registradas com sucesso!", ephemeral=True)
    return MatchModal()

@bot.tree.command(name="register_match", description="Registre suas respostas para o matchmaking.")
async def register_match(interaction: discord.Interaction):
    questions = load_questions()
    if not questions:
        await interaction.response.send_message("Nenhuma pergunta configurada ainda!", ephemeral=True)
        return
    await interaction.response.send_modal(create_match_modal(questions))

@bot.tree.command(name="edit_answer", description="Edite sua resposta para uma pergunta específica.")
@discord.app_commands.describe(key="Chave da pergunta", new_value="Nova resposta")
async def edit_answer(interaction: discord.Interaction, key: str, new_value: str):
    db.cursor.execute("SELECT answers FROM responses WHERE user_id = ?", (str(interaction.user.id),))
    row = db.cursor.fetchone()
    if not row:
        await interaction.response.send_message("Você ainda não registrou suas respostas!", ephemeral=True)
        return
    answers = json.loads(row[0])
    if key not in answers:
        await interaction.response.send_message("Pergunta não encontrada!", ephemeral=True)
        return
    answers[key] = new_value
    db.cursor.execute("UPDATE responses SET answers = ? WHERE user_id = ?", (json.dumps(answers), str(interaction.user.id)))
    db.conn.commit()
    await interaction.response.send_message("Resposta atualizada com sucesso!", ephemeral=True)

@bot.tree.command(name="import_test", description="Importa os resultados do BDSMTest.org para o matchmaking.")
@discord.app_commands.describe(test_input="Resultados do teste (formato: 'X% Categoria' em cada linha)")
async def import_test(interaction: discord.Interaction, test_input: str):
    test_data = parse_bdsm_test(test_input)
    if not test_data:
        await interaction.response.send_message("Formato inválido. Certifique-se de usar 'X% Categoria' por linha.", ephemeral=True)
        return
    db.cursor.execute(
        "REPLACE INTO bdsm_responses (user_id, test_data) VALUES (?, ?)",
        (str(interaction.user.id), json.dumps(test_data))
    )
    db.conn.commit()
    await interaction.response.send_message("Resultados do BDSMTest importados com sucesso!", ephemeral=True)

@bot.tree.command(name="clear_test", description="Limpa os resultados do BDSMTest registrados.")
async def clear_test(interaction: discord.Interaction):
    db.cursor.execute("DELETE FROM bdsm_responses WHERE user_id = ?", (str(interaction.user.id),))
    db.conn.commit()
    await interaction.response.send_message("Resultados do BDSMTest limpos com sucesso!", ephemeral=True)

@bot.tree.command(name="clear_responses", description="Apaga todas as suas respostas gerais de matchmaking.")
async def clear_responses(interaction: discord.Interaction):
    db.cursor.execute("DELETE FROM responses WHERE user_id = ?", (str(interaction.user.id),))
    db.conn.commit()
    await interaction.response.send_message("Respostas gerais apagadas com sucesso!", ephemeral=True)

def create_edit_responses_modal(questions, current_answers):
    """Modal para edição das respostas gerais, pré-preenchido com as respostas atuais."""
    class EditResponsesModal(discord.ui.Modal, title="Editar Respostas Gerais"):
        def __init__(self):
            super().__init__()
            self.new_answers = {}
            for q in questions:
                default_val = current_answers.get(q["key"], "")
                self.add_item(
                    discord.ui.TextInput(
                        label=q["question"][:45],
                        placeholder="Digite sua nova resposta...",
                        default=default_val,
                        custom_id=q["key"],
                        required=False
                    )
                )

        async def on_submit(self, interaction: discord.Interaction):
            for item in self.children:
                self.new_answers[item.custom_id] = item.value
            db.cursor.execute("UPDATE responses SET answers = ? WHERE user_id = ?", (json.dumps(self.new_answers), str(interaction.user.id)))
            db.conn.commit()
            await interaction.response.send_message("Respostas gerais atualizadas com sucesso!", ephemeral=True)
    return EditResponsesModal()

@bot.tree.command(name="edit_responses", description="Edita todas as suas respostas gerais de matchmaking.")
async def edit_responses(interaction: discord.Interaction):
    questions = load_questions()
    db.cursor.execute("SELECT answers FROM responses WHERE user_id = ?", (str(interaction.user.id),))
    row = db.cursor.fetchone()
    current_answers = json.loads(row[0]) if row else {}
    await interaction.response.send_modal(create_edit_responses_modal(questions, current_answers))

class EditBioModal(discord.ui.Modal, title="Editar Bio"):
    def __init__(self, current_bio):
        super().__init__()
        self.add_item(
            discord.ui.TextInput(
                label="Bio",
                style=discord.TextStyle.paragraph,
                placeholder="Digite sua nova bio...",
                default=current_bio,
                custom_id="bio"
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        new_bio = self.children[0].value
        db.cursor.execute("SELECT answers FROM responses WHERE user_id = ?", (str(interaction.user.id),))
        row = db.cursor.fetchone()
        answers = json.loads(row[0]) if row else {}
        answers["bio"] = new_bio
        db.cursor.execute("REPLACE INTO responses (user_id, answers) VALUES (?, ?)", (str(interaction.user.id), json.dumps(answers)))
        db.conn.commit()
        await interaction.response.send_message("Bio atualizada com sucesso!", ephemeral=True)

@bot.tree.command(name="edit_bio", description="Edita sua bio no perfil.")
async def edit_bio(interaction: discord.Interaction):
    db.cursor.execute("SELECT answers FROM responses WHERE user_id = ?", (str(interaction.user.id),))
    row = db.cursor.fetchone()
    current_bio = ""
    if row:
        answers = json.loads(row[0])
        current_bio = answers.get("bio", "")
    await interaction.response.send_modal(EditBioModal(current_bio))

class EditBdsmTestModal(discord.ui.Modal, title="Editar Resultados do BDSMTest"):
    def __init__(self, current_test_str):
        super().__init__()
        self.add_item(
            discord.ui.TextInput(
                label="Resultados do BDSMTest",
                style=discord.TextStyle.paragraph,
                placeholder="Ex: 70% Dominant\n50% Submissive",
                default=current_test_str,
                custom_id="bdsm_test"
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        new_test_input = self.children[0].value
        new_test_data = parse_bdsm_test(new_test_input)
        if not new_test_data:
            await interaction.response.send_message("Formato inválido para o BDSMTest!", ephemeral=True)
            return
        db.cursor.execute("REPLACE INTO bdsm_responses (user_id, test_data) VALUES (?, ?)", (str(interaction.user.id), json.dumps(new_test_data)))
        db.conn.commit()
        await interaction.response.send_message("Resultados do BDSMTest atualizados com sucesso!", ephemeral=True)

@bot.tree.command(name="edit_bdsm_test", description="Edita seus resultados do BDSMTest.")
async def edit_bdsm_test(interaction: discord.Interaction):
    db.cursor.execute("SELECT test_data FROM bdsm_responses WHERE user_id = ?", (str(interaction.user.id),))
    row = db.cursor.fetchone()
    current_test_str = ""
    if row:
        test_data = json.loads(row[0])
        lines = [f"{v}% {k}" for k, v in test_data.items()]
        current_test_str = "\n".join(lines)
    await interaction.response.send_modal(EditBdsmTestModal(current_test_str))

###############################
# Matchmaking e Perfil
###############################

class MatchmakingView(discord.ui.View):
    def __init__(self, origin: discord.Member, candidate_list: list):
        super().__init__(timeout=60)
        self.origin = origin
        self.candidate_list = candidate_list
        self.index = 0

    async def update_message(self, interaction: discord.Interaction):
        if self.index < len(self.candidate_list):
            candidate, score = self.candidate_list[self.index]
            embed = discord.Embed(
                title="Matchmaking",
                description=f"**Candidato:** {candidate.mention}\n**Compatibilidade:** {score:.2f}%",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(content="Nenhum match disponível!", embed=None, view=None)

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index >= len(self.candidate_list):
            return
        candidate, score = self.candidate_list[self.index]
        match_embed = discord.Embed(
            title="It's a Match!",
            description=f"{self.origin.mention} e {candidate.mention} se deram super bem!",
            color=discord.Color.purple()
        )
        match_embed.add_field(name="❤️❤️❤️", value="Que lindo match!", inline=False)
        await interaction.response.edit_message(embed=match_embed, view=None)
        for member in [self.origin, candidate]:
            try:
                await member.send(embed=match_embed)
            except Exception:
                pass

    @discord.ui.button(label="Negar", style=discord.ButtonStyle.red)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        await self.update_message(interaction)

@bot.tree.command(name="matchmake", description="Encontra o usuário mais compatível com você.")
async def matchmake(interaction: discord.Interaction):
    db.cursor.execute("SELECT answers FROM responses WHERE user_id = ?", (str(interaction.user.id),))
    row = db.cursor.fetchone()
    if not row:
        await interaction.response.send_message("Você ainda não registrou suas respostas gerais!", ephemeral=True)
        return
    user_answers = json.loads(row[0])
    questions = load_questions()
    db.cursor.execute("SELECT test_data FROM bdsm_responses WHERE user_id = ?", (str(interaction.user.id),))
    row_test = db.cursor.fetchone()
    user_test = json.loads(row_test[0]) if row_test else {}
    member_user = interaction.guild.get_member(interaction.user.id)
    if not member_user:
        await interaction.response.send_message("Não foi possível encontrar seus dados de membro.", ephemeral=True)
        return
    candidate_list = []
    db.cursor.execute("SELECT user_id, answers FROM responses")
    for user_id, answers_json in db.cursor.fetchall():
        if user_id == str(interaction.user.id):
            continue
        other_answers = json.loads(answers_json)
        db.cursor.execute("SELECT test_data FROM bdsm_responses WHERE user_id = ?", (user_id,))
        row_other = db.cursor.fetchone()
        other_test = json.loads(row_other[0]) if row_other else {}
        member_candidate = interaction.guild.get_member(int(user_id))
        if member_candidate:
            score = calc_total_match_full(user_answers, other_answers, questions, user_test, other_test, member_user, member_candidate)
            candidate_list.append((member_candidate, score))
    candidate_list.sort(key=lambda x: x[1], reverse=True)
    if candidate_list:
        candidate, score = candidate_list[0]
        embed = discord.Embed(
            title="Matchmaking",
            description=f"**Candidato:** {candidate.mention}\n**Compatibilidade:** {score:.2f}%",
            color=discord.Color.green()
        )
        view = MatchmakingView(member_user, candidate_list)
        await interaction.response.send_message(embed=embed, view=view)
    else:
        await interaction.response.send_message("Nenhum match encontrado!", ephemeral=True)

@bot.tree.command(name="search_match", description="Busca usuários com uma resposta específica para uma pergunta.")
@discord.app_commands.describe(key="Chave da pergunta", value="Valor da resposta")
async def search_match(interaction: discord.Interaction, key: str, value: str):
    matching_users = []
    db.cursor.execute("SELECT user_id, answers FROM responses")
    for user_id, answers_json in db.cursor.fetchall():
        answers = json.loads(answers_json)
        if answers.get(key, "").lower() == value.lower():
            matching_users.append(user_id)
    if matching_users:
        mentions = [bot.get_user(int(uid)).mention for uid in matching_users if bot.get_user(int(uid))]
        await interaction.response.send_message("Usuários encontrados: " + ", ".join(mentions), ephemeral=True)
    else:
        await interaction.response.send_message("Nenhum usuário encontrado com essa resposta.", ephemeral=True)

@bot.tree.command(name="perfil", description="Exibe o perfil do usuário com todas as informações registradas.")
@discord.app_commands.describe(usuario="Usuário para exibir o perfil (padrão: você mesmo)")
async def perfil(interaction: discord.Interaction, usuario: discord.Member = None):
    if usuario is None:
        usuario = interaction.user
    embed = discord.Embed(title=f"Perfil de {usuario.display_name}", color=discord.Color.blue())
    embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)
    embed.add_field(name="Nome", value=usuario.display_name, inline=True)
    embed.add_field(name="Tag", value=str(usuario), inline=True)
    db.cursor.execute("SELECT answers FROM responses WHERE user_id = ?", (str(usuario.id),))
    row = db.cursor.fetchone()
    if row:
        answers = json.loads(row[0])
        bio = answers.get("bio", "Bio não registrada.")
        respostas = "\n".join([f"**{k}**: {v}" for k, v in answers.items() if k != "bio"])
    else:
        bio = "Bio não registrada."
        respostas = "Nenhuma resposta registrada."
    embed.add_field(name="Bio", value=bio, inline=False)
    embed.add_field(name="Respostas Gerais", value=respostas, inline=False)
    db.cursor.execute("SELECT test_data FROM bdsm_responses WHERE user_id = ?", (str(usuario.id),))
    row_test = db.cursor.fetchone()
    if row_test:
        test_data = json.loads(row_test[0])
        resultados = "\n".join([f"- **{k}**: {v}%" for k, v in test_data.items()])
        embed.add_field(name="Resultados do BDSMTest", value=resultados, inline=False)
        embed.add_field(name="Data do Teste", value="Data não registrada", inline=True)
    else:
        embed.add_field(name="Resultados do BDSMTest", value="Teste não realizado.", inline=False)
    genders = []
    orientations = []
    for role in usuario.roles:
        db.cursor.execute("SELECT gender FROM gender_roles WHERE role_id = ?", (str(role.id),))
        row_gender = db.cursor.fetchone()
        if row_gender:
            genders.append(row_gender[0])
        db.cursor.execute("SELECT orientation FROM orientation_roles WHERE role_id = ?", (str(role.id),))
        row_orientation = db.cursor.fetchone()
        if row_orientation:
            orientations.append(row_orientation[0])
    gender_str = ", ".join(set(genders)) if genders else "Não registrado"
    orientation_str = ", ".join(set(orientations)) if orientations else "Não registrado"
    embed.add_field(name="Gênero", value=gender_str, inline=True)
    embed.add_field(name="Orientação Sexual", value=orientation_str, inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Executa o bot
bot.run("MTMzNTAxNTQ1MzYzMzk0MTY1OA.GQkc1k.ayJVkOd57NgPvIan5bxFaXDoO9WnyQbLJmf4Yo")
