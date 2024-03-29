import discord
import datetime
import time
import json
import math
from discord.ext import commands


with open("./token.txt") as f:
    TOKEN = f.readline()

bot = commands.Bot(command_prefix=".")
bot.remove_command("help")

save_file = "./data.json"
string_file = "./strings.json"

count_guilds = {}
PREV_SAVE = time.time()
SAVE_DEL = 10
DOWNTIME = -1
DISCONNECT = 0

def reload_strings():
    global MSGS, NAMES, ERRORS, CHARS, MSFREQ
    global presence, MASTER_ROLE
    with open(string_file) as f:
        data = json.load(f)
    MSGS = data["messages"]
    NAMES = data["names"]
    ERRORS = data["errors"]
    CHARS = data["chars"]
    MSFREQ = data["milestone_freq"]
    MASTER_ROLE = data["master_role"]
    for k in MSGS:
        MSGS[k] = "".join(MSGS[k])
    
    presence = discord.Game(name=data["status"])

reload_strings()


def log_miscount(message):
    line = f"{time.ctime()} [{message.channel.guild.name}] #{message.channel.name} "
    line += f'{message.author.mention} "{message.content}"\n'
    with open("./log.txt", "ab") as f:
        f.write(line.encode())


class Parse:
    def roman(x):
        """Original by @Kantoros1#4862, modified"""
        inp = x
        numerals = {"I":1, "V":5, "X":10, "L":50, "C":100, "D":500, "M":1000}
        
        num = list(inp.upper().replace('__','_'))
        Thousands = False

        for i in range(len(num)):
            if num[i] in numerals:
                num[i] = numerals[num[i]]
            elif num[i] != "_":
                return False
            if num[i] == '_':
                Thousands = not Thousands
            elif Thousands:
                num[i] *= 1000
        
        num = list(filter(lambda a:a != '_',num))
        
        result = 0
        while len(num)>0:
            if num[0] < max(num):
                result -= num[0]
            else:
                result += num[0]
            num.pop(0)
        return result

    def int(x):
        try:
            return int(x)
        except ValueError:
            return False

    def bin(x):
        try:
            return int(x, 2)
        except ValueError:
            return False

class Ctypes:
    def inc(old, new):
        return new == old+1
    
    def dec(old, new):
        return new == old-1
    
    def sqr(old, new):
        s = math.sqrt(new)
        return s == math.sqrt(old) + 1

def cutoff(content, chars="0123456789 "):# cut off message after number ends
    out = ""
    for c in content:
        if c not in chars:
            break
        out += c if c != " " else ""
    return out

## p n r b s

CHECKS = {"p":Ctypes.inc, "n":Ctypes.dec, "r":Ctypes.inc,
          "b":Ctypes.inc, "s":Ctypes.sqr}

PARSERS = {"p":Parse.int, "n":Parse.int, "r":Parse.roman,
         "b":Parse.bin, "s":Parse.int}

class Cchannel:
    def __init__(self, channel, ctype):
        """(Channel object, "p")"""
        self.channel = channel
        self.name = channel.name
        self.ctype = ctype
        self.progress = 0
        self.prev = "<prev_user>"

        self.check = CHECKS[ctype]
        self.parse = PARSERS[ctype]

    def try_count(self, txt):
        num = self.parse(cutoff(txt, CHARS[self.ctype]))
        c = self.check(self.progress, num)
        if c:
            self.progress = num
            return True
        return False

    def save(self):
        data = {"progress":self.progress,
                "prev":self.prev}
        return data


def milestr(info):
    value, t, user, prev = info
    date = datetime.date.today()
    datestr = f"{date.day}/{date.month} - {date.year}"
    message = MSGS["milestone"].replace("CHANNEL", NAMES[t]) % value
    message = message.replace("USER", user).replace("PREV", prev)
    message = message.replace("DATE", datestr)
    return message

