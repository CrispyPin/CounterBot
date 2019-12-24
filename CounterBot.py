import discord
import datetime
import time
from discord.ext import commands

with open("token.txt") as f:
    TOKEN = f.readline()

bot = commands.Bot(command_prefix=".")
bot.remove_command("help")

save_file = "./count_info.txt"
presence = discord.Game(name="with numbers | .help")

count_guilds = {}

channel_error = "```css\n[Error] Couldn't find channel "
join_msg = """```ini
[CounterBot 2.0 has connected.] Type .help for a list of commands."""
shutdown_msg = "```ini\n[CounterBot has been deactivated] Cannot count beyond Aleph-null```"
help_text = """```ini
-[List of commands]-``````css
.help     : show this list
.count {t}: show counting progress of type t
.credits  : show info on who made this possible
[Admin commands]
.set {t} {x} : manually set the count progress of type t to x
.find {t} {L}: looks for errors in channel t. looks back to L if specified, else to start
.save        : saves all counting info
.alephnull   : terminate CounterBot
[Argument types]
x = a number
L = limit
t = type of counting
[Values for t]
c = regular counting
b = backwards counting
r = roman numerals counting
```"""
credit_text = """```
CounterBot made by: @CrispyPin#1149
Contributer:        @Kantoros1#4862
Moral support:      Pingu
```"""

numerals = {"I":1, "V":5, "X":10, "L":50, "C":100, "D":500, "M":1000}

## from @Kantoros1#4862, modified
def Latinize(inp):
    num = list(inp.upper().replace('__','_'))
    Thousands = False

    for i in range(len(num)):
        if num[i] in numerals:
            num[i] = numerals[num[i]]
        elif num[i] != "_":
            return "Invalid"
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

class Cchannel:
    def __init__(self, channel, ctype):
        pass

channel_names = {"c":"counting", "b":"counting-backwards", "r":"roman-numerals"}
count_valid = {"c":"new == old+1", "b":"new == old-1", "r":"new == old+1"}# expression saying if new is valid
eval_num = {"c":"to_num(new)", "b":"to_num(new)", "r":"Latinize(new)"}# raw input -> integer

def milestr(value, t, user, prev):
    date = datetime.date.today()
    datestr = f"{date.day}/{date.month} - {date.year}"
    return f"`Milestone reached: {value} in` #{channel_names[t]} `by:` {user}`, with help from` {prev} `on {datestr}`"

class CountGuild:
    def __init__(self, guild):
        self.guild = guild
        self.bot_channel = None
        self.milestone_channel = None
        
        self.counts = {"c":0, "b":0, "r":0}
        self.latest = {"c":"Invalid", "b":"Invalid", "r":"Invalid"}
        self.milestones = {"c":[], "b":[], "r":[]}
        self.channels = {"c":None, "b":None, "r":None}
        
        for channel in guild.channels:
            if channel.name == "bot":
                self.bot_channel = channel
            elif channel.name == "milestones":
                self.milestone_channel = channel
            else:
                for c in self.channels:
                    if channel_names[c] == channel.name:
                        self.channels[c] = channel
        if self.bot_channel == None:
            print(f"<{guild.name}> Couldn't find channel 'bot'.")
        if self.milestone_channel == None:
            print(f"<{guild.name}> Couldn't find channel 'milestones'.")
        for channel in self.channels:
            if self.channels[channel] == None:
                print(f"<{guild.name}> Couldn't find channel '{channel_names[channel]}'")

    def save_str(self):
        data = self.guild.name + "\n"
        for count in self.counts:
            data += f"{self.counts[count]}\n"
        for counter in self.latest:
            data += f"{self.latest[counter]}\n"
        for ms in self.milestones:
            data += f"{self.milestones[ms]}\n"
        return data

    def try_count(self, message):
        """Should only be called if in an actual count channel"""
        #returns True if message should stay
        ctype = ""
        for c in self.channels:
            if self.channels[c] == message.channel:
                ctype = c
                break
        if not ctype:# not a count channel, shouldn't actually happen
            return True# don't want to delete if not in a count channel

        if message.author.mention == self.latest[ctype]:
            return False
        new = message.content.split()[0]
        new = eval(eval_num[ctype])
        old = self.counts[ctype]
        
        if eval(count_valid[ctype]):
            self.counts[ctype] = new
            ms = self.ms_update(ctype, message.author.mention)
            self.latest[ctype] = message.author.mention
            return [True,ms]
        return False

    def ms_update(self, t, user):
        if self.counts[t] % 1000 != 0:
            return False
        self.milestones[t].append(self.counts[t])
        return milestr(self.counts[t], t, user, self.latest[t])

def is_master(user):
    if user.mention == "<@316553438186045441>":
        return True
    for role in user.roles:
        if role.name == "Count Master":
            return True
    return False

def to_num(x):
    try:
        return int(x)
    except Exception:
        return "Invalid"

def load():
    with open(save_file)as f:
        alldata = f.read().split("\n\n")
    for gld_data in alldata:
        data = gld_data.split("\n")
        name = data[0]
        for gld in count_guilds:
            if gld.name == name:
                guild = count_guilds[gld]
                break
        else:
            print(f"Unused guild: {name} in save file")
            continue
        line = 1
        for c in guild.counts:
            guild.counts[c] = int(data[line])
            line += 1
        for c in guild.latest:
            guild.latest[c] = data[line]
            line += 1
        for m in guild.milestones:
            guild.milestones[m] = eval(data[line])
            line += 1
    print("Loaded counting data")
    
