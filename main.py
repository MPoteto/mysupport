TOKEN = ""

import disnake, sqlite3
from disnake.ext import commands
from disnake import TextInputStyle
import asyncio

db=sqlite3.connect("database.db")
sql=db.cursor()

sql.execute("""CREATE TABLE IF NOT EXISTS guilds (
    guild_id BIGINT,
    category_id BIGINT,
    role_id BIGINT
)""")
sql.execute("""CREATE TABLE IF NOT EXISTS support (
    channel_id BIGINT,
    guild_id BIGINT,
    user_id BIGINT,
    what TEXT,
    messages TEXT
)""")

db.commit()

bot = commands.Bot(command_prefix=".", intents=disnake.Intents().all())


@bot.event
async def on_ready():
    print("The bot is ready!")
    while True:
        await bot.change_presence(activity=disnake.Game(name=f'{len(bot.guilds)} серверов'))
        await asyncio.sleep(5)
        supports=0
        for x in sql.execute("SELECT * FROM support"): supports += 1
        await bot.change_presence(activity=disnake.Game(name=f'{supports} каналов открыто'))
        await asyncio.sleep(5)
        
@bot.event
async def on_guild_join(guild):
    sql.execute(f"INSERT INTO guilds VALUES ({guild.id}, 0, 0)")
    db.commit()

@bot.event
async def on_guild_leave(guild):
    sql.execute(f"DELETE FROM guilds WHERE guild_id = {guild.id}")
    db.commit()

# Subclassing the modal.
class MyModal(disnake.ui.Modal):
    def __init__(self):
        # The details of the modal, and its components
        components = [
            disnake.ui.TextInput(
                label="Ваше Имя",
                placeholder="Олег",
                custom_id="name",
                style=TextInputStyle.short,
                max_length=50,
            ),
            disnake.ui.TextInput(
                label="Что произошло?",
                placeholder="У меня взорвалась собака....",
                custom_id="description",
                style=TextInputStyle.paragraph,
            ),
        ]
        super().__init__(title="Создание помощи", components=components)

    # The callback received when the user input is completed.
    async def callback(self, inter: disnake.ModalInteraction):
        sql.execute(f"SELECT * FROM support WHERE user_id = {inter.user.id} AND guild_id = {inter.guild.id}")
        if sql.fetchone():
            try:
                await inter.user.send("У вас уже существует канал помощи!")
                
            except:
                pass
            return
        for x in sql.execute(f"SELECT * FROM guilds WHERE guild_id = {inter.guild.id}"):
            overwrites = {
                inter.guild.default_role: disnake.PermissionOverwrite(view_channel=False), 
                inter.user: disnake.PermissionOverwrite(view_channel=True), # give perm for user
                inter.guild.get_role(x[2]): disnake.PermissionOverwrite(view_channel=True) # give perm for support role
            }
            ch=await inter.guild.create_text_channel(f"support-{inter.user.name}", overwrites=overwrites, category=inter.guild.get_channel(x[1])) # channel creating
        
        embed = disnake.Embed(title="Запрос помощи!")
        for key, value in inter.text_values.items():
            embed.add_field(
                name=key.capitalize().replace("Name", "Имя").replace("Description", "Что произошло?"),
                value=value[:1024],
                inline=False,
            )
            
        for x in sql.execute(f"SELECT * FROM guilds WHERE guild_id = {inter.guild.id}"):
            await ch.send(content=f"{inter.user.mention} {inter.guild.get_role(x[2]).mention}", embed=embed,
            components=[
               disnake.ui.Button(label="Закрыть", emoji="❌", style=disnake.ButtonStyle.danger, custom_id="close")
        ])
        sql.execute("INSERT INTO support VALUES (?, ?, ?, ?, '')", (ch.id, inter.guild.id, inter.user.id, list(inter.text_values.items())[1][1]))
        db.commit()

@bot.event
async def on_message(message):
    
    sql.execute(f"SELECT * FROM support WHERE channel_id = {message.channel.id}")
    if sql.fetchone():
        for x in sql.execute(f"SELECT * FROM support WHERE channel_id = {message.channel.id}"):
            formatted_msg = f"{message.author}: {message.content}ymakenow"
            sql.execute(f"UPDATE support SET messages = '{x[3] + formatted_msg}' WHERE channel_id = {message.channel.id}")
            db.commit()

    await bot.process_commands(message)


@bot.slash_command(name="setup")
async def setup(ctx, support_role: disnake.Role):
    category=await ctx.guild.create_category("помощь")
    
    embed=disnake.Embed(title="Запрос Помощи", description="Нужна помощь? Обратитесь сюда!")
    ch=await category.create_text_channel("Запрос")
    
    # update data
    sql.execute(f"UPDATE guilds SET category_id = {category.id} WHERE guild_id = {ctx.guild.id}")
    sql.execute(f"UPDATE guilds SET role_id = {support_role.id} WHERE guild_id = {ctx.guild.id}")
    db.commit()

    overwrites = {
        ctx.guild.default_role: disnake.PermissionOverwrite(send_messages=False)
    }
    await ch.edit(overwrites=overwrites)
    await ch.send(embed=embed,
        components=[
            disnake.ui.Button(label="Создать", emoji="✉", style=disnake.ButtonStyle.primary, custom_id="create")
        ])
    await ctx.send("Успешно")
@bot.listen("on_button_click")
async def help_listener(inter: disnake.MessageInteraction):
    if inter.component.custom_id == "create":
        await inter.response.send_modal(modal=MyModal())
    if inter.component.custom_id == "close":
        await inter.response.send_message("Вы действительно хотите закрыть?",
                                                  components=[
            disnake.ui.Button(label="Подтердить", emoji="❌", style=disnake.ButtonStyle.danger, custom_id="close_confirm")
        ])
    if inter.component.custom_id == "close_confirm":
        await inter.channel.delete()
        for x in sql.execute(f"SELECT * FROM support WHERE channel_id = {inter.channel.id}"):
            member=inter.guild.get_member(x[2])
            msgs = ""
            for i in x[4].split("ymakenow"):
                msgs = f"{msgs}\n{i}"
            try:
                await member.send(f"Канал помощи закрыт!\nСообщения:\n\n```{msgs}```")
            except:
                pass
            if member.id != inter.user.id:
                try:
                    await inter.user.send(f"Канал помощи закрыт!\nСообщения:\n\n```{msgs}```")
                except:
                    pass
            sql.execute(f"DELETE FROM support WHERE channel_id = {inter.channel.id}")
            db.commit()
bot.run(TOKEN)