import nextcord
from nextcord.ext import commands, tasks
import sqlite3
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")

# =========================
# 설정
# =========================

GUILD_ID = 1487065484913410119

STAFF_ROLE_ID = 1487065485009752233

TARGET_SCORE = 210

# =========================
# 봇 설정
# =========================

intents = nextcord.Intents.default()
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DB
# =========================

def db():
    return sqlite3.connect("performance.db")

def init_db():
    with db() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                user_id TEXT PRIMARY KEY,
                score INTEGER DEFAULT 0
            )
        """)

        conn.commit()

init_db()

# =========================
# 유저 생성
# =========================

def create_user(user_id):
    with db() as conn:
        c = conn.cursor()

        c.execute("""
            INSERT OR IGNORE INTO performance (user_id)
            VALUES (?)
        """, (str(user_id),))

        conn.commit()

# =========================
# 점수 추가
# =========================

def add_score(user_id, amount=1):
    with db() as conn:
        c = conn.cursor()

        create_user(user_id)

        c.execute("""
            UPDATE performance
            SET score = score + ?
            WHERE user_id=?
        """, (amount, str(user_id)))

        conn.commit()

# =========================
# 점수 가져오기
# =========================

def get_score(user_id):
    with db() as conn:
        c = conn.cursor()

        create_user(user_id)

        c.execute("""
            SELECT score FROM performance
            WHERE user_id=?
        """, (str(user_id),))

        return c.fetchone()[0]

# =========================
# 음성 점수 지급
# =========================

@tasks.loop(minutes=1)
async def voice_tracker():

    guild = bot.get_guild(GUILD_ID)

    if not guild:
        return

    role = guild.get_role(STAFF_ROLE_ID)

    for member in guild.members:

        if member.bot:
            continue

        if role not in member.roles:
            continue

        # 음성채널에 있는 경우
        if member.voice and member.voice.channel:
            add_score(member.id, 1)

# =========================
# 주간 초기화
# 매주 월요일 00:00
# =========================

@tasks.loop(minutes=1)
async def weekly_reset():

    now = datetime.datetime.now()

    # 월요일 00:00
    if now.weekday() == 0 and now.hour == 0 and now.minute == 0:

        with db() as conn:
            c = conn.cursor()

            c.execute("UPDATE performance SET score = 0")

            conn.commit()

        print("주간 실적 초기화 완료")

# =========================
# 내 실적
# =========================

@bot.slash_command(
    name="내실적",
    description="내 음성 실적 확인",
    guild_ids=[GUILD_ID]
)
async def my_performance(interaction: nextcord.Interaction):

    # 🔥 관리진 역할 확인
    role = interaction.guild.get_role(STAFF_ROLE_ID)

    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "❌ 해당 명령어 사용이 불가합니다.",
            ephemeral=True
        )
        return


    score = get_score(interaction.user.id)

    status = "✅ 실적 완료" if score >= TARGET_SCORE else "❌ 실적 미달"

    embed = nextcord.Embed(
        title="📊 내 음성 실적",
        color=0x00ff99
    )

    embed.add_field(
        name="현재 점수",
        value=f"{score}점",
        inline=False
    )

    embed.add_field(
        name="실적 상태",
        value=status,
        inline=False
    )

    embed.add_field(
        name="목표 점수",
        value=f"{TARGET_SCORE}점",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

# =========================
# 실적순위
# =========================

@bot.slash_command(
    name="실적순위",
    description="음성 실적 순위",
    guild_ids=[GUILD_ID]
)
async def performance_rank(interaction: nextcord.Interaction):

    await interaction.response.defer()

    guild = interaction.guild

    # 🔥 수정
    conn = sqlite3.connect("performance.db")
    c = conn.cursor()

    ranking_data = []

    for member in guild.members:

        if any(role.id == STAFF_ROLE_ID for role in member.roles):

            # 🔥 수정
            c.execute(
                "SELECT score FROM performance WHERE user_id=?",
                (str(member.id),)
            )

            row = c.fetchone()

            score = row[0] if row else 0

            ranking_data.append((member, score))

    conn.close()

    ranking_data.sort(key=lambda x: x[1], reverse=True)

    embed = nextcord.Embed(
        title="🏆 음성 실적 순위",
        color=0xffd700
    )

    if not ranking_data:
        embed.description = "관리진이 없습니다."

    else:
        for idx, (member, score) in enumerate(ranking_data, start=1):

            status = "✅ 완료" if score >= TARGET_SCORE else "❌ 미달"

            embed.add_field(
                name=f"{idx}위 - {member.display_name}",
                value=f"{score}점 | {status}",
                inline=False
            )

    await interaction.followup.send(embed=embed)
    
# =========================
# 실적미달
# =========================

@bot.slash_command(
    name="실적미달",
    description="실적 미달자 목록",
    guild_ids=[GUILD_ID]
)
async def performance_fail(interaction: nextcord.Interaction):

    await interaction.response.defer()

    guild = interaction.guild

    # 🔥 수정
    conn = sqlite3.connect("performance.db")
    c = conn.cursor()

    failed_members = []

    for member in guild.members:

        if any(role.id == STAFF_ROLE_ID for role in member.roles):

            # 🔥 수정
            c.execute(
                "SELECT score FROM performance WHERE user_id=?",
                (str(member.id),)
            )

            row = c.fetchone()

            score = row[0] if row else 0

            if score < TARGET_SCORE:
                failed_members.append((member, score))

    conn.close()

    embed = nextcord.Embed(
        title="❌ 실적 미달자 목록",
        color=0xff4444
    )

    if not failed_members:
        embed.description = "모든 관리진이 실적을 달성했습니다."

    else:
        for member, score in failed_members:

            remain = TARGET_SCORE - score

            embed.add_field(
                name=member.display_name,
                value=f"{score}점\n부족 점수 : {remain}점",
                inline=False
            )

    await interaction.followup.send(embed=embed)
# =========================
# 준비 완료
# =========================

@bot.event
async def on_ready():

    print(f"로그인 완료: {bot.user}")

    if not voice_tracker.is_running():
        voice_tracker.start()

    if not weekly_reset.is_running():
        weekly_reset.start()

# =========================
# 실행
# =========================
bot.run(TOKEN)