def save():
    data = ""
    for gld in count_guilds:
        data += count_guilds[gld].save_str()
        data += "\n"
    data = data[:-2]
    with open(save_file, "w")as f:
        f.write(data)
    
    print("Saved info")

@bot.event
async def on_message(message):
    if message.author == bot.user or type(message.channel) == discord.DMChannel:
        return
    gld = count_guilds[message.channel.guild]
    
    if message.channel in gld.channels.values():
        counted = gld.try_count(message)
        if counted == False:
            await message.delete()
        elif type(counted) == list:
            if counted[1]:
                await gld.milestone_channel.send(counted[1])
    if message.channel == gld.bot_channel:
        await bot.process_commands(message)

@bot.command(name="find")
async def find_mistakes(ctx, t="c", limit=None):
    gld = count_guilds[ctx.guild]
##    if ctx.message.channel != gld.bot_channel:
##        return
    if not is_master(ctx.author):
        await ctx.send("`Permission denied.`")
        return
    if t not in gld.counts:
        await gld.bot_channel.send("`Unknown type. Use '.help' for help.`")
        return
    
    await ctx.send(f"`Scanning for errors in #{channel_names[t]}`")
    lim = to_num(limit)
    lim = lim if lim != "Invalid" else None
    history = await gld.channels[t].history(limit=lim).flatten()
    history.reverse()
    new = history[0].content.split()[0]
    old = eval(eval_num[t])

    for msg in history[1:]:
        new = msg.content.split()[0]
        new = eval(eval_num[t])
        if not eval(count_valid[t]):
            await ctx.send(f"`Located miscount around {old} - {new}`")
        old = new if new != "Invalid" else old
    await ctx.send("`Done checking for errors.`")

@bot.command(name="set")
async def setcount(ctx, t="c", amount="42"):
    gld = count_guilds[ctx.guild]
##    if ctx.message.channel != gld.bot_channel:
##        return
    if t not in gld.counts:
        await gld.bot_channel.send("`Unknown type. Use '.help' for help.`")
        return
    if not is_master(ctx.author):
        await ctx.send("`Permission denied.`")
        return
    n = to_num(amount)
    if n == "Invalid":
        await ctx.send("`[Error] Invalid number.`")
        return
    gld.counts[t] = n
    save()
    await ctx.send(f"`#{channel_names[t]} progress is now {gld.counts[t]}`")

@bot.command(name="count")
async def getcount(ctx, t="c"):
    gld = count_guilds[ctx.guild]
##    if ctx.message.channel != gld.bot_channel:
##        return
    if t not in gld.counts:
        await gld.bot_channel.send("`Unknown type. Use '.help' for help.`")
        return
    await gld.bot_channel.send(f"`#{channel_names[t]} progress is {gld.counts[t]}`")

@bot.command(name="help")
async def h(ctx):
    gld = count_guilds[ctx.guild]
##    if ctx.message.channel == gld.bot_channel:
    await ctx.send(help_text)

@bot.command(name="credits")
async def cred(ctx):
    gld = count_guilds[ctx.guild]
##    if ctx.message.channel == gld.bot_channel:
    await ctx.send(credit_text)

@bot.command(name="alephnull")
async def kill_bot(ctx):
    if "316553438186045441" in ctx.author.mention:
        print(f"Closed by {ctx.author.name}#{ctx.author.discriminator} in guild: {ctx.guild.name}")
        for guild in bot.guilds:
            gld = count_guilds[guild]
            if gld.bot_channel != None:
                await gld.bot_channel.send(shutdown_msg)
        await bot.close()
    else:
        print(f"{ctx.author.mention} tried to kill bot")
        await ctx.send("`Permission denied.`")

@bot.command(name="save")
async def manual_save(ctx):
    gld = count_guilds[ctx.guild]
    if ctx.message.channel != gld.bot_channel:
        return
    if not is_master(ctx.author):
        await ctx.send("`Permission denied.`")
        return
    save()
    await ctx.send("`Saved all counting info`")

@bot.event
async def on_ready():
    print(f"CONNECTED\nLogged in as {bot.user.name}")
    await bot.change_presence(activity=presence)

    #print(bot.user.id)
    print("guilds:")
    for guild in bot.guilds:
        print(guild.name)
        count_guilds[guild] = CountGuild(guild)
    print("-----")
    load()
    for guild in bot.guilds:
        gld = count_guilds[guild]
        if gld.bot_channel != None:
            join = join_msg
            for ctype in gld.counts:
                join += f"\n#{channel_names[ctype]} progress is [{gld.counts[ctype]}]."
            join += "\nPlease update if incorrect.```"
            await gld.bot_channel.send(join)
            for c in gld.channels:
                if gld.channels[c] == None:
                    await gld.bot_channel.send(f"{channel_error}{channel_names[c]}.```")
@bot.event
async def on_disconnect():
    print(f"Disconnected on {time.ctime()}")
    save()

bot.run(TOKEN)
