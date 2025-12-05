import discord
from discord.ext import commands
import asyncio
import os
from flask import Flask
from threading import Thread

# สร้าง Web Server สำหรับ Replit
app = Flask('')

@app.route('/')
def home():
    return "🤖 Discord Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# สร้างบอทด้วย Prefix
bot = commands.Bot(command_prefix='!', intents=intents)

# เก็บข้อมูล sticky messages
# Format: { channel_id: {'content': 'ข้อความ', 'last_message_id': id, 'active': True, 'processing': False} }
sticky_messages = {}

# ตัวแปรควบคุมการส่งข้อความ
STICKY_DELAY = 2  # รอ 2 วินาทีหลังข้อความล่าสุดก่อนส่ง sticky ใหม่


# ฟังก์ชันส่งข้อความ sticky
async def send_sticky_message(channel, channel_id):
    """ส่งข้อความ sticky และลบข้อความเก่า"""
    try:
        sticky_data = sticky_messages[channel_id]

        # ป้องกันการส่งซ้ำซ้อน
        if sticky_data.get('processing', False):
            return

        sticky_data['processing'] = True

        # รอให้ข้อความหยุดไหลก่อน
        await asyncio.sleep(STICKY_DELAY)

        # ลบข้อความเก่า
        if sticky_data['last_message_id']:
            try:
                old_message = await channel.fetch_message(sticky_data['last_message_id'])
                await old_message.delete()
            except discord.NotFound:
                pass  # ข้อความถูกลบไปแล้ว
            except discord.HTTPException as e:
                print(f'❌ ไม่สามารถลบข้อความเก่า: {e}')

        # ส่งข้อความใหม่
        new_message = await channel.send(sticky_data['content'])
        sticky_data['last_message_id'] = new_message.id
        sticky_data['processing'] = False

    except discord.HTTPException as e:
        print(f'❌ ไม่สามารถส่งข้อความ: {e}')
        if channel_id in sticky_messages:
            sticky_messages[channel_id]['processing'] = False
    except KeyError as e:
        print(f'❌ ไม่พบข้อมูล sticky message: {e}')


@bot.event
async def on_ready():
    """เมื่อบอทพร้อมใช้งาน"""
    print(f'✅ บอทออนไลน์แล้ว: {bot.user.name}')
    print(f'📊 อยู่ใน {len(bot.guilds)} เซิร์ฟเวอร์')
    print('━━━━━━━━━━━━━━━━━━━━━━━━')


@bot.event
async def on_message(message):
    """เมื่อมีข้อความใหม่"""
    # ไม่ตอบสนองกับบอท
    if message.author.bot:
        return

    channel_id = message.channel.id

    # ตรวจสอบและส่ง sticky message
    if channel_id in sticky_messages:
        sticky_data = sticky_messages[channel_id]

        if sticky_data['active'] and not sticky_data.get('processing', False):
            # ยกเลิก task เดิม (ถ้ามี)
            if 'task' in sticky_data and sticky_data['task']:
                sticky_data['task'].cancel()

            # สร้าง task ใหม่
            sticky_data['task'] = asyncio.create_task(
                send_sticky_message(message.channel, channel_id)
            )

    # ประมวลผลคำสั่ง
    await bot.process_commands(message)


@bot.command(name='stick')
@commands.has_permissions(manage_messages=True)
async def stick(ctx, *, content: str):
    """สร้าง sticky message"""
    channel_id = ctx.channel.id

    # บันทึกข้อมูล
    sticky_messages[channel_id] = {
        'content': content,
        'last_message_id': None,
        'active': True,
        'processing': False,
        'task': None
    }

    # ส่งข้อความแรก
    await send_sticky_message(ctx.channel, channel_id)

    # ส่งข้อความยืนยัน
    confirm = await ctx.send('✅ ตั้งค่า sticky message เรียบร้อยแล้ว!')

    # ลบข้อความคำสั่งและยืนยันหลัง 3 วินาที
    await asyncio.sleep(3)
    try:
        await ctx.message.delete()
        await confirm.delete()
    except discord.NotFound:
        pass  # ข้อความถูกลบไปแล้ว
    except discord.Forbidden:
        pass  # ไม่มีสิทธิ์ลบข้อความ
    except discord.HTTPException as e:
        print(f'❌ ไม่สามารถลบข้อความ: {e}')


@bot.command(name='stickstop')
@commands.has_permissions(manage_messages=True)
async def stickstop(ctx):
    """หยุด sticky message ชั่วคราว"""
    channel_id = ctx.channel.id

    if channel_id not in sticky_messages:
        await ctx.send('❌ ช่องนี้ไม่มี sticky message')
        return

    sticky_data = sticky_messages[channel_id]
    sticky_data['active'] = False

    # ลบข้อความ sticky ที่มีอยู่
    if sticky_data['last_message_id']:
        try:
            old_message = await ctx.channel.fetch_message(sticky_data['last_message_id'])
            await old_message.delete()
        except discord.NotFound:
            pass  # ข้อความถูกลบไปแล้ว
        except discord.Forbidden:
            pass  # ไม่มีสิทธิ์ลบข้อความ
        except discord.HTTPException as e:
            print(f'❌ ไม่สามารถลบข้อความ: {e}')

    await ctx.send('⏸️ หยุด sticky message ชั่วคราวแล้ว (ใช้ `!stickstart` เพื่อเริ่มอีกครั้ง)')