class CountGuild:
    def __init__(self, guild):
        self.guild = guild
        self.bot_channel = None
        self.milestone_main = None
        self.milestone_extra = None
        
        self.channels = {t:None for t in PARSERS}
        
        for channel in guild.channels:
            if channel.name == "bot":
                self.bot_channel = channel
            elif channel.name == "milestones":
                self.milestone_main = channel
            elif channel.name == "milestones-extra":
                self.milestone_extra = channel
            else:
                for t in self.channels:
                    if NAMES[t] == channel.name:
                        self.channels[t] = Cchannel(channel, t)
        
        if self.bot_channel == None:
            print(f"<{guild.name}> Couldn't find channel 'bot'.")
        if self.milestone_main == None:
            print(f"<{guild.name}> Couldn't find channel 'milestones'.")
        if self.milestone_extra == None:
            print(f"<{guild.name}> Couldn't find channel 'milestones-extra'.")
        for channel in self.channels:
            if self.channels[channel] == None:
                print(f"<{guild.name}> Couldn't find channel '{NAMES[channel]}'")

    def load(self, data):
        for c in self.channels:
            if data[c]:
                self.channels[c].progress = data[c]["progress"]
                self.channels[c].prev = data[c]["prev"]

    def save_str(self):
        data = {}
        for c in self.channels:
            if self.channels[c]:
                data[c] = self.channels[c].save()
            else:
                data[c] = None
        return data

    def try_count(self, message):
        """Should only be called if in an actual count channel"""
        #returns True if message should stay
        ctype = ""
        for c in self.channels:
            if self.channels[c].channel.id == message.channel.id:
                ctype = c
                break
        if not ctype:# not a count channel, shouldn't actually happen
            return True# don't want to delete if not in a count channel

        cch = self.channels[ctype]
        
        if message.author.mention == cch.prev:
            return False
        counted = cch.try_count(message.content)

        if counted:
            old = cch.prev
            cch.prev = message.author.mention
            if abs(cch.progress) % MSFREQ[ctype] == 0:
                return (True, cch.progress, ctype, cch.prev, old)
            
            return True
        return False


async def is_master(user):
    own = await bot.is_owner(user)
    if own:
        return True
    for role in user.roles:
        if role.name.lower() == MASTER_ROLE:
            return True
    return False

def load():
    try:
        with open(save_file) as f:
            alldata = json.load(f)
    except FileNotFoundError:
        save()
        with open(save_file) as f:
            alldata = json.load(f)
    for gldid in alldata:
        data = alldata[gldid]
        
        for gld in count_guilds:
            if str(gld.id) == gldid:
                count_guilds[gld].load(data)
                break
        else:
            print(f"Unused guild: {gldid} in save file")
    print("Loaded counting data")
    
def save():
    data = {}
    for gld in count_guilds:
        data[gld.id] = count_guilds[gld].save_str()
    
    with open(save_file, "w") as fp:
        json.dump(data, fp)

    PREV_SAVE = time.ctime()

@bot.event
async def on_message(message):
    if message.author == bot.user or type(message.channel) == discord.DMChannel:
        return
    gld = count_guilds[message.channel.guild]
    
    if message.channel in [i.channel if i else None for i in gld.channels.values()]:
        counted = gld.try_count(message)
        if not counted:
            log_miscount(message)
            await message.delete()
            return
        if type(counted) == tuple:
            if counted[2] == "p":
                if gld.milestone_main:
                    await gld.milestone_main.send(milestr(counted[1:]))
            else:
                if gld.milestone_extra:
                    await gld.milestone_extra.send(milestr(counted[1:]))
        if time.time() - PREV_SAVE >= SAVE_DEL:
            save()
        
    if message.channel == gld.bot_channel:
        await bot.process_commands(message)

@bot.command(name="find")
async def find_mistakes(ctx, t="p", limit=None):
    gld = count_guilds[ctx.guild]
    
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    
    if t not in gld.channels or gld.channels[t] == None:
        await gld.bot_channel.send(ERRORS["type"])
        return
    
    await ctx.send(f"`Scanning for errors in #{NAMES[t]}`")
    #TODO remember a safe point to not look through all messages
    #TODO ignore messages with a certain reaction OR allow for whitelisting messages
    lim = Parse.int(limit)
    lim = lim if lim else None# False -> None
    history = await gld.channels[t].channel.history(limit=lim).flatten()
    history.reverse()
    
    new = history[0].content
    old = PARSERS[t](cutoff(new, CHARS[t]))

    for msg in history[1:]:
        new = PARSERS[t](cutoff(msg.content, CHARS[t]))
        if not CHECKS[t](old, new):
            await ctx.send(f"`Located miscount or invalid number around {old} - {new}`")
        if new:
            old = new
    await ctx.send("`Done checking for errors.`")

@bot.command(name="set")
async def setcount(ctx, t="p", amount="42"):
    gld = count_guilds[ctx.guild]
    if t not in gld.channels:
        await gld.bot_channel.send(ERRORS["type"])
        return
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    
    n = Parse.int(amount)
    
    if not n:
        await ctx.send(ERRORS["num"])
        return
    gld.channels[t].progress = n
    save()
    await ctx.send(f"`#{NAMES[t]} progress is now {n}`")

