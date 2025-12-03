How to run locally:

1. ensure that you have all python packages installed especially discord.py
2. go to discord developer portal and create a new application
3. this will grant you an API key from discord to use for your bot, this is sensitive information and discord will immediately null this key if it is found online at all, so keep it safe
4. go through the basics like entering the bio of the bot, the name, etc. and then click on the bot tab on the left hand side under settings
5. scroll down and give your bot administrator privileges so it cannot be interfered with
6. after this, you are going to go back to general information tab and copy your discord bot key
7. go to the bottom of the valbot.py file and replace the "insert your key" parameter with your actual bot key
8. NOTICE:
9. THE VALORANT NEWS WEBSITE CHANGES FREQUENTLY, I have already ran into an issue where the class name has changed, so factors like class name and the overall HTML structure of the news website is going to change and will need to be monitored every so often in the event that you are trying to run this bot. The reason being is because the bot is finding and scraping the information via class names
10. after you do this, the discord bot should be running and you can use the /hello so the bot says hello, and use /patchnotes to activate the scraping process
