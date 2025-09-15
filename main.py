
"""
Discord Moderation Bot - Enhanced & Consolidated Version with Hybrid Commands
80+ commands with hybrid support, no-prefix system, enhanced role parsing, and optimized codebase
Enhanced with custom command system for role assignment and mention responses
Fixed music system with Spotify/YouTube support and vcpull command
New features: listcmds, setprefix, steal emoji/sticker, owner-only say command
Made by Onevibe
"""

import discord
from discord.ui import View, Select
from discord.ext import commands, tasks
import os
from datetime import datetime
from utils import (
    bot_stats, load_data, get_emoji, create_embed, start_web_server, update_bot_stats, build_embed_from_data
)
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your_bot_token_here')
DEFAULT_PREFIX = os.getenv('BOT_PREFIX', '!')
EMBED_COLOR = discord.Color.blue()
FOOTER_TEXT = "Made by Nikuuu"
BOT_OWNER_ID = 957110332495630366  # Owner ID for restricted commands

# Dynamic prefix storage (guild_id: prefix)
guild_prefixes = {}

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True
intents.voice_states = True

# Role mappings for role assignment commands
ROLE_MAPPINGS = {
    'gif': 'Gif exe',
    'img': 'Attach exe', 
    'vce': 'Vc exe',
    'ext': 'Ext exe',
    'nick': 'nick exe',
    'req': 'Req role'
}

# Dynamic prefix function
def get_prefix(bot, message):
    if message.guild:
        return guild_prefixes.get(message.guild.id, DEFAULT_PREFIX)
    return DEFAULT_PREFIX

def get_current_prefix(guild_id):
    return guild_prefixes.get(guild_id, DEFAULT_PREFIX)

async def handle_custom_command(message, cmd_name, cmd_data):
    """Handle execution of custom commands for role assignment"""
    if not message.mentions:
        embed = create_embed(
            f"{get_emoji('cross')} Missing User", 
            f"Please mention a user to use this command!\n"
            f"Example: `{get_current_prefix(message.guild.id)}{cmd_name} @username`"
        )
        return await message.channel.send(embed=embed)

    target_user = message.mentions[0]
    
    # Handle both old and new data structures
    if isinstance(cmd_data, dict) and 'role_id' in cmd_data:
        role_id = cmd_data['role_id']
        role_name = cmd_data.get('role', 'Unknown Role')
    else:
        # Legacy support for old structure
        role_id = cmd_data if isinstance(cmd_data, int) else None
        role_name = 'Unknown Role'

    # Find the role by ID first
    role = message.guild.get_role(role_id) if role_id else None
    
    if not role:
        embed = create_embed(
            f"{get_emoji('cross')} Role Not Found", 
            f"The role for command `{cmd_name}` doesn't exist or has been deleted!\n"
            f"Please recreate the command with `addcmd {cmd_name} <role>`"
        )
        return await message.channel.send(embed=embed)

    # Check role hierarchy
    if role >= message.guild.me.top_role:
        embed = create_embed(
            f"{get_emoji('cross')} Hierarchy Error", 
            f"I can't assign **{role.name}** - it's higher than my role!"
        )
        return await message.channel.send(embed=embed)

    # Check if user can assign this role (if not server owner)
    if message.author != message.guild.owner and role >= message.author.top_role:
        embed = create_embed(
            f"{get_emoji('cross')} Permission Error", 
            f"You can't assign **{role.name}** - it's higher than your role!"
        )
        return await message.channel.send(embed=embed)

    # Toggle role assignment
    try:
        if role in target_user.roles:
            await target_user.remove_roles(role, reason=f"Custom command: {cmd_name} by {message.author}")
            action = "removed from"
            emoji = get_emoji('cross')
        else:
            await target_user.add_roles(role, reason=f"Custom command: {cmd_name} by {message.author}")
            action = "assigned to"
            emoji = get_emoji('tick')

        embed = create_embed(
            f"{emoji} Role {action.title()}", 
            f"Role **{role.name}** {action} {target_user.mention}"
        )
        await message.channel.send(embed=embed)

    except discord.Forbidden:
        embed = create_embed(
            f"{get_emoji('cross')} Permission Error", 
            f"I don't have permission to manage **{role.name}**!"
        )
        await message.channel.send(embed=embed)
    except Exception as e:
        embed = create_embed(
            f"{get_emoji('cross')} Error", 
            f"An error occurred: {str(e)}"
        )
        await message.channel.send(embed=embed)