@bot.command(name="count")
async def getcount(ctx, t="c"):
    gld = count_guilds[ctx.guild]
    if t not in gld.channels or gld.channels[t] == None:
        await gld.bot_channel.send(ERRORS["type"])
        return
    await gld.bot_channel.send(f"`#{NAMES[t]} progress is {gld.channels[t].progress}`")

@bot.command(name="convert")
async def convert(ctx, t, val):
    gld = count_guilds[ctx.guild]
    if t not in gld.channels or gld.channels[t] == None:
        await gld.bot_channel.send(ERRORS["type"])
        return
    await gld.bot_channel.send(f"`{PARSERS[t](val)}`")

@bot.command(name="help")
async def h(ctx):
    await ctx.send(MSGS["help"])

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("```pong```")

@bot.command(name="credits")
async def cred(ctx):
    img = discord.File("./cat.png")
    await ctx.send(MSGS["credits"], file=img)

@bot.command(name="alephnull")
async def kill_bot(ctx):
    if await is_master(ctx.author):
        print(f"Closed by {ctx.author.name}#{ctx.author.discriminator} in guild: {ctx.guild.name}")
        save()
        for guild in bot.guilds:
            gld = count_guilds[guild]
            if gld.bot_channel != None:
                await gld.bot_channel.send(MSGS["shutdown"])
        ownid = "<@" + str(bot.owner_id) + ">"
        if ctx.author.mention != ownid:
            await ctx.send(MSGS["shutdown_ping"].replace("OWNER", ownid))
        await bot.close()
    else:
        print(f"{ctx.author.name}#{ctx.author.discriminator} tried to kill the bot")
        await ctx.send(ERRORS["perm"])

@bot.command(name="save")
async def manual_save(ctx):
    gld = count_guilds[ctx.guild]
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    save()
    await ctx.send(MSGS["saved"])

@bot.command(name="milestone")
async def manual_milestone(ctx, value, t, user, prev):
    gld = count_guilds[ctx.guild]
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    
    n = Parse.int(value)
    
    if not n:
        await ctx.send(ERRORS["num"])
        return
    if t not in gld.channels:
        await gld.bot_channel.send(ERRORS["type"])
        return

    data = (n, t, user, prev)
    if t == "p":
        if gld.milestone_main:
            await gld.milestone_main.send(milestr(data))
    else:
        if gld.milestone_extra:
            await gld.milestone_extra.send(milestr(data))

@bot.command(name="log")
async def getlog(ctx):
    file = discord.File("./log.txt")
    await ctx.send(MSGS["getlog"], file=file)

@bot.command(name="reload")
async def reload(ctx):
    reload_strings()
    await bot.change_presence(activity=presence)
    await ctx.send(MSGS["reload"])

@bot.command(name="resetusers")
async def reset_last_counter(ctx):
    #globally
    if not await is_master(ctx.author):
        await ctx.send(ERRORS["perm"])
        return
    for cg in count_guilds:
        for ctype in count_guilds[cg].channels:
            if count_guilds[cg].channels[ctype] != None:
                count_guilds[cg].channels[ctype].prev = "<prev_user>"
    await ctx.send(MSGS["reset_users"])

def join_msg(gld):
    if DOWNTIME == -1:
        join = MSGS["join"]
    else:
        join = MSGS["rejoin"] % DOWNTIME
    for ctype in gld.channels:
        if gld.channels[ctype]:
            join += MSGS["progress"].replace("CHANNEL",NAMES[ctype])%gld.channels[ctype].progress
    join += MSGS["join_end"]
    return join

@bot.event
async def on_ready():
    print(f"CONNECTED\n{time.ctime()}\nLogged in as {bot.user.name}")
    await bot.change_presence(activity=presence)

    print("Guilds:")
    for guild in bot.guilds:
        print(guild.name)
        count_guilds[guild] = CountGuild(guild)
    print("-----")
    load()
    for guild in count_guilds:
        gld = count_guilds[guild]
        
        if gld.bot_channel != None:#alert that the bot has joined
            await gld.bot_channel.send(join_msg(gld))
            
            for c in gld.channels:
                if gld.channels[c] == None:
                    await gld.bot_channel.send(MSGS["channel_missing"] % NAMES[c])

@bot.event
async def on_connect():
    global DOWNTIME
    if DOWNTIME != -1:
        DOWNTIME = time.ctime() - DISCONNECT
        print(f"reconnected after {DOWNTIME} seconds")

@bot.event
async def on_disconnect():
    global DISCONNECT
    DISCONNECT = time.ctime()
    print(f"Disconnected on {DISCONNECT}")
    save()

print("Starting bot")
bot.run(TOKEN)