@bot.command(name='stickstart')
@commands.has_permissions(manage_messages=True)
async def stickstart(ctx):
    """เริ่ม sticky message อีกครั้ง"""
    channel_id = ctx.channel.id

    if channel_id not in sticky_messages:
        await ctx.send('❌ ช่องนี้ไม่มี sticky message')
        return

    sticky_data = sticky_messages[channel_id]
    sticky_data['active'] = True

    await send_sticky_message(ctx.channel, channel_id)
    await ctx.send('▶️ เริ่ม sticky message อีกครั้งแล้ว!')


@bot.command(name='stickremove')
@commands.has_permissions(manage_messages=True)
async def stickremove(ctx):
    """ลบ sticky message ถาวร"""
    channel_id = ctx.channel.id

    if channel_id not in sticky_messages:
        await ctx.send('❌ ช่องนี้ไม่มี sticky message')
        return

    sticky_data = sticky_messages[channel_id]

    # ลบข้อความ sticky
    if sticky_data['last_message_id']:
        try:
            old_message = await ctx.channel.fetch_message(sticky_data['last_message_id'])
            await old_message.delete()
        except discord.NotFound:
            pass  # ข้อความถูกลบไปแล้ว
        except discord.Forbidden:
            pass  # ไม่มีสิทธิ์ลบข้อความ
        except discord.HTTPException as e:
            print(f'❌ ไม่สามารถลบข้อความ: {e}')

    del sticky_messages[channel_id]
    await ctx.send('🗑️ ลบ sticky message เรียบร้อยแล้ว!')


@bot.command(name='stickinfo')
@commands.has_permissions(manage_messages=True)
async def stickinfo(ctx):
    """ดูข้อมูล sticky message"""
    channel_id = ctx.channel.id

    if channel_id not in sticky_messages:
        await ctx.send('❌ ช่องนี้ไม่มี sticky message')
        return

    sticky_data = sticky_messages[channel_id]

    # สร้าง Embed
    embed = discord.Embed(
        title='📌 ข้อมูล Sticky Message',
        color=discord.Color.blue(),
        timestamp=ctx.message.created_at
    )

    status = '✅ เปิดใช้งาน' if sticky_data['active'] else '⏸️ หยุดชั่วคราว'
    embed.add_field(name='สถานะ', value=status, inline=False)
    embed.add_field(name='ข้อความ', value=sticky_data['content'], inline=False)

    await ctx.send(embed=embed)


# กำหนด help command แบบกำหนดเอง
bot.remove_command('help')


@bot.command(name='help')
async def help_command(ctx):
    """แสดงคำสั่งทั้งหมด"""
    embed = discord.Embed(
        title='📖 คำสั่งบอท Sticky Message',
        description='คำสั่งทั้งหมดของบอท (ต้องมีสิทธิ์ Manage Messages)',
        color=discord.Color.green()
    )

    embed.add_field(
        name='`!stick <ข้อความ>`',
        value='สร้าง sticky message ในช่องนี้',
        inline=False
    )
    embed.add_field(
        name='`!stickstop`',
        value='หยุด sticky message ชั่วคราว',
        inline=False
    )
    embed.add_field(
        name='`!stickstart`',
        value='เริ่ม sticky message อีกครั้ง',
        inline=False
    )
    embed.add_field(
        name='`!stickremove`',
        value='ลบ sticky message ถาวร',
        inline=False
    )
    embed.add_field(
        name='`!stickinfo`',
        value='ดูข้อมูล sticky message ในช่องนี้',
        inline=False
    )
    embed.add_field(
        name='`!help`',
        value='แสดงคำสั่งทั้งหมด',
        inline=False
    )

    embed.set_footer(text='Sticky Bot - ไม่จำกัดจำนวนช่อง!')
    embed.timestamp = ctx.message.created_at

    await ctx.send(embed=embed)


# จัดการ Error
@stick.error
@stickstop.error
@stickstart.error
@stickremove.error
@stickinfo.error
async def permission_error(ctx, error):
    """จัดการ error เมื่อไม่มีสิทธิ์"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('❌ คุณต้องมีสิทธิ์ **Manage Messages** เพื่อใช้คำสั่งนี้')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('❌ กรุณาระบุข้อความที่ต้องการ sticky\nตัวอย่าง: `!stick ยินดีต้อนรับสู่เซิร์ฟเวอร์!`')


# รันบอท - ใช้ Environment Variable
if __name__ == '__main__':
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print('❌ ไม่พบ DISCORD_TOKEN! กรุณาตั้งค่า Environment Variable')
        exit(1)
    
    # ⚡ เปิด Web Server ก่อนรันบอท (สำคัญมาก!)
    print('🌐 กำลังเปิด Web Server...')
    keep_alive()
    
    print('🤖 กำลังเชื่อมต่อบอท...')
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print('❌ Token ไม่ถูกต้อง! กรุณาตรวจสอบ Token')
    except Exception as e:
        print(f'❌ เกิดข้อผิดพลาด: {e}')
