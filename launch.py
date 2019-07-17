from logging import basicConfig, INFO

from discord.ext.commands import Bot

from bot import Vouch, prefixes
from config import load_config


basicConfig(level=INFO)

if __name__ == '__main__':
    config = load_config()
    bot = Bot(
        command_prefix=prefixes, help_attrs={'name':config['help-command']}
    )
    bot.add_cog(Vouch(config, bot))
    bot.run(config['bot-token'])
