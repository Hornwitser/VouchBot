from logging import basicConfig, INFO

from bot import Bot, prefixes
from config import load_config


basicConfig(level=INFO)

if __name__ == '__main__':
    config = load_config()
    bot = Bot(
        config, command_prefix=prefixes,
        help_attrs={'name':config['help-command']}
    )
    bot.run(config['bot-token'])
