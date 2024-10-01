import asyncio
import random
from urllib.parse import unquote, quote

import aiohttp
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from datetime import timedelta
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.errors import UsernameNotOccupied
from pyrogram.raw.functions import account
from pyrogram.raw.types import InputBotAppShortName, InputNotifyPeer, InputPeerNotifySettings
from .agents import generate_random_user_agent
from bot.config import settings
from typing import Callable
from time import time
import functools
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers


def error_handler(func: Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            await asyncio.sleep(1)
    return wrapper

class Tapper:
    def __init__(self, tg_client: Client, proxy: str):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.proxy = proxy
        self.tg_web_data = None
        self.tg_client_id = 0

    async def get_tg_web_data(self) -> str:
        
        if self.proxy:
            proxy = Proxy.from_str(self.proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()

                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)
            
            while True:
                try:
                    peer = await self.tg_client.resolve_peer('b_usersbot')
                    break
                except FloodWait as fl:
                    fls = fl.value

                    logger.warning(f"{self.session_name} | FloodWait {fl}")
                    logger.info(f"{self.session_name} | Sleep {fls}s")
                    await asyncio.sleep(fls + 3)
            
            ref_id = random.choices([settings.REF_ID, "ref-boKr22ZTh5QatNJHMzqHhx"], weights=[75, 25], k=1)[0]
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                platform='android',
                app=InputBotAppShortName(bot_id=peer, short_name="join"),
                write_allowed=True,
                start_param=ref_id
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))
            tg_web_data_parts = tg_web_data.split('&')
            
            user_data = tg_web_data_parts[0].split('=')[1]
            chat_instance = tg_web_data_parts[1].split('=')[1]
            chat_type = tg_web_data_parts[2].split('=')[1]
            start_param = tg_web_data_parts[3].split('=')[1]
            auth_date = tg_web_data_parts[4].split('=')[1]
            hash_value = tg_web_data_parts[5].split('=')[1]

            user_data_encoded = quote(user_data)

            init_data = (f"user={user_data_encoded}&chat_instance={chat_instance}&chat_type={chat_type}&"
                         f"start_param={start_param}&auth_date={auth_date}&hash={hash_value}")

            me = await self.tg_client.get_me()
            self.tg_client_id = me.id
            
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return init_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error: {error}")
            await asyncio.sleep(delay=3)

    
    @error_handler
    async def make_request(self, http_client, method, endpoint=None, url=None, **kwargs):
        full_url = url or f"https://api.billion.tg/api/v1{endpoint or ''}"
        response = await http_client.request(method, full_url, **kwargs)
        response.raise_for_status()
        return await response.json()
    
    @error_handler
    async def login(self, http_client, init_data):
        http_client.headers["Tg-Auth"] = init_data
        user = await self.make_request(http_client, 'GET', endpoint="/auth/login")
        return user
    
    @error_handler
    async def info(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/users/me")
    
    
    @error_handler
    async def join_and_mute_tg_channel(self, link: str):
        await asyncio.sleep(delay=random.randint(15, 30))
        
        if not self.tg_client.is_connected:
            await self.tg_client.connect()
            
        parsed_link = link if 'https://t.me/+' in link else link[13:]
        try:
            try:
                chat = await self.tg_client.join_chat(parsed_link)
                logger.info(f"{self.session_name} | Successfully joined chat <b>{chat.title}</b>")
            except Exception as join_error:
                if "USER_ALREADY_PARTICIPANT" in str(join_error):
                    logger.info(f"{self.session_name} | Already a member of the chat: {link}")
                    chat = await self.tg_client.get_chat(parsed_link)
                else:
                    
                    raise join_error

            chat_id = chat.id
            chat_title = getattr(chat, 'title', link)

            await asyncio.sleep(random.randint(5, 10))

            peer = await self.tg_client.resolve_peer(chat_id)
            await self.tg_client.invoke(account.UpdateNotifySettings(
                peer=InputNotifyPeer(peer=peer),
                settings=InputPeerNotifySettings(mute_until=2147483647)
            ))
            logger.info(f"{self.session_name} | Successfully muted chat <b>{chat_title}</b>")

        except Exception as e:
            logger.error(f"{self.session_name} | Error joining/muting channel {link}: {str(e)}")

        finally:
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

        await asyncio.sleep(random.randint(10, 20))
            
    
    @error_handler
    async def add_gem_last_name(self, http_client: aiohttp.ClientSession, task_id: str):
        if not self.tg_client.is_connected:
            try:
                await self.tg_client.connect()
            except Exception as error:
                logger.error(f"{self.session_name} | (Gem) Connect failed: {error}")

        me = await self.tg_client.get_me()
        await self.tg_client.update_profile(first_name=f"{me.first_name} 💎")
        await asyncio.sleep(5)
        result = await self.done_task(http_client=http_client, task_id=task_id)
        await asyncio.sleep(5)
        await self.tg_client.update_profile(first_name=me.first_name)
        if self.tg_client.is_connected:
                await self.tg_client.disconnect()
        
        return result
    
    @error_handler
    async def get_task(self, http_client: aiohttp.ClientSession) -> dict:
        return await self.make_request(http_client, 'GET', endpoint="/tasks")
    
    
    @error_handler
    async def done_task(self, http_client: aiohttp.ClientSession, task_id: str):
        return await self.make_request(http_client, 'POST', endpoint= "/tasks", json={'uuid': task_id})
        
        
    @error_handler
    async def check_proxy(self, http_client: aiohttp.ClientSession) -> None:
        response = await self.make_request(http_client, 'GET', url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
        ip = response.get('origin')
        logger.info(f"{self.session_name} | Proxy IP: <lc>{ip}</lc>")
        
        
    
    async def run(self) -> None:
        if settings.USE_RANDOM_DELAY_IN_RUN:
                random_delay = random.randint(settings.RANDOM_DELAY_IN_RUN[0], settings.RANDOM_DELAY_IN_RUN[1])
                logger.info(f"{self.session_name} | Bot will start in <lc>{random_delay}s</lc>")
                await asyncio.sleep(random_delay)
        
        
        proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None
        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)
        if self.proxy:
            await self.check_proxy(http_client=http_client)
        
        random_user_agent = generate_random_user_agent(device_type='android', browser_type='chrome')
        
        if settings.FAKE_USERAGENT:            
            http_client.headers['User-Agent'] = random_user_agent
        
        while True:
            try:
                if http_client.closed:
                    if proxy_conn:
                        if not proxy_conn.closed:
                            proxy_conn.close()

                    proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None
                    http_client = aiohttp.ClientSession(headers=headers, connector=proxy_conn)
                    if settings.FAKE_USERAGENT:            
                        http_client.headers['User-Agent'] = random_user_agent
                init_data = await self.get_tg_web_data()
                if not init_data:
                    if not http_client.closed:
                        await http_client.close()
                    if proxy_conn:
                        if not proxy_conn.closed:
                            proxy_conn.close()
                    logger.info(f"{self.session_name} | 💎 <lc>Login failed</lc>")     
                    await asyncio.sleep(300)
                    logger.info(f"{self.session_name} | Sleep <lc>300s</lc>")
                    continue
                login = await self.login(http_client=http_client, init_data=init_data)
                if not login:
                    logger.info(f"{self.session_name} | 💎 <lc>Login failed</lc>")
                    await asyncio.sleep(300)
                    logger.info(f"{self.session_name} | Sleep <lc>300s</lc>")
                    continue
                    
                    
                if login.get('response', {}).get('isNewUser', False):
                    logger.info(f'{self.session_name} | 💎 <lc>User registered!</lc>')
                    
                accessToken = login.get('response', {}).get('accessToken')
                logger.info(f"{self.session_name} | 💎 <lc>Login successful</lc>")
                
                http_client.headers["Authorization"] = "Bearer " + accessToken
                user_data = await self.info(http_client=http_client)
                user_info = user_data.get('response', {}).get('user', {})
                time_left = max(user_info.get('deathDate') - time(), 0)
                time_left_formatted = str(timedelta(seconds=int(time_left))).replace(',', '')
                time_left_formatted = str(timedelta(seconds=int(time_left)))
                if ',' in time_left_formatted:
                    days, time_ = time_left_formatted.split(',')
                    days = days.split()[0] + 'd'
                else:
                    days = '0d'
                    time_ = time_left_formatted
                hours, minutes, seconds = time_.split(':')
                formatted_time = f"{days[:-1]}d{hours}h {minutes}m {seconds}s"
                logger.info(f"{self.session_name} | Left: <lc>{formatted_time}</lc> seconds | Alive: <lc>{user_info.get('isAlive')}</lc>")
                tasks = await self.get_task(http_client=http_client)
                for task in tasks.get('response', {}):
                    if not task.get('isCompleted') and task.get('type') not in ["INVITE_FRIENDS", "BOOST_TG", "CONNECT_WALLET"]:
                        logger.info(f"{self.session_name} | Performing task <lc>{task['taskName']}</lc>...")
                        if task.get('type') == 'REGEX_STRING':
                            result = await self.add_gem_last_name(http_client=http_client, task_id=task['uuid'])
                            if result:
                                logger.info(f"{self.session_name} | Task <lc>{task.get('taskName')}</lc> completed! | Reward: <lc>+{task.get('secondsAmount')}</lc>")
                            continue
                        
                        
                        if task.get('type') == 'SUBSCRIPTION_TG':
                            logger.info(f"{self.session_name} | Performing TG subscription to <lc>{task['link']}</lc>")
                            await self.join_and_mute_tg_channel(task['link'])
                        
                        result = await self.done_task(http_client=http_client, task_id=task['uuid'])
                        if result:
                            if result:
                                logger.info(f"{self.session_name} | Task <lc>{task.get('taskName')}</lc> completed! | Reward: <lc>+{task.get('secondsAmount')}</lc>")
                    await asyncio.sleep(delay=5)
                await http_client.close()
                if proxy_conn:
                    if not proxy_conn.closed:
                        proxy_conn.close()
            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error: {error}")
                await asyncio.sleep(delay=3)
            
            sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
            logger.info(f"{self.session_name} | Sleep <lc>{sleep_time}s</lc>")
            await asyncio.sleep(delay=sleep_time)
            
            
            
            

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client, proxy=proxy).run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
