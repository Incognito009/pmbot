from telegram.ext import CommandHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.helper.mirror_utils.upload_utils import gdriveTools
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.clone_status import CloneStatus
from bot import dispatcher, LOGGER, CLONE_LIMIT, STOP_DUPLICATE, download_dict, download_dict_lock, Interval, DOWNLOAD_STATUS_UPDATE_INTERVAL
from bot.helper.ext_utils.bot_utils import get_readable_file_size, check_limit, setInterval
import random
import string


def cloneNode(update, context):
    args = update.message.text.split(" ", maxsplit=1)
    uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
    if len(args) > 1:
        link = args[1]
        gd = gdriveTools.GoogleDriveHelper()
        res, size, name, files = gd.clonehelper(link)
        if res != "":
            sendMessage(res, context.bot, update)
            return
        if STOP_DUPLICATE:
            LOGGER.info('Checking File/Folder if already in Drive...')
            smsg, button = gd.drive_list(name)
            if smsg:
                msg3 = "File/Folder is already available in Drive.\nHere are the search results:"
                sendMarkup(msg3, context.bot, update, button)
                return
        if CLONE_LIMIT is not None:
            result = check_limit(size, CLONE_LIMIT)
            if result:
                msg2 = f'Failed, Clone limit is {CLONE_LIMIT}.\nYour File/Folder size is {get_readable_file_size(size)}.'
                sendMessage(msg2, context.bot, update)
                return
        if files < 15:
            msg = sendMessage(f"Cloning: <code>{link}</code>", context.bot, update)
            result, button = gd.clone(link)
            deleteMessage(context.bot, msg)
        else:
            drive = gdriveTools.GoogleDriveHelper(name)
            gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=12))
            clone_status = CloneStatus(drive, size, update, gid)
            with download_dict_lock:
                download_dict[update.message.message_id] = clone_status
            if len(Interval) == 0:
                Interval.append(setInterval(DOWNLOAD_STATUS_UPDATE_INTERVAL, update_all_messages))
            sendClone = f"<b>Hei {uname} </b>\n\n<b>Your Clone Has Been Added To The Status</b>\n\n<b>Use /{BotCommands.StatusCommand} To Check Your Progress</b>"
            sendMessage(sendClone, context.bot, update)
            result, button = drive.clone(link)
            with download_dict_lock:
                del download_dict[update.message.message_id]
                count = len(download_dict)
            try:
                if count == 0:
                    Interval[0].cancel()
                    del Interval[0]
                    delete_all_messages()
                else:
                    update_all_messages()
            except IndexError:
                pass
        if update.message.from_user.username:
            uname = f'@{update.message.from_user.username}'
        else:
            uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
        if uname is not None:
            cc = f'\n\n<b>#Cloned By {uname}</b>\n\n<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
            men = f'{uname} '
            msg_g = f'\n\n - <b><i>Never Share G-Drive/Index Link.</i></b>\n - <b><i>Join TD To Access G-Drive Link.</i></b>\n\n<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
            fwdpm = f'\n\n<b>You Can Find Upload In Private Chat</b>\n\n<b>▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬</b>'
        if button == "cancelled" or button == "":
            sendMessage(men + result, context.bot, update)
        else:
            logmsg = sendLog(result + cc + msg_g, context.bot, update, button)
            if logmsg:
                log_m = f"\n\n<b>Link Uploaded, Click Below Button</b>"
                sendMarkup(result + cc + log_m + fwdpm, context.bot, update, InlineKeyboardMarkup([[InlineKeyboardButton(text="CLICK HERE", url=logmsg.link)]]))
                sendPrivate(result + cc + msg_g, context.bot, update, button)
    else:
        sendMessage('Provide G-Drive Shareable Link to Clone.', context.bot, update)

clone_handler = CommandHandler(BotCommands.CloneCommand, cloneNode, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(clone_handler)
