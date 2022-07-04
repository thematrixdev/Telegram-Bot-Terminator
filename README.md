# Telegram Bot Terminator

Telegram CAPTCHA bot. Fight SPAM in Telegram groups.

Cloud hosted instance
[@bot_terminator_bot](https://t.me/bot_terminator_bot)

## How does it work

1. Add the bot to your group or supergroup
2. Ask the group owner to grant the bot `admin` permission
3. Everytime a new user join the group, the user has to pass the CAPTCHA to obtain normal user rights
4. New user sending out suspicious will be banned as well 

## Step-by-step installation guide

Open [@bot_terminator_bot](https://t.me/bot_terminator_bot) on PC or phone with Telegram installed

![img_1.png](static/image/img_1.png)

Select "START"
 
![img_2.png](static/image/img_2.png)

Open the "Bot Info" dialog

![img_4.png](static/image/img_4.png)

Choose "Add to Group" and "OK"

![img_5.png](static/image/img_5.png)

Go to the group and open the "Edit group" dialog

![img_6.png](static/image/img_6.png)

Select "Administrators"

![img_7.png](static/image/img_7.png)

Find and select "Bot Terminator"

![img_8.png](static/image/img_8.png)

Default settings would be fine. Click "Save"

![img_9.png](static/image/img_9.png)

Select "Close"

![img_10.png](static/image/img_10.png)

Select "Save"

![img_5.png](static/image/img_6.png)

## Self-hosting instance

1. Talk to [BotFather](https://t.me/BotFather)
2. `git clone` this project
3. Rename `.env.sample` to `.env` and modify configurations
4. `docker-compose up -d`

## Thanks

[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)

