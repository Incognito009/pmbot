import os
import pickle
import re
import requests
import logging
import time

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from telegraph import Telegraph
from telegram import InlineKeyboardMarkup
from bot.helper.telegram_helper import button_build
from bot import DRIVE_NAME, DRIVE_ID, INDEX_LINK, telegraph_token
from bot.helper.ext_utils.bot_utils import get_readable_time


LOGGER = logging.getLogger(__name__)
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
TELEGRAPHLIMIT = 95

class GoogleDriveHelper:
    def __init__(self, name=None, listener=None):
        self.__G_DRIVE_TOKEN_FILE = "token.pickle"
        # Check https://developers.google.com/drive/scopes for all available scopes
        self.__OAUTH_SCOPE = ['https://www.googleapis.com/auth/drive']
        self.__service = self.authorize()
        self.telegraph_content = []
        self.path = []
        self.total_bytes = 0

    def get_readable_file_size(self,size_in_bytes) -> str:
        if size_in_bytes is None:
            return '0B'
        index = 0
        size_in_bytes = int(size_in_bytes)
        while size_in_bytes >= 1024:
            size_in_bytes /= 1024
            index += 1
        try:
            return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
        except IndexError:
            return 'File too large'


    def authorize(self):
        # Get credentials
        credentials = None
        if os.path.exists(self.__G_DRIVE_TOKEN_FILE):
            with open(self.__G_DRIVE_TOKEN_FILE, 'rb') as f:
                credentials = pickle.load(f)
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.__OAUTH_SCOPE)
                LOGGER.info(flow)
                credentials = flow.run_console(port=0)

            # Save the credentials for the next run
            with open(self.__G_DRIVE_TOKEN_FILE, 'wb') as token:
                pickle.dump(credentials, token)
        return build('drive', 'v3', credentials=credentials, cache_discovery=False)

    def get_recursive_list(self, file, rootid = "root"):
        rtnlist = []
        if not rootid:
            rootid = file.get('teamDriveId')
        if rootid == "root":
            rootid = self.__service.files().get(fileId = 'root', fields="id").execute().get('id')
        x = file.get("name")
        y = file.get("id")
        while(y != rootid):
            rtnlist.append(x)
            file = self.__service.files().get(
                                            fileId=file.get("parents")[0],
                                            supportsAllDrives=True,
                                            fields='id, name, parents'
                                            ).execute()
            x = file.get("name")
            y = file.get("id")
        rtnlist.reverse()
        return rtnlist

    def drive_query(self, parent_id, fileName):
        var=re.split(' |\.|_',fileName)
        query = f"name contains '{var[0]}' and trashed=false"
        return (
            self.__service.files()
            .list(
                supportsTeamDrives=True,
                includeTeamDriveItems=True,
                teamDriveId=parent_id,
                q=query,
                corpora='drive',
                spaces='drive',
                pageSize=1000,
                fields='files(id, name, mimeType, size, teamDriveId, parents)',
                orderBy='folder, modifiedTime desc',
            )
            .execute()["files"]
            if parent_id != "root"
            else self.__service.files()
            .list(
                q=query + " and 'me' in owners",
                pageSize=1000,
                spaces='drive',
                fields='files(id, name, mimeType, size, parents)',
                orderBy='folder, modifiedTime desc',
            )
            .execute()["files"]
        )

    def edit_telegraph(self):
        nxt_page = 1 
        prev_page = 0
        for content in self.telegraph_content :
            if nxt_page == 1 :
                content += f'<b><a href="https://telegra.ph/{self.path[nxt_page]}">Nᴇxᴛ</a></b>'
                nxt_page += 1
            else :
                if prev_page <= self.num_of_path:
                    content += f'<b><a href="https://telegra.ph/{self.path[prev_page]}">Pʀᴇᴠɪᴏᴜs</a></b>'
                    prev_page += 1
                if nxt_page < self.num_of_path:
                    content += f'<b> | <a href="https://telegra.ph/{self.path[nxt_page]}">Nᴇxᴛ</a></b>'
                    nxt_page += 1
            Telegraph(access_token=telegraph_token).edit_page(path = self.path[prev_page],
                                 title = "AZ Mirror Search",
                                 author_name="AZ Mirror",
                                 author_url='https://t.me/azbackup',
                                 html_content=content)
        return

    def drive_list(self, fileName):
        s_time = time.time()
        msg = ''
        content_count = 0
        add_title_msg = True
        var=re.split(' |\.|_|,',fileName)
        pattern = "".join(".*"+i for i in var)
        for INDEX, parent_id in enumerate(DRIVE_ID):
            add_drive_title = True
            response = self.drive_query(parent_id, fileName)
            if response:
                
                
                for file in response:
                    
                    x = re.search(pattern, file.get('name'),re.IGNORECASE)

                    if x:
                        if add_title_msg:
                            msg = f'<h3>Sᴇᴀʀᴄʜ Rᴇsᴜʟᴛs Fᴏʀ : {fileName}</h3><br><b><a href="https://cloud4.az0707.workers.dev/1:/Cloud%204"> Index Homepage </a></b> ||<b><a href="https://t.me/deity07"> Owner </a></b><br><br>'
                            add_title_msg = False
                        if add_drive_title:
                            msg += f"╾────────────╼<br><b>{DRIVE_NAME[INDEX]}</b><br>╾────────────╼<br>"
                            add_drive_title = False
                        if file.get('mimeType') == "application/vnd.google-apps.folder":  # Detect Whether Current Entity is a Folder or File.
                            msg += f"🗃️<code>{file.get('name')}</code> <b>(folder)</b><br>" \
                                   f"<b><a href='https://drive.google.com/drive/folders/{file.get('id')}'>G-Dʀɪᴠᴇ Lɪɴᴋ</a></b>"
                            if INDEX_LINK[INDEX] is not None:
                                url_path = "/".join(
                                    requests.utils.quote(n, safe='')
                                    for n in self.get_recursive_list(
                                        file, parent_id
                                    )
                                )

                                url = f'{INDEX_LINK[INDEX]}/{url_path}/'
                                msg += f'<b> | <a href="{url}">Iɴᴅᴇx Lɪɴᴋ</a></b>'
                        else:
                            msg += f"📄<code>{file.get('name')}</code> <b>({self.get_readable_file_size(file.get('size'))})</b><br>" \
                                   f"<b><a href='https://drive.google.com/uc?id={file.get('id')}&export=download'>G-Dʀɪᴠᴇ Lɪɴᴋ</a></b>"
                            if INDEX_LINK[INDEX] is not None:
                                url_path = "/".join(
                                    requests.utils.quote(n, safe='')
                                    for n in self.get_recursive_list(
                                        file, parent_id
                                    )
                                )

                                url = f'{INDEX_LINK[INDEX]}/{url_path}'
                                urls = f'{INDEX_LINK[INDEX]}/{url_path}?a=view'
                                msg += f'<b> | <a href="{url}">Iɴᴅᴇx Lɪɴᴋ</a></b>'
                                msg += f'<b> | <a href="{urls}">Vɪᴇᴡ Lɪɴᴋ</a></b>'
                        msg += '<br><br>'
                        content_count += 1
                    if (content_count==TELEGRAPHLIMIT):
                        msg = f'<h3>Too many Sᴇᴀʀᴄʜ Rᴇsᴜʟᴛs Fᴏʀ Yᴏᴜʀ Kᴇʏᴡᴏʀᴅ : {fileName}</h3><br>'


                        LOGGER.info(f"my a: {content_count}")
                        #self.telegraph_content.append(msg)
                        #msg = ""
                        #content_count = 0
                        return f'<b>Too Many Results To Show\nI have Found more than {content_count}\n\nPlease Modify Your Search Query, Like Add Year With Movie Name, Add Season/Episode Number To TV-Show Name :(</b> \n\n<b><i>Best Way Use #Index For Searching</i></b>', None


        if msg != '':
            self.telegraph_content.append(msg)

        if len(self.telegraph_content) == 0:
            return "<b>Nᴏ Rᴇsᴜʟᴛs Fᴏᴜɴᴅ :( </b>", None




        for content in self.telegraph_content :
            self.path.append(Telegraph(access_token=telegraph_token).create_page(
                                                        title = "AZ Mirror Search",
                                                        author_name="AZ Mirror",
                                                        author_url='https://t.me/azbackup',
                                                        html_content=content
                                                        )['path'])

        self.num_of_path = len(self.path)
        if self.num_of_path > 1:
            self.edit_telegraph()

        msg = f" <b>Sᴇᴀʀᴄʜ Rᴇsᴜʟᴛs Fᴏʀ :</b> ➼ {fileName}  "
        e_time = int(time.time() - s_time)
        msg = f" <b>🔎 Found : {content_count} Results For {fileName} <i>(Finished in <code>{get_readable_time(e_time)}</code>)</i> </b>\n\n#SearchResults"

        buttons = button_build.ButtonMaker()
        buttons.buildbutton("Click Here For Results", f"https://telegra.ph/{self.path[0]}")

        return msg, InlineKeyboardMarkup(buttons.build_menu(1))