class ModBot(commands.Bot):
    def __init__(self):
        # Optimize intents - only use what's needed
        optimized_intents = discord.Intents.default()
        optimized_intents.message_content = True
        optimized_intents.members = True
        optimized_intents.voice_states = True
        optimized_intents.presences = False  # Disable presences for better performance
        
        super().__init__(
            command_prefix=get_prefix,
            intents=optimized_intents,
            help_command=None,
            case_insensitive=True,
            chunk_guilds_at_startup=False,  # Don't chunk all guilds at startup
            member_cache_flags=discord.MemberCacheFlags.from_intents(optimized_intents),  # Enable member cache for accurate counts
            max_messages=1000,  # Reduced message cache for better performance
            heartbeat_timeout=30,  # Faster heartbeat timeout for better responsiveness
            guild_ready_timeout=2  # Faster guild ready timeout
        )
        
        # Add connection pooling
        self.session = None
        
        # Load data and initialize variables
        self.data = load_data()
        self.no_prefix_users = set(self.data.get('no_prefix_users', []))
        self.custom_commands = self.data.get('custom_commands', {})
        
        # Load guild prefixes
        global guild_prefixes
        guild_prefixes = self.data.get('guild_prefixes', {})

        # Ensure data persistence
        self.force_save_data()
        
    def force_save_data(self):
        """Force save all current data to ensure persistence"""
        try:
            from utils import save_data
            save_data(self.data)
            print("💾 Force saved all bot data on startup")
        except Exception as e:
            print(f"❌ Error force saving data: {e}")
        
        # Music system variables
        self.music_queues = {}
        self.bot_voice_clients = {}
        
        # AFK system
        self.afk_users = {}
        
        # Statistics
        self.start_time = datetime.now()
        self.commands_used = 0
        
        # Snipe system
        self.deleted_messages = []
        
        # Warning system
        self.user_warnings = {}
        
        # Commands synced flag
        self.commands_synced = False

        # store guild data
        self.guild_data = self.data.get('guild_data', {})
        
        # Performance monitoring
        self.latency_samples = []
        self.commands_used = 0

    @tasks.loop(minutes=1)
    async def performance_monitor(self):
        """Monitor bot performance and latency"""
        try:
            if not self.is_ready():
                return
                
            current_latency = self.latency * 1000
            self.latency_samples.append(current_latency)
            
            # Keep only last 100 samples
            if len(self.latency_samples) > 100:
                self.latency_samples.pop(0)
            
            # Log performance every 5 minutes
            if len(self.latency_samples) % 5 == 0:
                avg_latency = sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0
                print(f"Performance: {current_latency:.1f}ms current, {avg_latency:.1f}ms avg, {self.commands_used} commands")
                
        except Exception as e:
            print(f"Performance monitor error: {e}")

    @performance_monitor.before_loop
    async def before_performance_monitor(self):
        await self.wait_until_ready()

    async def setup_hook(self):
        """Setup function called when bot is starting"""
        # Start web server immediately to satisfy deployment health checks
        print("🚀 Starting web server for deployment health checks...")
        start_web_server()
        
        # Give web server time to start before proceeding
        await asyncio.sleep(3)
        print("✅ Web server startup delay completed")
        
        # Create HTTP session with conservative limits for hosting platforms
        try:
            connector = aiohttp.TCPConnector(
                limit=10,  # Further reduced to prevent rate limiting
                limit_per_host=2,  # Much lower limit per host
                ttl_dns_cache=1800,  # Longer cache time
                use_dns_cache=True,
                keepalive_timeout=60,  # Longer keepalive
                enable_cleanup_closed=True
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)  # Longer timeout
            )
        except Exception as e:
            print(f"❌ Error creating HTTP session: {e}")
            self.session = None
        
        # Voice commands disabled - removed music functionality
        # await self.load_extension("voice")
        # Search command disabled - removed due to YouTube authentication issues
        # await self.load_extension("search")
        
        # Start performance monitoring
        self.performance_monitor.start()
        
        # Load all organized command modules
        from commands import setup_all_commands
        await setup_all_commands(self)
        
        if not self.commands_synced:
            try:
                print("🔧 Setting up slash commands...")
                synced = await self.tree.sync()
                print(f"✅ Synced {len(synced)} slash commands")
                self.commands_synced = True
            except Exception as e:
                print(f"❌ Failed to sync commands: {e}")

    async def on_ready(self):
        """Event called when bot is ready"""
        print(f"🤖 Bot is ready! Logged in as {self.user}")
        print(f"📊 Connected to {len(self.guilds)} guilds with {len(set(self.get_all_members()))} users")
        
        # Set bot presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Nikuuu drinking milk"
            )
        )
        
        # Start statistics update task
        self.update_stats.start()
        
        print("🌐 Web dashboard available at http://0.0.0.0:5000")

    @tasks.loop(minutes=30)  # Much longer interval to prevent rate limiting
    async def update_stats(self):
        """Update bot statistics with minimal API calls"""
        try:
            if self.is_ready() and hasattr(self, 'guilds'):
                # Only update basic stats without API calls
                bot_stats['status'] = 'online'
                bot_stats['guilds'] = len(self.guilds) if self.guilds else 0
                bot_stats['commands_used'] = self.commands_used
                
                # Calculate uptime without API calls
                if hasattr(self, 'start_time'):
                    uptime = datetime.now() - self.start_time
                    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    bot_stats['uptime'] = f"{hours}h {minutes}m"
                
                bot_stats['last_activity'] = datetime.now().isoformat()
                
        except Exception as e:
            print(f"❌ Error updating stats: {e}")
            await asyncio.sleep(60)  # Wait longer on error

    @update_stats.before_loop
    async def before_update_stats(self):
        await self.wait_until_ready()

    async def on_message(self, message):
        """Optimized message handling with strict rate limiting"""
        if message.author.bot:
            return

        # Much stricter rate limiting - prevent API spam
        if not hasattr(self, 'message_timestamps'):
            self.message_timestamps = []
        
        current_time = datetime.now().timestamp()
        
        # Clean old timestamps (last 60 seconds)
        self.message_timestamps = [t for t in self.message_timestamps if current_time - t < 60]
        
        # Limit to 15 messages per minute to prevent rate limiting
        if len(self.message_timestamps) >= 15:
            return
        
        self.message_timestamps.append(current_time)
        
        # Add delay between processing messages
        await asyncio.sleep(0.2)

        # Handle AFK system (optimized with rate limiting)
        if message.author.id in self.afk_users:
            afk_data = self.afk_users[message.author.id]
            del self.afk_users[message.author.id]

            embed = create_embed(
                f"{get_emoji('tick')} Welcome back!",
                f"*{message.author.display_name}* is no longer AFK\n"
                f"You were AFK for: *{afk_data['reason']}*"
            )
            # Use create_task for non-blocking execution with rate limiting
            try:
                asyncio.create_task(message.channel.send(embed=embed, delete_after=10))
            except discord.HTTPException:
                pass  # Ignore rate limit errors for AFK messages

        # Notify if mentioned user is AFK (limit to first mention only)
        if message.mentions and len(message.mentions) > 0:
            mention = message.mentions[0]  # Only check first mention
            if mention.id in self.afk_users:
                afk_data = self.afk_users[mention.id]
                time_afk = datetime.now() - afk_data['timestamp']
                hours, remainder = divmod(int(time_afk.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)

                embed = create_embed(
                    f"{get_emoji('sleepy')} User is AFK",
                    f"*{mention.display_name}* is currently AFK\n"
                    f"*Reason:* {afk_data['reason']}\n"
                    f"*Time:* {hours}h {minutes}m ago"
                )
                try:
                    await message.channel.send(embed=embed, delete_after=15)
                except discord.HTTPException:
                    pass  # Ignore rate limit errors

        # Respond if someone mentions the bot directly (with cooldown)
        if self.user in message.mentions and not message.mention_everyone:
            if len(message.content.split()) == 1:
                # Add cooldown to prevent spam
                if not hasattr(self, 'mention_cooldowns'):
                    self.mention_cooldowns = {}
                
                user_id = message.author.id
                current_time = datetime.now().timestamp()
                
                if user_id in self.mention_cooldowns:
                    if current_time - self.mention_cooldowns[user_id] < 30:  # 30 second cooldown
                        return
                
                self.mention_cooldowns[user_id] = current_time
                
                embed = create_embed(
                    "<:Bots:1407904145393844318> Hello there!",
                    f"My prefix is {get_current_prefix(message.guild.id)} or you can use slash commands!\n"
                    f"Type {get_current_prefix(message.guild.id)}help for a list of commands."
                )
                try:
                    await message.channel.send(embed=embed)
                except discord.HTTPException:
                    pass  # Ignore rate limit errors
                return

        # Process in guild only
        if message.guild:
            prefix = get_current_prefix(message.guild.id)
            content = message.content.strip()

            # Alias map
            alias_map = self.data.get('aliases', {}).get(str(message.guild.id), {})

            parts = content.split()
            if parts:
                cmd_name = parts[0].lower()

                # Replace alias if prefix command
                if content.startswith(prefix):
                    real_cmd = alias_map.get(cmd_name)
                    if real_cmd:
                        message.content = f"{prefix}{real_cmd} {' '.join(parts[1:])}".strip()
                            
                # Replace alias if no-prefix user
                elif message.author.id in self.no_prefix_users:
                    real_cmd = alias_map.get(cmd_name)
                    if real_cmd:
                        message.content = f"{real_cmd} {' '.join(parts[1:])}".strip()

            # After alias replacement, continue normal processing
            guild_id = str(message.guild.id)

            # Check custom commands
            cmd_name = message.content[len(prefix):].split()[0].lower() if message.content.startswith(prefix) else ""
            if guild_id in self.custom_commands and cmd_name in self.custom_commands[guild_id]:
                await handle_custom_command(message, cmd_name, self.custom_commands[guild_id][cmd_name])
                return

            # No-prefix built-in commands
            if message.author.id in self.no_prefix_users:
                all_commands = []
                for command in self.commands:
                    all_commands.append(command.name)
                    all_commands.extend(command.aliases)

                custom_commands = list(self.custom_commands.get(guild_id, {}).keys())
                first_word = message.content.split()[0].lower() if message.content.split() else ""

                if first_word in custom_commands:
                    await handle_custom_command(message, first_word, self.custom_commands[guild_id][first_word])
                    return

                if first_word in all_commands:
                    message.content = f"{prefix}{message.content}"
                    ctx = await self.get_context(message)
                    if ctx.valid:
                        self.commands_used += 1
                        return await self.invoke(ctx)

        # Finally process as normal command
        ctx = await self.get_context(message)
        if ctx.valid:
            self.commands_used += 1
            await self.invoke(ctx)

    async def close(self):
        """Clean up resources when bot shuts down"""
        if self.session:
            await self.session.close()
        await super().close()

    async def on_command(self, ctx):
        """Called when a command is invoked"""
        self.commands_used += 1
        
        # Add command rate limiting per user
        if not hasattr(self, 'command_cooldowns'):
            self.command_cooldowns = {}
        
        user_id = ctx.author.id
        current_time = datetime.now().timestamp()
        
        if user_id in self.command_cooldowns:
            # Remove old entries
            self.command_cooldowns[user_id] = [
                t for t in self.command_cooldowns[user_id] 
                if current_time - t < 60  # 1 minute window
            ]
            
            # Check if user is sending too many commands
            if len(self.command_cooldowns[user_id]) > 10:  # Max 10 commands per minute
                embed = create_embed(
                    f"{get_emoji('cross')} Rate Limited",
                    "You're sending commands too quickly! Please wait a moment."
                )
                try:
                    await ctx.send(embed=embed, delete_after=10)
                except:
                    pass
                return
            
            self.command_cooldowns[user_id].append(current_time)
        else:
            self.command_cooldowns[user_id] = [current_time]
        
        print(f"🔧 Command '{ctx.command}' used by {ctx.author} in {ctx.guild}")
        
    async def on_member_join(self, member):
        guild_id = str(member.guild.id)
        
        # Determine which autorole to use based on member type
        autorole_key = 'autoroles_bot' if member.bot else 'autoroles'
        member_type = "bot" if member.bot else "human"
        
        # Handle autorole with enhanced error checking
        if autorole_key in self.data and guild_id in self.data[autorole_key]:
            try:
                role_data = self.data[autorole_key][guild_id]
                
                # Handle both old single role format and new multiple roles format
                role_ids = []
                if isinstance(role_data, str):
                    try:
                        role_ids = [int(role_data)]
                    except ValueError:
                        print(f"❌ Invalid role ID string: {role_data}")
                        return
                elif isinstance(role_data, list):
                    for role_id in role_data:
                        try:
                            role_ids.append(int(role_id))
                        except ValueError:
                            print(f"❌ Invalid role ID in list: {role_id}")
                else:
                    try:
                        role_ids = [int(role_data)]  # Direct integer
                    except (ValueError, TypeError):
                        print(f"❌ Invalid role data type: {type(role_data)} - {role_data}")
                        return
                
                roles_assigned = 0
                total_roles = len(role_ids)
                
                for role_id in role_ids:
                    role = member.guild.get_role(role_id)
                    
                    if role:
                        # Check if bot has permission to assign the role
                        if member.guild.me.guild_permissions.manage_roles:
                            # More lenient hierarchy check - allow same position roles
                            if role.position <= member.guild.me.top_role.position and role != member.guild.me.top_role:
                                try:
                                    await member.add_roles(role, reason=f"Autorole assignment for {member_type}")
                                    print(f"✅ {member_type.capitalize()} autorole '{role.name}' successfully added to {member.display_name}")
                                    roles_assigned += 1
                                except discord.Forbidden:
                                    print(f"❌ No permission to assign {member_type} autorole '{role.name}' to {member.display_name}")
                                except discord.HTTPException as e:
                                    print(f"❌ HTTP error assigning {member_type} autorole '{role.name}' to {member.display_name}: {e}")
                            else:
                                print(f"❌ Cannot assign {member_type} autorole '{role.name}' to {member.display_name} - Role hierarchy issue. Move bot role higher or autorole lower.")
                        else:
                            print(f"❌ Bot doesn't have 'Manage Roles' permission in {member.guild.name}")
                            break  # No point checking other roles if no permission
                    else:
                        print(f"❌ {member_type.capitalize()} autorole with ID {role_id} not found in {member.guild.name}")
                
                if roles_assigned > 0:
                    print(f"✅ Successfully assigned {roles_assigned}/{total_roles} {member_type} autoroles to {member.display_name}")
                    
            except ValueError as e:
                print(f"❌ Invalid {member_type} autorole ID for {member.guild.name}: {self.data[autorole_key][guild_id]} - {e}")
            except Exception as e:
                print(f"❌ Unexpected error with {member_type} autorole for {member.display_name}: {e}")
        
        # Handle welcome message
        welcome_config = self.data.get('welcome', {}).get(guild_id)
        if welcome_config and welcome_config.get('enabled'):
            try:
                channel_id = welcome_config.get('channel_id')
                embed_name = welcome_config.get('embed_name')
                custom_message = welcome_config.get('message', '')
                
                if not channel_id or not embed_name:
                    print(f"❌ Welcome config incomplete for {member.guild.name}")
                    return
                
                channel = member.guild.get_channel(channel_id)
                if not channel:
                    print(f"❌ Welcome channel not found in {member.guild.name}")
                    return
                
                # Check if bot can send messages in channel
                if not channel.permissions_for(member.guild.me).send_messages:
                    print(f"❌ No permission to send messages in welcome channel for {member.guild.name}")
                    return
                
                # Get embed data
                embed_data = self.data.get('embeds', {}).get(guild_id, {}).get(embed_name)
                if not embed_data:
                    print(f"❌ Welcome embed '{embed_name}' not found for {member.guild.name}")
                    return
                
                from utils import build_embed_from_data
                embed = build_embed_from_data(
                    embed_data,
                    user=member,
                    bot=self.user,
                    guild=member.guild,
                    channel=channel
                )
                
                # Send custom message with embed in single message if custom message exists
                if custom_message:
                    # Replace placeholders in custom message
                    processed_message = custom_message.replace('{user}', member.mention)
                    processed_message = processed_message.replace('{username}', member.name)
                    processed_message = processed_message.replace('{server}', member.guild.name)
                    await channel.send(content=processed_message, embed=embed)
                else:
                    # Send only embed if no custom message
                    await channel.send(embed=embed)
                
                print(f"✅ Welcome message sent for {member.display_name}")
                
            except discord.Forbidden:
                print(f"❌ No permission to send welcome message for {member.display_name}")
            except discord.HTTPException as e:
                print(f"❌ HTTP error sending welcome message for {member.display_name}: {e}")
            except Exception as e:
                print(f"❌ Welcome message failed for {member.display_name}: {e}")

    async def on_command_error(self, ctx, error):
        """Handle command errors with rate limit detection"""
        try:
            if isinstance(error, commands.CommandNotFound):
                # Check for custom commands
                if ctx.guild:
                    guild_id = str(ctx.guild.id)
                    cmd_name = ctx.message.content.split()[0][len(ctx.prefix):].lower()
                    
                    if guild_id in self.custom_commands and cmd_name in self.custom_commands[guild_id]:
                        await handle_custom_command(ctx.message, cmd_name, self.custom_commands[guild_id][cmd_name])
                        return
                return
            
            elif isinstance(error, discord.HTTPException):
                if error.status == 429:  # Rate limited
                    print(f"🚨 RATE LIMITED: {error}")
                    print(f"Retry after: {getattr(error, 'retry_after', 'unknown')} seconds")
                    return
                elif error.status == 1015:  # Cloudflare block
                    print(f"🚨 CLOUDFLARE BLOCKED: {error}")
                    return
                else:
                    print(f"❌ HTTP Error {error.status}: {error}")
                    return
            
            elif isinstance(error, commands.MissingPermissions):
                embed = create_embed(
                    f"{get_emoji('cross')} Missing Permissions",
                    f"You need: {', '.join(error.missing_permissions)}"
                )
                await ctx.send(embed=embed)
            
            elif isinstance(error, commands.BotMissingPermissions):
                embed = create_embed(
                    f"{get_emoji('cross')} Bot Missing Permissions",
                    f"I need: {', '.join(error.missing_permissions)}"
                )
                await ctx.send(embed=embed)
            
            else:
                print(f"❌ Unhandled error: {error}")
                
        except Exception as e:
            print(f"❌ Error in error handler: {e}")

# Initialize bot
bot = ModBot()

# Interactive Help System with Views
class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(HelpSelect())

class HelpSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="🛡 Moderation",
                description="Moderation commands",
                value="mod"
            ),
            discord.SelectOption(
                label="👑 Roles",
                description="Role management commands",
                value="roles"
            ),
            discord.SelectOption(
                label="🎉 Fun & Social",
                description="Fun, games & social cmds",
                value="fun"
            ),
            discord.SelectOption(
                label="🛠 Utility & Info",
                description="Tools & info cmds",
                value="util"
            ),
            discord.SelectOption(
                label="🧱 Server setup & Management",
                description="Build & customize easily",
                value="setup"
            )
        ]
        super().__init__(placeholder="📜 Choose a category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        if value == "mod":
            embed = create_embed(
                "<a:Kabu_star:1400372359160008744> Moderation Commands",
                "• Ban — Ban a user\n"
                "• Kick — Kick a user\n"
                "• Mute — Temp mute a user\n"
                "• Unmute — Unmute a user\n"
                "• Unban — Unban a user\n"
                "• Warn — Add warning\n"
                "• Warnings — Check user warnings\n"
                "• Clearwarns — clear user warnings\n"
                "• Lock — lock channel\n"
                "• Unlock — unlock channel\n"
                "• Vcpull — Pull user to your Vc\n"
                "• Join — Bot joins your Vc\n"
                "• Leave — Bot leaves Vc\n"
                "• Purge — Delete messages\n"
                "• Cbot — Delete bot messages\n"
                "• Slowmode — Set slowmode\n"
                "• Nuke — Delete & recreate channel\n"
                "• Massban — Ban multiple users\n"
                "• Leaveguild — Bot leaves server\n"
                "• Setprefix — change prefix"
            )

        elif value == "roles":
            embed = create_embed(
                "<a:star:1407644764802912286> Role Management",
                "• Addrole — Add role to user\n"
                "• Removerole — Remove role from user\n"
                "• Createrole — Create a new role\n"
                "• Deleterole — Delete a role\n"
                "• Roleinfo — Get role details\n"
                "• Massrole — Add role to multiple users\n"
                "• Autorole — Auto on join\n"
                "• Autoroleremove — Remove auto role\n"
                "• Autorolebot — Auto on bot join\n"
                "• Addcmd — Create custom role cmd\n"
                "• Delcmd — Delete custom role cmd\n"
                "• Listcmds — List all custom cmds\n"
                "• Addalias — Add alias to cmd\n"
                "• Delalias — Delete alias\n"
                "• Listalias — List all aliases\n"
                "• Gif/Img/Vce/Ext/Nick/Req — Toggle quick roles"
            )

        elif value == "fun":
            embed = create_embed(
                "<a:star:1407644764802912286> Fun & Social",
                "• Coinflip — Flip a coin\n"
                "• Dice — Roll a dice\n"
                "• 8ball — Ask the magic 8ball\n"
                "• Joke — Get a random joke\n"
                "• Fact — Get a random fact\n"
                "• Poll — Create a poll\n"
                "• Ship — Ship two users"
            )

        elif value == "util":
            embed = create_embed(
                "<a:star:1407644764802912286> Utility & Info",
                "• Afk — Set afk\n"
                "• Remind — Set a reminder\n"
                "• Userinfo — Get user info\n"
                "• Serverinfo — Get server info\n"
                "• Avatar — Get user avatar\n"
                "• Noprefix — Toggle no prefix access\n"
                "• Leaveguild id — bot leaves server\n"
                "• Steal — steal emoji/sticker\n"
                "• Dm — Dm a user\n"
                "• Say — Bot says something\n"
                "• Ping — Check bot latency\n"
                "• Uptime — Check bot uptime\n"
                "• Mc — Member count\n"
                "• Npusers — List no prefix users\n"
                "• Snipe — Show last deleted message\n"
                "• Help — show help menu"
            )

        elif value == "setup":
            embed = create_embed(
                 "<a:star:1407644764802912286> Server Setup & Management",
                "• Embedadd — Create & save custom embed\n"
                "• Embededit — Edit saved embed\n"
                "• Embeddel — Delete saved embed\n"
                "• Embedlist — List all saved embeds\n"
                "• Embedsend — Send saved embed\n"
                "• Setwelcome — Set welcome embed\n"
                "• Delwelcome — Remove welcome embed\n"
                "• Togglewelcome — Enable/disable welcome\n"
                "• Testwelcome — Test welcome embed"
            )
        else:
            embed = create_embed("❓ Unknown", "Unknown category selected.")

        embed.set_footer(text="Designed & crafted by Onevibe 🫧")
        await interaction.response.edit_message(embed=embed, view=self.view)

# Create optimized bot instance
bot = ModBot()

# Performance optimizations added to existing bot structure

# Help Command
@bot.hybrid_command(name="help", description="Show help menu")
async def help(ctx):
    embed = create_embed(
        "<a:flowers:1407646827481927680>**Kabu Help Menu**<a:flowers:1407646827481927680>",
        "Hey there! I'm **Kabu**, your friendly Discord companion.\n\n"
        "<a:dot:1407642445616906350> **Prefix:** `!`\n"
        "<a:dot:1407642445616906350> **Total Commands:** 80+\n\n"
        "<:vnx_pink_dot:1407706084281417788> **Moderation & Roles** — keep server safe\n"
        "<:vnx_pink_dot:1407706084281417788> **Fun & Social** — play & vibe\n"
        "<:vnx_pink_dot:1407706084281417788> **Utility & Info** — quick tools & info\n\n"
        "<:heart_blue3:1407643679660839033> Tip: Use dropdown below to browse commands!"
    )
    embed.set_footer(text="Designed & crafted by Onevibe 🫧")
    await ctx.send(embed=embed, view=HelpView())

async def run_bot_with_retry():
    """Run bot with exponential backoff for rate limit recovery"""
    max_retries = 5
    base_delay = 30
    
    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting bot (attempt {attempt + 1}/{max_retries})...")
            
            if attempt > 0:
                # Exponential backoff with jitter
                delay = base_delay * (2 ** (attempt - 1)) + (attempt * 10)
                print(f"⏳ Waiting {delay}s before retry (rate limit recovery)...")
                await asyncio.sleep(delay)
            
            await bot.start(BOT_TOKEN)
            break
            
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = getattr(e, 'retry_after', 60)
                print(f"🚨 Rate limited! Waiting {retry_after + 30}s...")
                await asyncio.sleep(retry_after + 30)
                continue
            elif e.status == 1015:  # Cloudflare block
                print(f"🚨 Cloudflare blocked! Waiting 5 minutes...")
                await asyncio.sleep(300)  # Wait 5 minutes for IP unblock
                continue
            else:
                print(f"❌ HTTP Error: {e}")
                if attempt == max_retries - 1:
                    raise
                
        except discord.LoginFailure:
            print("❌ Invalid bot token!")
            break
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(base_delay * (2 ** attempt))

# Run the bot
if __name__ == "__main__":
    if BOT_TOKEN == 'your_bot_token_here':
        print("❌ Please set the DISCORD_BOT_TOKEN environment variable!")
        exit(1)
    
    try:
        asyncio.run(run_bot_with_retry())
    except KeyboardInterrupt:
        print("👋 Bot shutdown requested")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
