import os
import sys
import re
import json
import time
import queue
import zipfile
import shutil
import webbrowser
import traceback
import threading
import urllib.parse
import difflib
import bisect
import base64
import zlib
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import webview
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 路径与常量 ====================

def get_resource_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_data_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

RESOURCE_DIR = get_resource_dir()
DATA_DIR = get_data_dir()

DATA_ROOT = os.path.join(DATA_DIR, "date")
os.makedirs(DATA_ROOT, exist_ok=True)

DATA_FILE = os.path.join(DATA_ROOT, "local_data.json")
DETAIL_MAIN_FILE = os.path.join(DATA_ROOT, "detail_main.json")
DETAIL_EXTRA_FILE = os.path.join(DATA_ROOT, "detail_extra.json")
USER_FILE = os.path.join(DATA_ROOT, "user_data.json")
STATE_FILE = os.path.join(DATA_ROOT, "app_state.json")
ARCHIVE_DIR = os.path.join(DATA_ROOT, "archive_data")

RE_TIME = re.compile(r"([0-9]{1,2}:[0-9]{2})")
RE_CLEAN_TEXT = re.compile(r'[^\w\u4e00-\u9fa5]')
RE_WEEKDAY = re.compile(r'([一二三四五六日天1-7])')
# 更新解析用字节级预筛正则(整行二进制匹配，兼容空白)：命中候选集才做 json.loads，跳过海量无关行
RE_B_TYPE2 = re.compile(rb'"type"\s*:\s*2\s*[,}]')
RE_B_SUBJECT_ID = re.compile(rb'"subject_id"\s*:\s*(\d+)')
RE_B_ID = re.compile(rb'"id"\s*:\s*(\d+)')
WEEKDAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
               "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}
EPISODE_LIMIT = 100
GITHUB_API_URL = "https://api.github.com/repos/bangumi/Archive/releases/tags/archive"

# 下载不再测速：固定源顺序，下载中按速率判定切换
# 低速看门狗：每 5 秒记一段字节数；任一连续两段(约10秒)合计低于 1MB 即判定当前源过慢并切换
SPEED_SAMPLE_SECONDS = 5
LOW_SPEED_TEN_SEC_BYTES = 1 * 1024 * 1024
# 建立连接(拿到响应头)超过该秒数判失败换源
CONNECT_LIMIT_SECONDS = 2.0

# Bangumi 职位常量映射 (依据同目录 subject_staffs.yml 中的 anime 职位表补全，未收录的兜底显示数字编号)
POS_MAP = {
    "1": "原作", "2": "导演", "3": "脚本", "4": "分镜", "5": "演出", "6": "音乐", "7": "人物原案",
    "8": "人物设定", "9": "构图", "10": "系列构成", "11": "美术监督", "13": "色彩设计",
    "14": "总作画监督", "15": "作画监督", "16": "机械设定", "17": "摄影监督", "18": "监修",
    "19": "道具设计", "20": "原画", "21": "第二原画", "22": "动画检查", "23": "助理制片人",
    "24": "制作助理", "25": "背景美术", "26": "色彩指定", "27": "数码绘图", "28": "剪辑",
    "29": "原案", "30": "主题歌编曲", "31": "主题歌作曲", "32": "主题歌作词", "33": "主题歌演出",
    "34": "插入歌演出", "35": "企画", "36": "企划制作人", "37": "制作管理", "38": "宣传",
    "39": "录音", "40": "录音助理", "41": "系列监督", "42": "製作", "43": "设定",
    "44": "音响监督", "45": "音响", "46": "音效", "47": "特效", "48": "配音监督", "49": "联合导演",
    "50": "背景设定", "51": "补间动画", "52": "执行制片人", "53": "助理制片人", "54": "制片人",
    "55": "音乐助理", "56": "制作进行", "57": "演员监督", "58": "总制片人", "59": "联合制片人",
    "60": "台词编辑", "61": "后期制片协调", "62": "制作助理", "63": "制作", "64": "制作协调",
    "65": "音乐制作", "66": "特别鸣谢", "67": "动画制作", "69": "CG 导演", "70": "机械作画监督",
    "71": "美术设计", "72": "副导演", "73": "OP・ED 分镜", "74": "总导演", "75": "3DCG",
    "76": "制作协力", "77": "动作作画监督", "80": "监制", "81": "协力", "82": "摄影",
    "83": "制作进行协力", "84": "设定制作", "85": "音乐制作人", "86": "3DCG 导演", "87": "动画制片人",
    "88": "特效作画监督", "89": "主演出", "90": "作画监督助理", "91": "演出助理", "92": "主动画师",
    "93": "上色", "94": "上色检查", "95": "色彩检查", "96": "美术板", "97": "美术", "98": "印象板",
    "99": "2D 设计", "100": "3D 设计", "101": "技术导演", "102": "特技导演", "103": "色彩脚本",
    "104": "分镜协力", "105": "分镜抄写", "106": "副人物设定", "107": "客座人物设定", "108": "构图监修",
    "109": "构图作画监督", "110": "总作画监督助理", "111": "道具作画监督", "112": "概念设计",
    "113": "服装设计", "114": "标题设计", "115": "设定协力", "116": "音乐监督", "117": "选曲",
    "118": "插入歌作词", "119": "插入歌作曲", "120": "插入歌编曲", "121": "创意制片人",
    "122": "副制片人", "123": "制作统括", "124": "现场制片人", "125": "文艺制作", "127": "企画协力",
    "128": "OP・ED 演出", "129": "Bank 分镜演出", "130": "Live 分镜演出", "131": "剧中剧分镜演出",
    "132": "剧中剧人设", "133": "视觉导演", "134": "创意总监", "135": "特摄效果", "136": "视觉效果",
    "137": "动作导演", "138": "转场绘", "139": "插画", "140": "角色作画监督", "141": "作画监修",
    "142": "机设原案", "143": "概念艺术", "144": "视觉概念", "145": "画面设计", "146": "怪物设计",
    "147": "故事概念", "148": "剧本协调", "149": "脚本协力", "150": "副系列构成", "151": "构成协力",
    "152": "录音工作室", "153": "整音", "154": "音响制作担当", "155": "在线剪辑", "156": "离线剪辑",
    "157": "3D 动画师", "158": "CG 制作人", "159": "宣传制片人", "160": "美术制作人",
    "161": "音响制作人", "162": "CG 制作进行", "163": "美术制作进行", "164": "美术监督助理",
    "165": "色彩设计助理", "166": "摄影监督助理", "167": "制作管理助理", "168": "设定制作助理",
    "169": "剪辑助理", "170": "宣传协力", "171": "建模/模型", "172": "视觉开发/外观开发",
    "173": "动画导演", "174": "发行", "175": "原作协力", "176": "製作协力", "177": "製作统括",
    "178": "制作事务", "179": "OP・ED 动画制作", "180": "3DCG 导演助理", "181": "CG 导演助理",
    "182": "制作制片人"
}

def translate_position(raw_pos):
    if isinstance(raw_pos, list):
        nums = [str(x) for x in raw_pos if x]
    else:
        nums = [str(raw_pos)] if raw_pos else []
    display = '/'.join(POS_MAP.get(n, n) for n in nums)
    sort_key = min((int(n) for n in nums), default=0)
    return display, sort_key

def normalize_tags(tags):
    out = []
    if not tags:
        return out
    for t in tags:
        if isinstance(t, dict):
            name = t.get('name') or ''
            count = t.get('count') or 0
            if name:
                out.append([name, count])
        elif isinstance(t, str) and t:
            out.append([t, 0])
    return out

# 隐藏项过滤标记：依据标签名做包含匹配，追加 5 个布尔字段
TAG_KEYWORDS = {
    'is_compilation': ("总集篇", "拆分放送", "TV版", "TV剪辑版"),
    'is_short_mv': ("短片", "泡面番", "MV", "Music Video"),
    'is_cn': ("国产", "国漫"),
    'is_western': ("欧美", "美国"),
    'is_r18': ("里番",),
}

def calc_anime_flags(tags):
    names = [t[0] for t in tags]
    return {
        key: any(any(k in name for k in keywords) for name in names)
        for key, keywords in TAG_KEYWORDS.items()
    }

def source_label(url, direct_url):
    return "GitHub 直连" if url == direct_url else url.split("//")[1].split("/")[0]

# 每个下载源尝试独立线程执行，主控负责 2 秒连接硬超时与取消守卫；
_PART_LOCK = threading.Lock()

def _attempt_download_worker(label, url, proxies, zip_part, zip_path, total_size,
                             session_holder, established, cancel, result_q):
    session = get_session()
    # 显式代理失败后的直连尝试不能再次被环境变量代理接管。
    session.trust_env = False
    session_holder.append(session)
    offset = 0
    try:
        st = read_state()
        st['progress'] = f"正在连接下载源 {label} 5%"
        write_state(st)
        with _PART_LOCK:
            if os.path.exists(zip_part):
                offset = os.path.getsize(zip_part)
        if offset > 0:
            print(f"断点续传 {offset / 1024 / 1024:.0f}MB [{label}] ...")
        headers = {'Range': f'bytes={offset}-'} if offset > 0 else None
        t0 = time.time()
        with session.get(url, timeout=(2, 15), stream=True,
                         headers=headers, proxies=proxies) as r:
            elapsed = time.time() - t0
            if elapsed > CONNECT_LIMIT_SECONDS:
                raise Exception(f"建立连接耗时 {elapsed:.1f}s(>2s)")
            if cancel.is_set():
                raise Exception("已放弃")
            if offset > 0 and r.status_code == 200:
                offset = 0
                print("服务器不支持断点续传，从头重新下载")
            established.set()
            mode = "ab" if offset > 0 else "wb"
            last_report = 0.0
            seg_bytes = 0
            seg_t0 = time.time()
            seg_hist = []
            with open(zip_part, mode) as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if SHUTDOWN_EVENT.is_set():
                        raise Exception("操作已取消")
                    if cancel.is_set():
                        raise Exception("已放弃")
                    if not chunk:
                        continue
                    f.write(chunk)
                    offset += len(chunk)
                    seg_bytes += len(chunk)
                    now = time.time()
                    if now - seg_t0 >= SPEED_SAMPLE_SECONDS:
                        seg_t0 = now
                        seg_hist.append(seg_bytes)
                        seg_bytes = 0
                        if len(seg_hist) > 2:
                            seg_hist.pop(0)
                        spd = seg_hist[-1] / SPEED_SAMPLE_SECONDS
                        if len(seg_hist) == 2 and (seg_hist[0] + seg_hist[1]) < LOW_SPEED_TEN_SEC_BYTES:
                            raise Exception("下载速度过慢(连续10秒低于1MB)")
                        if not cancel.is_set() and total_size > 0:
                            pct = min(100, int(offset / total_size * 100))
                            overall = 5 + int(pct * 50 / 100)
                            st = read_state()
                            st['progress'] = f"正在下载 {overall}% ({spd / 1024 / 1024:.2f} MB/s)"
                            write_state(st)
                    elif total_size > 0 and now - last_report >= 0.2:
                        last_report = now
                        pct = min(100, int(offset / total_size * 100))
                        overall = 5 + int(pct * 50 / 100)
                        st = read_state()
                        st['progress'] = f"正在下载 {overall}%"
                        write_state(st)
        if cancel.is_set():
            raise Exception("已放弃")
        os.replace(zip_part, zip_path)
        session.close()
        result_q.put(("ok", None))
    except Exception as e:
        if not cancel.is_set():
            result_q.put(("fail", str(e)))


def _attempt_source(label, url, proxies, zip_part, zip_path, total_size):
    # 返回 (True, None) 成功；(False, reason)：reason='abandoned' 表示被主控强制放弃
    established = threading.Event()
    cancel = threading.Event()
    session_holder = []
    result_q = queue.Queue()
    t = threading.Thread(target=_attempt_download_worker,
                         args=(label, url, proxies, zip_part, zip_path, total_size,
                               session_holder, established, cancel, result_q),
                         daemon=True)
    t.start()
    if not established.wait(timeout=CONNECT_LIMIT_SECONDS):
        # 2 秒内未建立连接：强制放弃(关闭专属会话以打断阻塞)，等待线程收尾
        cancel.set()
        for s in session_holder:
            try:
                s.close()
            except Exception:
                pass
        t.join(timeout=5.0)
        return False, "abandoned"
    try:
        status, msg = result_q.get(timeout=300)
    except queue.Empty:
        cancel.set()
        for s in session_holder:
            try:
                s.close()
            except Exception:
                pass
        t.join(timeout=5.0)
        return False, "abandoned"
    if status == "ok":
        return True, None
    return False, msg or "失败"


def download_archive_zip(zip_url, zip_path, total_size=0):
    # 不做测速直接下载。有无系统代理都是三个源(GitHub直连/gh-proxy/ghfast)，
    # 有系统代理时三个都走系统代理，无代理时三个都直连；每源只试一次；
    # 2 秒内无法建立连接或下载中 10 秒累计 <1MB 即换下一源；全源失败清理 .part 并报错退出
    zip_part = zip_path + ".part"
    px = _system_proxy()
    direct = zip_url
    sources = [("GitHub 直连", direct),
               ("gh-proxy.com", "https://gh-proxy.com/" + zip_url),
               ("ghfast.top", "https://ghfast.top/" + zip_url)]
    attempts = []
    for label, url in sources:
        attempts.append((label, url, px))
        if px:
            attempts.append((label + "(直连)", url, None))
    failures = []
    for label, url, proxies in attempts:
        ok, info = _attempt_source(label, url, proxies, zip_part, zip_path, total_size)
        if ok:
            print(f"下载完成 [{label}]")
            return
        if info == "abandoned":
            # 连接超时被放弃：被放弃的线程已由 cancel/close/join 保证不再写盘，
            # 保留 .part 让下一源从已下载进度安全续传
            print(f"[{label}] 连接超时被放弃，切换下一源(保留断点)")
            failures.append(f"{label}: 建立连接超时(>2s)")
        else:
            print(f"[{label}] 中断: {info}")
            failures.append(f"{label}: {info}")
    try:
        if os.path.exists(zip_part):
            os.remove(zip_part)
    except OSError:
        pass
    raise Exception("所有下载源均失败：" + "；".join(failures) + "。请检查网络连接后重试。")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SHUTDOWN_EVENT = threading.Event()

# ==================== 系统代理接入 ====================
# requests 只认 HTTP(S)_PROXY 环境变量、不读 Windows 系统代理；
# 浏览器走系统代理(如 Clash 127.0.0.1:7890)快而程序直连被限速/卡住，故主动读取注册表接入

def _registry_proxy():
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            enabled = winreg.QueryValueEx(k, "ProxyEnable")[0]
            server = winreg.QueryValueEx(k, "ProxyServer")[0]
        if not enabled or not server:
            return None
        # Windows 代理可能是单地址，也可能是 http=...;https=... 形式。
        # PAC(AutoConfigURL)暂不解析；没有可用静态地址时交给直连兜底。
        def normalize(value):
            value = str(value or '').strip()
            if not value:
                return None
            return value if '://' in value else 'http://' + value

        if ';' in server or '=' in server:
            result = {}
            for item in server.split(';'):
                if '=' not in item:
                    continue
                scheme, value = item.split('=', 1)
                scheme = scheme.strip().lower()
                if scheme in ('http', 'https'):
                    proxy = normalize(value)
                    if proxy:
                        result[scheme] = proxy
            if result:
                fallback = result.get('https') or result.get('http')
                result.setdefault('http', fallback)
                result.setdefault('https', fallback)
                return result
        proxy = normalize(server)
        return {'http': proxy, 'https': proxy} if proxy else None
    except Exception:
        return None

def _env_proxies():
    http_p = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_p = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if http_p or https_p:
        def normalize(value):
            value = str(value or '').strip()
            if not value:
                return None
            return value if '://' in value else 'http://' + value
        http_p = normalize(http_p)
        https_p = normalize(https_p) or http_p
        return {"http": http_p or https_p, "https": https_p}
    return None

def _system_proxy():
    return _registry_proxy()

def active_proxies():
    # 显式环境变量优先，其次系统代理；每次读取以支持运行期间切换代理。
    return _env_proxies() or _system_proxy()

# ==================== 存储 ====================

def atomic_save(file_path, data):
    tmp_file = file_path + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        # 紧凑序列化：主文件可由 14MB 级缩至 4MB 级，读写解析均受益
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp_file, file_path)

def read_state():
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_state(state):
    atomic_save(STATE_FILE, state)

def load_local_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"rank": [], "rating": [], "collect": [], "broadcast": []}

def save_local_data(data):
    atomic_save(DATA_FILE, data)

def _load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def _save_json_compact(path, data):
    tmp_file = path + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp_file, path)

def load_detail_main():
    return _load_json_file(DETAIL_MAIN_FILE)

def load_detail_extra():
    return _load_json_file(DETAIL_EXTRA_FILE)

def save_detail_main(data):
    _save_json_compact(DETAIL_MAIN_FILE, data)

def save_detail_extra(data):
    _save_json_compact(DETAIL_EXTRA_FILE, data)

def has_detail_data():
    try:
        return os.path.getsize(DETAIL_MAIN_FILE) > 0
    except OSError:
        return False

_FILE_CACHE = {}
_FILE_CACHE_LOCK = threading.Lock()
# 防止预热(第一次点详情开关)与首次取详情并发时对详情文件双重解析
_FILE_LOAD_LOCK = threading.Lock()

def load_file_cached(path, loader):
    # 注意: 返回的是共享缓存对象，调用方必须视为只读，不得修改
    st = os.stat(path)
    key = (st.st_mtime, st.st_size)
    with _FILE_CACHE_LOCK:
        entry = _FILE_CACHE.get(path)
        if entry and entry[0] == key:
            return entry[1]
    # 双检 + 串行：同路径同时只有一次 loader() 在执行，其余调用等待后直接命中缓存
    with _FILE_LOAD_LOCK:
        with _FILE_CACHE_LOCK:
            entry = _FILE_CACHE.get(path)
            if entry and entry[0] == key:
                return entry[1]
        data = loader()
        with _FILE_CACHE_LOCK:
            _FILE_CACHE[path] = (key, data)
    return data

def load_local_data_cached():
    return load_file_cached(DATA_FILE, load_local_data)

def load_detail_main_cached():
    return load_file_cached(DETAIL_MAIN_FILE, load_detail_main)

def load_detail_extra_cached():
    return load_file_cached(DETAIL_EXTRA_FILE, load_detail_extra)

def load_user_watched():
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_user_watched(watched_list):
    atomic_save(USER_FILE, watched_list)

# ==================== 网络会话 ====================

_SHARED_SESSION = None

def get_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10))
    session.headers.update({'User-Agent': USER_AGENT})
    return session

def get_shared_session():
    # 全局共享会话：复用连接池，避免每次请求重新握手(requests.Session 对并发 GET 是安全的)
    global _SHARED_SESSION
    if _SHARED_SESSION is None:
        _SHARED_SESSION = get_session()
    return _SHARED_SESSION

def safe_request(url, timeout=(5, 10), session=None, headers=None):
    if SHUTDOWN_EVENT.is_set():
        raise Exception("操作已取消")
    if session is None:
        session = get_shared_session()
    try:
        resp = session.get(url, timeout=timeout, headers=headers, proxies=active_proxies())
        if resp.status_code != 200 and resp.status_code != 206:
            raise Exception(f"HTTP {resp.status_code}")
        return resp
    except requests.RequestException as e:
        if SHUTDOWN_EVENT.is_set():
            raise Exception("操作已取消")
        raise Exception(f"请求失败: {str(e)}")

# ==================== 推荐分与段位（统一全量池，数据更新时计算并落地） ====================

REC_SCORES_VERSION = 15

def _is_special_anime(a):
    return bool(a.get('is_compilation') or a.get('is_short_mv') or a.get('is_cn')
                or a.get('is_western') or a.get('is_r18'))

# 数据完整：五维(总排名/评分/热度/评分数/标准差)均有有效值；
# 不完整作品与特殊项目同样不占名额(不计入作品总数)
def _is_complete_anime(a):
    return ((a.get('overall_rank') or 999999) != 999999
            and (a.get('score_num') or 0) > 0
            and (a.get('pop_count') or 0) > 0
            and (a.get('score_cnt') or 0) > 0
            and a.get('std') is not None)

# 单维档位贡献(0~100，除以 10 即该维 0~10 分)：档位 = floor(k*100/total)，
# k 为池内严格更优的常规作品数；k=0(榜首)得满分 100，k 达到 total(最差)得 0
def _percentile_score(k, total):
    return max(0, 100 - (100 * k) // total)

# 段位与推荐分共用同一"完整池"：三张榜单(综合/评分/热度)全部条目按 subject_id 去重后即池，
# 常规数 total_regular = 池中非特殊(非总集/短片/国产/欧美/里番)且数据完整(五维均有有效值)的作品数；
# 总排名维度取更小值为优；评分/人数维度取更大值为优，同值按总排名(overall_rank 更小者更优)
# 打破并列，与榜单显示排序口径一致(负值反转后统一升序二分统计)。
# 特殊项目与数据不完整作品均不占名额：不进入计数与分母，自身顺延取当前档位(段位、贡献同理)。
# 无效指标值(总排名 999999 未上榜 / 评分为 0)：段位不出字段；贡献按"全部常规更优"自然为 0。
# 标准差维度取更小值为优(低标准差=争议小)，推荐分维度取更大值为优；二者有效值放宽为 >= 0。
# 各维度同值一律按总排名(唯一)打破并列，与榜单显示排序口径一致。
# 每部作品落地：pct_rank/pct_score/pct_pop/pct_cnt/pct_std/pct_rec = 各维段位 ceil(k*100/total) 最小 1%、封顶 100%，
# 推荐度 = 6×(1−评分百分位) + 3×(1−热度百分位) + 1×(1−标准差百分位)，各百分位取该维段位(1~100，越小越优)；
#   评分/热度/标准差百分位即 pct_score/pct_pop/pct_std(基于常规池段位)，直接作为最终推荐分(不再做 min/max 重映射)；
#   缺任一所需段位(评分/热度/标准差)者不写推荐度；
# 三榜各自保存副本，逐条写齐后与榜单一并入库
def fill_rec_scores(data):
    now = datetime.now()
    current_abs = now.year * 4 + ((now.month - 1) // 3)
    subjects = {}
    for key in ('rank', 'rating', 'collect'):
        for group in data.get(key, []):
            gq = group[0][1]
            try:
                gq_num = int(str(gq).replace('月', ''))
            except ValueError:
                gq_num = None
            # 未来两个季度的未播出作品不进入推荐分/百分位池(不占用分母、不影响现有作品段位)
            if gq_num is not None and group[0][0] * 4 + (gq_num - 1) // 3 > current_abs:
                continue
            for a in group[1]:
                subjects.setdefault(str(a['subject_id']), a)
    regulars = [a for a in subjects.values() if not _is_special_anime(a) and _is_complete_anime(a)]
    total_regular = len(regulars)
    if total_regular <= 0:
        return False
    # 复合键：总排名唯一，故总排名以外的各维度同值一律按总排名打破并列
    # (键为 (指标键, overall_rank)，升序 => 指标更优在前、同值排名更高者在前)
    rank_vals = sorted(a.get('overall_rank') for a in regulars)
    score_vals = sorted((-(a.get('score_num') or 0), a.get('overall_rank') or 999999) for a in regulars)
    pop_vals = sorted((-(a.get('pop_count') or 0), a.get('overall_rank') or 999999) for a in regulars)
    cnt_vals = sorted((-(a.get('score_cnt') or 0), a.get('overall_rank') or 999999) for a in regulars)
    std_vals = sorted((a.get('std') if a.get('std') is not None else float('inf'), a.get('overall_rank') or 999999) for a in regulars)

    def dimension(metric, values, composite, invalid, positive=True, value_map=None, negate=True):
        k_map = {}
        tier_map = {}
        for sid, a in subjects.items():
            v = value_map[sid] if value_map is not None else a.get(metric)
            valid = v is not None and v != invalid and (v > 0 if positive else v >= 0)
            if valid:
                if composite:
                    vv = -v if negate else v
                    k = bisect.bisect_left(values, (vv, a.get('overall_rank') or 999999))
                else:
                    k = bisect.bisect_left(values, v)
                tier_map[sid] = min(100, max(1, (k * 100 + total_regular - 1) // total_regular))
            else:
                k = total_regular
            k_map[sid] = k
        return k_map, tier_map

    rank_k, rank_t = dimension('overall_rank', rank_vals, False, 999999)
    score_k, score_t = dimension('score_num', score_vals, True, 0)
    pop_k, pop_t = dimension('pop_count', pop_vals, True, 0)
    cnt_k, cnt_t = dimension('score_cnt', cnt_vals, True, 0)
    std_k, std_t = dimension('std', std_vals, True, -1, positive=False, negate=False)

    # 推荐度 = 6×(1−评分百分位) + 3×(1−热度百分位) + 1×(1−标准差百分位)
    # 各百分位取该维段位(1~100，越小越优)；缺任一所需段位(评分/热度/标准差)者不计算(不写 rec_score)
    rec_map = {}
    for sid in subjects:
        t_score = score_t.get(sid)
        t_pop = pop_t.get(sid)
        t_std = std_t.get(sid)
        if t_score is None or t_pop is None or t_std is None:
            continue
        rec_map[sid] = round(6 * (1 - t_score / 100.0) + 3 * (1 - t_pop / 100.0) + (1 - t_std / 100.0), 2)
    # 推荐分档位：以已算好的推荐分为准(越大越前)，同值按总排名打破并列(有效值放宽为 >= 0)
    rec_vals = sorted((-(rec_map[sid]), a.get('overall_rank') or 999999)
                      for sid, a in subjects.items() if not _is_special_anime(a))
    rec_k, rec_t = dimension('rec_score', rec_vals, True, -1, positive=False, value_map=rec_map)
    for key in ('rank', 'rating', 'collect'):
        for group in data.get(key, []):
            for a in group[1]:
                sid = str(a['subject_id'])
                if sid in rec_map:
                    a['rec_score'] = rec_map[sid]
                if sid in rank_t:
                    a['pct_rank'] = rank_t[sid]
                if sid in score_t:
                    a['pct_score'] = score_t[sid]
                if sid in pop_t:
                    a['pct_pop'] = pop_t[sid]
                if sid in cnt_t:
                    a['pct_cnt'] = cnt_t[sid]
                if sid in std_t:
                    a['pct_std'] = std_t[sid]
                if sid in rec_t:
                    a['pct_rec'] = rec_t[sid]
    data['rec_scores_version'] = REC_SCORES_VERSION
    return True

# ==================== 归档更新 ====================

def build_weekly_baseline(local_data):
    # 上周快照：优先取榜单条目的精确评分，缺失时回退 anime_brief 的一位小数评分
    snap = {}
    for key in ('rank', 'rating', 'collect'):
        for group in (local_data.get(key) or []):
            for a in (group[1] if len(group) > 1 else []):
                sid = str(a.get('subject_id') or '')
                if not sid:
                    continue
                score = a.get('score_exact')
                if score is None and a.get('score_num'):
                    score = a.get('score_num')
                pop = a.get('pop_count')
                prev = snap.get(sid)
                if prev is None:
                    snap[sid] = {'score': score, 'pop': pop}
                else:
                    if prev.get('score') is None and score is not None:
                        prev['score'] = score
                    if prev.get('pop') is None and pop is not None:
                        prev['pop'] = pop
    for sid, b in (local_data.get('anime_brief') or {}).items():
        sid = str(sid)
        prev = snap.get(sid)
        if prev is None:
            snap[sid] = {'score': b.get('score'), 'pop': b.get('pop_count')}
        else:
            if prev.get('score') is None:
                prev['score'] = b.get('score')
            if prev.get('pop') is None:
                prev['pop'] = b.get('pop_count')
    return snap


def update_local_data():
    state = read_state()
    # 清除上次失败残留的错误状态，避免本次更新期间前端轮询持续显示"更新失败"
    state.pop('error', None)
    state['progress'] = "开始更新 0%"
    write_state(state)

    try:
        state['progress'] = "获取版本信息 2%"
        write_state(state)
        # 版本检查快速失败：代理不可用时再尝试直连，避免浏览器代理与程序代理不一致
        # 导致更新在第一步直接失败。直连请求关闭 trust_env，防止重新读入失效环境变量。
        configured_proxy = active_proxies()
        proxy_options = [configured_proxy]
        if configured_proxy:
            proxy_options.append(None)
        request_errors = []
        resp = None
        for proxy in proxy_options:
            session = requests.Session()
            session.trust_env = False
            try:
                resp = session.get(
                    GITHUB_API_URL,
                    timeout=(5, 10),
                    headers={'User-Agent': USER_AGENT},
                    proxies=proxy
                )
                if resp.status_code == 200:
                    break
                detail = resp.text.strip().replace('\n', ' ')[:200]
                request_errors.append(f"HTTP {resp.status_code}" + (f": {detail}" if detail else ""))
            except requests.RequestException as exc:
                request_errors.append(str(exc))
            finally:
                session.close()
        if not resp or resp.status_code != 200:
            tried = '；'.join(request_errors) or '无响应'
            raise Exception(f"获取版本信息失败：{tried}。请检查代理设置或网络连接")
        release_data = resp.json()
        zip_assets = [asset for asset in release_data.get('assets', [])
                      if asset['name'].startswith('dump-') and asset['name'].endswith('.zip')]
        if not zip_assets:
            raise Exception("在 Github Release 中未解析到符合 dump-*.zip 格式的数据包。")
        zip_assets.sort(key=lambda x: x['name'], reverse=True)
        latest_asset = zip_assets[0]
        zip_url = latest_asset['browser_download_url']
        zip_filename = latest_asset['name']
        zip_path = os.path.join(ARCHIVE_DIR, zip_filename)

        local_data = load_local_data()
        now = datetime.now()
        current_abs_now = now.year * 4 + (now.month - 1) // 3
        if (state.get('archive_version') == zip_filename and has_detail_data()
                and local_data.get('rec_scores_version') == REC_SCORES_VERSION
                and local_data.get('data_abs_quarter') == current_abs_now):
            state['progress'] = "已是最新版本 100%"
            write_state(state)
            try:
                if os.path.exists(ARCHIVE_DIR): shutil.rmtree(ARCHIVE_DIR)
            except OSError: pass
            return

        # 本次更新前把当前本地数据换算成“上周”基线，供评分变动/热度增长使用。
        # 同一归档版本因跨季度/算法版本变化而重建时，不能拿自己和自己比较，需原样保留已有增量。
        same_archive = (state.get('archive_version') == zip_filename)
        prev_snapshot = {} if same_archive else build_weekly_baseline(local_data)
        preserved_delta = {}
        if same_archive:
            for key in ('rank', 'rating', 'collect'):
                for group in (local_data.get(key) or []):
                    for a in (group[1] if len(group) > 1 else []):
                        sid = str(a.get('subject_id') or '')
                        if not sid:
                            continue
                        fields = {k: a[k] for k in
                                  ('prev_score', 'score_delta', 'prev_pop', 'pop_delta', 'pop_pct')
                                  if k in a}
                        if fields:
                            preserved_delta[sid] = fields

        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
        print(f"开始下载 {zip_filename} ...")
        download_archive_zip(zip_url, zip_path, latest_asset.get('size', 0))

        state['progress'] = "解压数据 60%"
        write_state(state)
        with zipfile.ZipFile(zip_path, 'r') as z:
            jsonlines = {}
            for name in z.namelist():
                base = name.rsplit('/', 1)[-1]
                if base.endswith('.jsonlines'):
                    jsonlines[base] = name
            subject_filename = next((n for k, n in jsonlines.items() if k == 'subject.jsonlines'), None)
            if not subject_filename:
                raise Exception("解压成功，但未找到 subject 数据文件。")
            detail_filenames = {}
            for key, aliases in {
                'person': ['person.jsonlines'],
                'character': ['character.jsonlines'],
                'subject_characters': ['subject-characters.jsonlines', 'subject_characters.jsonlines'],
                'subject_persons': ['subject-persons.jsonlines', 'subject_persons.jsonlines'],
                'person_characters': ['person-characters.jsonlines', 'person_characters.jsonlines'],
            }.items():
                detail_filenames[key] = next((n for k, n in jsonlines.items() if k in aliases), None)
            for f in [subject_filename] + [f for f in detail_filenames.values() if f]:
                z.extract(f, path=ARCHIVE_DIR)

        subject_path = os.path.join(ARCHIVE_DIR, subject_filename)

        state['progress'] = "处理榜单数据 65%"
        write_state(state)

        all_animes_brief = {}
        anime_data = defaultdict(list)
        bucket_data = defaultdict(list)
        detail_anime = {}
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        current_quarter_start = ((current_month - 1) // 3) * 3 + 1
        current_abs = current_year * 4 + (current_quarter_start - 1) // 3

        subject_size = os.path.getsize(subject_path)
        last_report = 0.0
        with open(subject_path, 'rb') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                # 按文件读取进度实时上报(节流)。注意: for line in f 迭代期间禁止调用 tell(), 必须用 readline()
                if time.time() - last_report >= 0.2:
                    last_report = time.time()
                    ratio = f.tell() / subject_size if subject_size else 0
                    state['progress'] = f"处理榜单数据 {65 + int(ratio * 20)}%"
                    write_state(state)
                # 字节级预筛：仅动画条目(type=2)解码，漫画/音乐/游戏等行直接跳过
                if not RE_B_TYPE2.search(line):
                    continue
                try:
                    item = json.loads(line)
                    date_str = item.get('date')
                    if not date_str: continue
                    
                    title = item.get('name_cn') or item.get('name') or "未知标题"
                    score_num = item.get('score') or 0.0
                    
                    all_animes_brief[str(item['id'])] = {
                        "title": title,
                        "date": date_str
                    }
                    
                    parts = date_str.split('-')
                    year = int(parts[0])
                    if year > current_year + 1: continue
                    month = 1
                    day = 1
                    if len(parts) >= 2:
                        try:
                            month = int(parts[1])
                            if month == 0: month = 1
                        except Exception: pass
                    if len(parts) >= 3:
                        try:
                            day = int(parts[2])
                        except Exception: pass
                    item_quarter_start = ((month - 1) // 3) * 3 + 1
                    # 季度末最后十天(3月22-31/6月21-30/9月21-30/12月22-31)开播的动画归入下个季度，12月跨年则年份+1
                    if month in (3, 6, 9, 12):
                        month_end_day = (31, 30, 30, 31)[month // 3 - 1]
                        if day >= month_end_day - 9:
                            item_quarter_start += 3
                            if item_quarter_start > 10:
                                item_quarter_start = 1
                                year += 1
                    # 允许收录到未来两个季度(当前季度之后两个)，更远的整季未公布数据丢弃
                    item_abs = year * 4 + (item_quarter_start - 1) // 3
                    if item_abs > current_abs + 2: continue
                    score_details = item.get('score_details') or {}
                    score_cnt = sum(score_details.values())  # 评分人数(评分数)
                    # 往年作品需评分人数 >=100 才收录(当年作品不受限)，噪声过滤保证榜单质量
                    if year < current_year and score_cnt < 100: continue
                    # 精确评分与标准差：评分分布(1~10 分档)的加权平均/加权总体标准差；
                    # 归档 score 仅 1 位小数，精确平均分可给出两位小数；标准差保留两位小数
                    score_exact = None
                    std = None
                    if score_cnt > 0:
                        try:
                            mean = sum(int(k) * v for k, v in score_details.items()) / score_cnt
                            var = sum(v * (int(k) - mean) ** 2 for k, v in score_details.items()) / score_cnt
                            score_exact = round(mean, 2)
                            std = round(var ** 0.5, 2)
                        except (ValueError, TypeError):
                            score_exact = None
                            std = None
                    # 收藏人数(热度)：favorite 为各收藏状态计数对象时求总和，纯数字直读，异常回退评分人数
                    fav = item.get('favorite')
                    if isinstance(fav, dict) and fav:
                        collect_count = sum(v for v in fav.values() if isinstance(v, (int, float)))
                    elif isinstance(fav, (int, float)):
                        collect_count = int(fav)
                    else:
                        collect_count = score_cnt

                    tags_normalized = normalize_tags(item.get('tags'))
                    anime_obj = {
                        "subject_id": item['id'],
                        "title": title,
                        "score_num": score_num,
                        "score_exact": score_exact,
                        "score_cnt": score_cnt,
                        "std": std,
                        "pop_count": collect_count,
                        "overall_rank": item.get('rank') or 999999,
                        "score_str": f"{score_num:.1f}" if score_num else "N/A",
                        "url": f"https://bgm.tv/subject/{item['id']}"
                    }
                    anime_obj.update(calc_anime_flags(tags_normalized))
                    # 相较上周的评分变动与热度增长（旧安装无基线时不写字段）
                    if same_archive:
                        preserved = preserved_delta.get(str(item['id']))
                        if preserved:
                            anime_obj.update(preserved)
                    else:
                        prev = prev_snapshot.get(str(item['id']))
                        if prev:
                            new_score = score_exact if score_exact is not None else (score_num if score_num else None)
                            prev_score = prev.get('score')
                            if new_score is not None and prev_score is not None:
                                anime_obj['prev_score'] = round(float(prev_score), 2)
                                anime_obj['score_delta'] = round(float(new_score) - float(prev_score), 2)
                            prev_pop = prev.get('pop')
                            if prev_pop is not None:
                                prev_pop = int(prev_pop)
                                pop_delta = int(collect_count or 0) - prev_pop
                                anime_obj['prev_pop'] = prev_pop
                                anime_obj['pop_delta'] = pop_delta
                                if prev_pop > 0:
                                    anime_obj['pop_pct'] = round(pop_delta * 100.0 / prev_pop, 1)
                    detail_anime[str(item['id'])] = {
                        "title": title,
                        "date": date_str,
                        "rank": item.get('rank') or 999999,
                        "score_cnt": score_cnt,
                        "pop_count": collect_count,
                        "score": score_num,
                        "summary": item.get('summary') or '',
                        "tags": tags_normalized,
                    }
                    # 2000 年及以后按季度归组；1970-1999 按"近细远粗"分段聚合(更早的不入榜)
                    if year >= 2000:
                        anime_data[(year, f"{item_quarter_start}月")].append(anime_obj)
                    elif year >= 1970:
                        # 分段：1970-1979 / 1980-1987 / 1988-1993 / 1994-1997 / 1998-1999
                        if year <= 1979: bidx = 0
                        elif year <= 1987: bidx = 1
                        elif year <= 1993: bidx = 2
                        elif year <= 1997: bidx = 3
                        else: bidx = 4
                        bucket_data[bidx].append(anime_obj)
                except Exception: continue

        final_data = { "rank": [], "rating": [], "collect": [], "broadcast": [], "plan": [] }
        # 记录构建时的绝对季度：跨季后点更新即使归档同版也会强制重建，避免占位行被当成正式数据
        final_data['data_abs_quarter'] = current_abs
        if same_archive:
            if local_data.get('delta_base'):
                final_data['delta_base'] = local_data.get('delta_base')
            if local_data.get('delta_base_date'):
                final_data['delta_base_date'] = local_data.get('delta_base_date')
        elif prev_snapshot:
            base_version = str(state.get('archive_version') or '')
            final_data['delta_base'] = base_version
            m = re.search(r'dump-(\d{4})-(\d{2})-(\d{2})', base_version)
            if m:
                final_data['delta_base_date'] = ''.join(m.groups())
        old_data = load_local_data()
        final_data["broadcast"] = old_data.get("broadcast", [])
        final_data["plan"] = old_data.get("plan", [])

        sorted_keys = sorted(anime_data.keys(), key=lambda x: (x[0], int(x[1].replace('月', ''))), reverse=True)

        for key in sorted_keys:
            year, quarter = key
            animes = anime_data[key]
            group_abs = year * 4 + (int(quarter.replace('月', '')) - 1) // 3
            # 未来两个季度：未播出作品尚无总排名/评分数，三榜统一按收藏数占位排序
            is_future = group_abs > current_abs
            if is_future:
                rank_list = collect_list = rating_list = sorted(
                    animes, key=lambda x: (x['pop_count'], -x['overall_rank']), reverse=True)[:60]
            else:
                # 过往季度(含本年度已过去的季度)三榜统一要求评分人数≥100；当前季度起不设门槛(新番评分人数普遍不足)
                past = group_abs < current_abs
                rank_list = sorted([a for a in animes if a['overall_rank'] < 999999 and (not past or a['score_cnt'] >= 100)],
                                   key=lambda x: x['overall_rank'])[:60]
                rating_list = sorted([a for a in animes if not past or a['score_cnt'] >= 100],
                                     key=lambda x: (x['score_exact'] if x.get('score_exact') is not None else x['score_num'], -x['overall_rank']), reverse=True)[:60]
                collect_list = sorted([a for a in animes if not past or a['score_cnt'] >= 100],
                                      key=lambda x: (x['pop_count'], -x['overall_rank']), reverse=True)[:60]
            if rank_list: final_data["rank"].append([[year, quarter], rank_list])
            if rating_list: final_data["rating"].append([[year, quarter], rating_list])
            if collect_list: final_data["collect"].append([[year, quarter], collect_list])

        # 2000 年以前按"近细远粗"分段(10/8/6/4/2 年)聚合成行，追加在三张榜单末尾：
        # 行键为 [起始年, "YYYY-YYYY"]，段内按三榜各自口径各取前 60，前端从起始年<2000 识别为聚合行
        for bidx, start_year, end_year in (
                (4, 1998, 1999), (3, 1994, 1997), (2, 1988, 1993),
                (1, 1980, 1987), (0, 1970, 1979)):
            animes = bucket_data.get(bidx)
            if not animes:
                continue
            era_label = f"{start_year}-{end_year}"
            rank_list = sorted([a for a in animes if a['overall_rank'] < 999999], key=lambda x: x['overall_rank'])[:60]
            rating_list = sorted([a for a in animes if a['score_cnt'] >= 100],
                                 key=lambda x: (x['score_exact'] if x.get('score_exact') is not None else x['score_num'], -x['overall_rank']), reverse=True)[:60]
            collect_list = sorted(animes, key=lambda x: (x['pop_count'], -x['overall_rank']), reverse=True)[:60]
            if rank_list: final_data["rank"].append([[start_year, era_label], rank_list])
            if rating_list: final_data["rating"].append([[start_year, era_label], rating_list])
            if collect_list: final_data["collect"].append([[start_year, era_label], collect_list])

        # 推荐分/段位基于三榜去重的完整池计算并落地(含 2000 年前聚合行的作品)
        fill_rec_scores(final_data)

        table_ids = set()
        for key in ('rank', 'rating', 'collect'):
            for group in final_data[key]:
                for a in group[1]: table_ids.add(str(a['subject_id']))
                
        table_detail_anime = {sid: d for sid, d in detail_anime.items() if sid in table_ids}

        state['progress'] = "处理详情数据 87%"
        write_state(state)

        def scan_jsonlines(path, id_pattern, id_ints):
            # 字节级预筛：先按 id 正则整行匹配，命中候选集合(整数 id)才 json.loads；
            # 正则无法定位(格式异常)时兜底解码后按主键判断
            if not path:
                return
            with open(path, 'rb') as f:
                for line in f:
                    m = id_pattern.search(line)
                    try:
                        if m:
                            if int(m.group(1)) in id_ints:
                                yield json.loads(line)
                        else:
                            item = json.loads(line)
                            key = item.get('subject_id') if id_pattern is RE_B_SUBJECT_ID else item.get('id')
                            if key is not None and int(key) in id_ints:
                                yield item
                    except Exception:
                        continue

        table_ids_int = {int(s) for s in table_ids}
        sc_path = os.path.join(ARCHIVE_DIR, detail_filenames['subject_characters']) if detail_filenames['subject_characters'] else None
        sp_path = os.path.join(ARCHIVE_DIR, detail_filenames['subject_persons']) if detail_filenames['subject_persons'] else None
        pc_path = os.path.join(ARCHIVE_DIR, detail_filenames['person_characters']) if detail_filenames['person_characters'] else None

        # 阶段一：三个详情关联文件并行扫描(各自独立容器，结果后再合并)
        def scan_subject_characters():
            raw = defaultdict(list)
            needed = set()
            for sc in scan_jsonlines(sc_path, RE_B_SUBJECT_ID, table_ids_int):
                sid = str(sc.get('subject_id') or '')
                if sid not in table_ids:
                    continue
                raw[sid].append((sc.get('type') or 99, sc.get('order') or 9999, str(sc.get('character_id') or '')))
                needed.add(str(sc.get('character_id') or ''))
            return raw, needed

        def scan_subject_persons():
            staff = defaultdict(list)
            needed = set()
            career = []
            for sp in scan_jsonlines(sp_path, RE_B_SUBJECT_ID, table_ids_int):
                sid = str(sp.get('subject_id') or '')
                pid = str(sp.get('person_id') or '')
                if not pid:
                    continue
                if sid in table_ids:
                    pos, pos_key = translate_position(sp.get('position') or '')
                    staff[sid].append([pid, pos, pos_key])
                    needed.add(pid)
                if sid in all_animes_brief:
                    career.append((pid, sid, sp.get('position') or ''))
            return staff, needed, career

        def scan_person_characters():
            va = defaultdict(list)
            needed = set()
            career = []
            for pc in scan_jsonlines(pc_path, RE_B_SUBJECT_ID, table_ids_int):
                sid = str(pc.get('subject_id') or '')
                pid = str(pc.get('person_id') or '')
                cid = str(pc.get('character_id') or '')
                if sid in table_ids:
                    if pid and cid and pid not in va[(sid, cid)]:
                        va[(sid, cid)].append(pid)
                        needed.add(pid)
                if pid and sid in all_animes_brief:
                    career.append((pid, sid, cid))
            return va, needed, career

        with ThreadPoolExecutor(max_workers=3) as ex:
            fut_sc = ex.submit(scan_subject_characters)
            fut_sp = ex.submit(scan_subject_persons)
            fut_pc = ex.submit(scan_person_characters)
            subject_characters_raw, sc_needed = fut_sc.result()
            subject_persons_table, sp_needed, career_staff_raw = fut_sp.result()
            character_va, pc_needed, career_va_raw = fut_pc.result()

        needed_person_ids = sp_needed | pc_needed
        needed_character_ids = sc_needed

        subject_characters_table = {}
        for sid, char_list in subject_characters_raw.items():
            char_list.sort(key=lambda x: (x[0], x[1]))
            ordered = []
            seen = set()
            for _, _, cid in char_list:
                if cid not in seen:
                    seen.add(cid)
                    ordered.append(cid)
            subject_characters_table[sid] = ordered

        # (作品, 角色) -> 角色类型：1 主角 / 2 配角 / 3 客串；供声优实线/虚线标记使用
        role_type_map = {}
        for sid, char_list in subject_characters_raw.items():
            for typ, _order, cid in char_list:
                try:
                    role_type_map[(str(sid), str(cid))] = int(typ)
                except (TypeError, ValueError):
                    role_type_map[(str(sid), str(cid))] = 0

        for staff_list in subject_persons_table.values():
            staff_list.sort(key=lambda x: x[2])

        # 履历按需过滤（此时 needed_person_ids 已完整）。条目改为紧凑数组 [sid,pos]/[sid,cid]，
        # 标题/日期收敛到 career_subjects 单份映射(仅收录被引用到的作品)，大幅缩减文件体积
        career_subjects = {}
        person_career_staff = defaultdict(list)
        for pid, sid, raw_pos in career_staff_raw:
            if pid in needed_person_ids:
                pos, _ = translate_position(raw_pos)
                person_career_staff[pid].append([sid, pos])
                if sid not in career_subjects:
                    b = all_animes_brief[sid]
                    career_subjects[sid] = [b["title"], b["date"]]

        person_career_va = defaultdict(list)
        for pid, sid, cid in career_va_raw:
            if pid in needed_person_ids:
                role_type = role_type_map.get((str(sid), str(cid)), 0)
                person_career_va[pid].append([sid, cid, role_type])
                needed_character_ids.add(cid)
                if sid not in career_subjects:
                    b = all_animes_brief[sid]
                    career_subjects[sid] = [b["title"], b["date"]]

        state['progress'] = "处理履历数据 90%"
        write_state(state)

        # 阶段二：人物/角色名称文件并行扫描(依赖上一阶段合并出的 needed 集合)
        p_path = os.path.join(ARCHIVE_DIR, detail_filenames['person']) if detail_filenames['person'] else None
        c_path = os.path.join(ARCHIVE_DIR, detail_filenames['character']) if detail_filenames['character'] else None

        def scan_person_names():
            names = {}
            person_ints = {int(x) for x in needed_person_ids}
            for p in scan_jsonlines(p_path, RE_B_ID, person_ints):
                pid = str(p.get('id') or '')
                if pid in needed_person_ids:
                    names[pid] = p.get('name_cn') or p.get('name') or ''
            return names

        def scan_character_names():
            names = {}
            char_ints = {int(x) for x in needed_character_ids}
            for c in scan_jsonlines(c_path, RE_B_ID, char_ints):
                cid = str(c.get('id') or '')
                if cid in needed_character_ids:
                    names[cid] = c.get('name_cn') or c.get('name') or ''
            return names

        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_pn = ex.submit(scan_person_names)
            fut_cn = ex.submit(scan_character_names)
            person_names = fut_pn.result()
            character_names = fut_cn.result()

        for sid, d in table_detail_anime.items():
            d['staff'] = subject_persons_table.get(sid, [])
            d['characters'] = [[cid, character_va.get((sid, cid), [])] for cid in subject_characters_table.get(sid, [])]

        # 详情数据拆成两个文件：
        # detail_main = 作品主体(标签/简介/staff/characters) + 人物/角色名；detail_extra = 人物/声优履历
        detail_main = {
            'anime': table_detail_anime,
            'persons': person_names,
            'characters': character_names,
        }
        detail_extra = {
            'career_staff': person_career_staff,
            'career_va': person_career_va,
            'career_subjects': career_subjects,
        }

        anime_brief = {}
        for sid, d in table_detail_anime.items():
            anime_brief[sid] = {
                "title": d.get('title'),
                "date": d.get('date'),
                "rank": d.get('rank'),
                "score": d.get('score'),
                "pop_count": d.get('pop_count'),
                "tags": d.get('tags', [])
            }
        final_data['anime_brief'] = anime_brief

        state['progress'] = "保存数据 92%"
        write_state(state)
        # 顺序写：core → careers → 主文件；任一中断下次更新可整体重建
        save_detail_main(detail_main)
        state['progress'] = "保存数据 94%"
        write_state(state)
        save_detail_extra(detail_extra)
        state['progress'] = "保存数据 96%"
        write_state(state)
        save_local_data({k: v for k, v in final_data.items() if k != 'detail'})
        state['progress'] = "保存数据 98%"
        write_state(state)

        state['archive_version'] = zip_filename

        try:
            if os.path.exists(ARCHIVE_DIR):
                shutil.rmtree(ARCHIVE_DIR)
        except Exception as e:
            print(f"清理临时文件失败: {e}")

        state['progress'] = "完成 100%"
        write_state(state)
        return

    except Exception as e:
        error_msg = str(e)
        state['error'] = error_msg
        state['progress'] = "错误"
        write_state(state)
        raise

# ==================== 爬虫 ====================

# Yuc 排期表按天缓存：手动搜索时不再重复爬取
_YUC_CACHE = {"date": None, "data": None}

def fetch_yuc_times():
    today = datetime.now().strftime("%Y-%m-%d")
    if _YUC_CACHE.get("date") == today:
        return _YUC_CACHE["data"]
    yuc_dict = {}
    try:
        now = datetime.now()
        y = now.year
        m = (now.month - 1) // 3 * 3 + 1
        resp = None
        for _ in range(4):
            url = f"https://yuc.wiki/{y}{m:02d}/"
            try:
                resp = safe_request(url, timeout=(5, 10))
                break
            except Exception:
                resp = None
            m -= 3
            if m <= 0:
                m += 12
                y -= 1
        if resp is None:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        for title in soup.select(".date_title_, .title_zh, .title_en"):
            name = title.get_text(" ", strip=True)
            if not name:
                continue
            parent = title.find_parent(lambda tag: RE_TIME.search(tag.get_text(" ", strip=True)))
            if parent:
                match = RE_TIME.search(parent.get_text(" ", strip=True))
                if match:
                    yuc_dict[name] = match.group(1)
    except Exception as e:
        print("Yuc获取异常:", e)

    cleaned = {}
    for k, v in yuc_dict.items():
        clean_k = RE_CLEAN_TEXT.sub('', k).lower()
        if clean_k:
            cleaned[clean_k] = v
    # 抓取成功才写入缓存，失败时下次仍会重试
    _YUC_CACHE["date"] = today
    _YUC_CACHE["data"] = cleaned
    return cleaned

def match_yuc_time(name_cn, yuc_cleaned):
    matched_time = "23:59"
    display_time = "未知"
    if not yuc_cleaned:
        return matched_time, display_time
    clean_bgm = RE_CLEAN_TEXT.sub('', name_cn).lower()
    if clean_bgm in yuc_cleaned:
        matched_time = yuc_cleaned[clean_bgm]
        display_time = matched_time
    else:
        for y_name, y_time in yuc_cleaned.items():
            if y_name and clean_bgm and (y_name in clean_bgm or clean_bgm in y_name):
                matched_time = y_time
                display_time = matched_time
                break
        else:
            matches = difflib.get_close_matches(clean_bgm, yuc_cleaned.keys(), n=1, cutoff=0.6)
            if matches:
                matched_time = yuc_cleaned[matches[0]]
                display_time = matched_time
    return matched_time, display_time

def fetch_episode_progress(subject_id):
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        ep_url = f"https://api.bgm.tv/v0/episodes?subject_id={subject_id}&type=0&limit={EPISODE_LIMIT}"
        ep_resp = safe_request(ep_url, timeout=(5, 10))
        eps_data = ep_resp.json().get('data', [])
        if not eps_data:
            return None, None
        total_eps = min(len(eps_data), EPISODE_LIMIT)
        aired_eps = sum(1 for ep in eps_data if ep.get('airdate') and ep.get('airdate') <= today_str)
        return total_eps, min(aired_eps, EPISODE_LIMIT)
    except Exception:
        return None, None

def fetch_broadcast_data():
    yuc_cleaned = fetch_yuc_times()

    cal_url = "https://api.bgm.tv/calendar"
    resp = safe_request(cal_url, timeout=(5, 10))
    cal_data = resp.json()
    bgm_calendar = []
    for day_data in cal_data:
        wd = day_data['weekday']['id']
        for item in day_data.get('items', []):
            item['weekday'] = wd
            bgm_calendar.append(item)

    def fetch_progress(anime):
        if SHUTDOWN_EVENT.is_set():
            return None
        subject_id = anime['id']
        name_cn = anime.get('name_cn') or anime.get('name')
        air_date = anime.get('air_date', '未知')
        if "配音" in name_cn or "中配" in name_cn:
            return None

        matched_time, display_time = match_yuc_time(name_cn, yuc_cleaned)

        total_eps, aired_eps = fetch_episode_progress(subject_id)
        if not total_eps:
            return None
        return {
            'title': name_cn,
            'id': subject_id,
            'total': total_eps,
            'aired': aired_eps,
            'air_date': air_date,
            'update_time': display_time,
            'sort_time': matched_time,
            'weekday': anime['weekday']
        }

    st = read_state()
    st['broadcast_progress'] = "正在更新 5%"
    write_state(st)

    executor = ThreadPoolExecutor(max_workers=4)
    futures = [executor.submit(fetch_progress, anime) for anime in bgm_calendar]
    total_futures = len(futures)
    done_count = 0
    last_report = 0.0
    results = []
    try:
        for future in as_completed(futures):
            if SHUTDOWN_EVENT.is_set():
                break
            done_count += 1
            try:
                result = future.result()
                if result and result['total'] > 0:
                    results.append(result)
            except Exception:
                continue
            # 进度上报节流(0.2s)，避免频繁写盘拖慢更新
            if total_futures > 0 and time.time() - last_report >= 0.2:
                last_report = time.time()
                pct = int(done_count / total_futures * 100)
                st = read_state()
                st['broadcast_progress'] = f"正在更新 {pct}%"
                write_state(st)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    try:
        st = read_state()
        st.pop('broadcast_progress', None)
        write_state(st)
    except Exception:
        pass
    return results

def search_anime_and_build(keyword):
    search_url = f"https://api.bgm.tv/search/subject/{urllib.parse.quote(keyword)}?type=2&responseGroup=small"
    res = safe_request(search_url, timeout=(5, 10))
    data = res.json()
    items = data.get('list') or []
    if not items:
        raise Exception("未搜索到相关的番剧")

    # 优先添加最匹配的搜索结果：名称完全一致 > 包含关系 > 文本相似度，相同时取列表靠前的
    clean_kw = RE_CLEAN_TEXT.sub('', keyword).lower()
    best_item = None
    best_key = (-1.0, -1)
    for idx, item in enumerate(items):
        cand_name = item.get('name_cn') or item.get('name') or ''
        base = RE_CLEAN_TEXT.sub('', cand_name).lower()
        if not base:
            continue
        if not clean_kw:
            sim = 0.0
        elif base == clean_kw:
            sim = 2.0
        elif clean_kw in base or base in clean_kw:
            sim = 1.5
        else:
            sim = difflib.SequenceMatcher(None, clean_kw, base).ratio()
        key = (sim, -idx)
        if key > best_key:
            best_key = key
            best_item = item
    if best_item is None:
        best_item = items[0]

    first_item = best_item
    subject_id = first_item['id']
    name_cn = first_item.get('name_cn') or first_item.get('name')

    sub_url = f"https://api.bgm.tv/v0/subjects/{subject_id}"
    sub_res = safe_request(sub_url, timeout=(5, 10))
    bgm_weekday = None
    bgm_time = "未知"
    air_date = "未知"
    sub_data = sub_res.json()
    air_date = sub_data.get('date') or "未知"
    for info in sub_data.get('infobox', []):
        key = info.get('key', '')
        val_str = str(info.get('value', ''))
        if key == "放送星期":
            match = RE_WEEKDAY.search(val_str)
            if match:
                bgm_weekday = WEEKDAY_MAP.get(match.group(1))
        elif key in ["放送开始", "放送时间"]:
            time_match = RE_TIME.search(val_str)
            if time_match:
                bgm_time = time_match.group(1)

    if not bgm_weekday and air_date != '未知':
        try:
            dt = datetime.strptime(air_date, "%Y-%m-%d")
            bgm_weekday = dt.isoweekday()
        except Exception:
            pass
    if not bgm_weekday:
        bgm_weekday = datetime.now().isoweekday()

    yuc_cleaned = fetch_yuc_times()
    matched_time, display_time = match_yuc_time(name_cn, yuc_cleaned)
    sort_time = matched_time if matched_time != "23:59" else (bgm_time if ":" in bgm_time else "23:59")

    total_eps = 1
    aired_eps = 0
    fetched_total, fetched_aired = fetch_episode_progress(subject_id)
    if fetched_total:
        total_eps = fetched_total
        aired_eps = fetched_aired

    return {
        'title': name_cn,
        'id': f"manual_{subject_id}",
        'total': total_eps,
        'aired': aired_eps,
        'air_date': air_date,
        'update_time': display_time,
        'sort_time': sort_time,
        'weekday': bgm_weekday,
        'is_manual': True
    }

# ==================== 用户同步 ====================

def sync_user_collections(username):
    if not username or not username.strip():
        save_user_watched([])
        try:
            st = read_state()
            st.pop('sync_progress', None)
            write_state(st)
        except Exception:
            pass
        return []

    encoded_name = urllib.parse.quote(username.strip())
    watched_set = set()
    offset = 0
    limit = 50
    session = get_session()

    while True:
        url = f"https://api.bgm.tv/v0/users/{encoded_name}/collections?subject_type=2&limit={limit}&offset={offset}"
        try:
            resp = session.get(url, timeout=(5, 10), proxies=active_proxies())
        except requests.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")

        if resp.status_code != 200:
            try:
                err_data = resp.json()
                err_msg = err_data.get('message', resp.text)
            except Exception:
                err_msg = resp.text or f"HTTP {resp.status_code}"
            if "offset should be less than or equal to" in err_msg:
                break
            else:
                raise Exception(f"API 返回错误 (HTTP {resp.status_code}): {err_msg}")

        data = resp.json()
        items = data.get('data', [])
        if not items:
            break

        for item in items:
            subject_id = item.get('subject_id')
            if not subject_id and 'subject' in item:
                subject_id = item['subject'].get('id')
            if subject_id:
                watched_set.add(str(subject_id))

        total = data.get('total', 0)
        if total:
            pct = int(min(offset + limit, total) / total * 100)
            st = read_state()
            st['sync_progress'] = f"正在同步 {pct}%"
            write_state(st)
        if offset + limit >= total:
            break
        offset += limit
        time.sleep(0.5)

    watched_list = list(watched_set)
    save_user_watched(watched_list)
    try:
        st = read_state()
        st.pop('sync_progress', None)
        write_state(st)
    except Exception:
        pass
    return watched_list

# ==================== 后端接口 ====================

class Api:
    def get_local_data(self, compress=True):
        try:
            watched = load_user_watched()
            if compress:
                # 直接压缩本地数据文件的原始字节(再 base64)：
                # 省掉一次 json.loads + json.dumps，同时把经 js_api 桥传输的体积压到 ~1.9MB
                with open(DATA_FILE, 'rb') as f:
                    raw = f.read()
                w = json.dumps(watched, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                payload = b'{"l":' + raw + b',"w":' + w + b'}'
                return {"deflate_base64": base64.b64encode(zlib.compress(payload, 6)).decode('ascii')}
            data = load_local_data_cached()
            # 核心修复：只下发轻量级的番剧目录(表格字段+标签)，详细 staff/summary 等按需从 detail 文件获取
            # 注意：缓存对象为只读共享，必须构造新 dict，不能修改 data 本身
            anime_map = data.get("anime_brief", {})
            resp_data = {k: v for k, v in data.items() if k != 'anime_brief'}
            return {"data": resp_data, "watched": watched, "anime_map": anime_map}
        except Exception as e:
            return {"error": str(e)}

    # 最新下载的归档日期(取自归档包名 dump-YYYY-MM-DD.*.zip → YYYYMMDD)
    def get_data_date(self):
        try:
            state = read_state()
            version = str(state.get('archive_version') or '')
            m = re.search(r'dump-(\d{4})-(\d{2})-(\d{2})', version)
            if m:
                return {"date": ''.join(m.groups())}
            return {"date": ""}
        except Exception as e:
            return {"date": "", "error": str(e)}

    # 获取单个作品的详情主体(简介/标签/制作人员/角色声优)，来自 detail_main；履历另行按人拉取
    def get_anime_detail(self, subject_id):
        try:
            detail = load_detail_main_cached()
            anime_map = detail.get("anime", {})
            sid = str(subject_id)

            if sid not in anime_map:
                return {"error": "未找到该作品的详情，请先点击底部的“更新数据”"}

            target_anime = anime_map[sid]

            pids = set()
            cids = set()

            for p in target_anime.get("staff", []):
                pids.add(p[0])
            for c in target_anime.get("characters", []):
                cids.add(c[0])
                for va in c[1]:
                    pids.add(va)

            persons = {p: detail.get("persons", {}).get(p, "未知") for p in pids}
            characters = {c: detail.get("characters", {}).get(c, "未知角色") for c in cids}

            return {
                "success": True,
                "anime": target_anime,
                "persons": persons,
                "characters": characters
            }
        except Exception as e:
            return {"error": str(e)}

    # 按需拉取单个制作人员/声优的履历(staff+va 一起返回)，来自 detail_extra
    def get_person_careers(self, person_id):
        try:
            detail = load_detail_extra_cached()
            pid = str(person_id)
            career_subjects = detail.get("career_subjects") or {}

            def meta_of(ref_sid):
                m = career_subjects.get(str(ref_sid))
                return (m[0], m[1]) if m else ("", "")

            staff = []
            for sid_ref, pos in detail.get("career_staff", {}).get(pid, []):
                title, date = meta_of(sid_ref)
                staff.append({"sid": str(sid_ref), "title": title, "date": date, "pos": pos})

            # 声优角色涉及的作品可能不在当前详情视图内，角色名随响应一并带回
            characters = {}
            va = []
            for entry in detail.get("career_va", {}).get(pid, []):
                if not entry:
                    continue
                sid_ref, cid = entry[0], entry[1]
                role_type = entry[2] if len(entry) > 2 else 0
                title, date = meta_of(sid_ref)
                va.append({"sid": str(sid_ref), "cid": cid, "title": title,
                           "date": date, "role_type": role_type})
                if cid and str(cid) not in characters:
                    characters[str(cid)] = "未知角色"

            if characters:
                chars_map = load_detail_main_cached()
                name_map = chars_map.get("characters", {})
                for cid in characters:
                    name = name_map.get(cid)
                    if name:
                        characters[cid] = name

            return {"success": True, "staff": staff, "va": va, "characters": characters}
        except Exception as e:
            return {"error": str(e)}

    # 全库人物检索：scope='cast' 只搜有配音履历者，'staff' 只搜有制作履历者；
    # 名称完全一致 > 前缀 > 包含 > 文本相似度，返回相近结果供详情页底栏使用
    def search_persons(self, keyword, scope='cast', limit=50):
        try:
            kw = RE_CLEAN_TEXT.sub('', str(keyword or '')).lower()
            if not kw:
                return {"success": True, "results": []}
            names = load_detail_main_cached().get("persons") or {}
            extra = load_detail_extra_cached()
            career = extra.get("career_va" if scope == 'cast' else "career_staff") or {}
            scored = []
            for pid, works in career.items():
                name = names.get(str(pid)) or ''
                base = RE_CLEAN_TEXT.sub('', name).lower()
                if not base:
                    continue
                if base == kw:
                    score = 4.0
                elif base.startswith(kw):
                    score = 3.0
                elif kw in base:
                    score = 2.0
                else:
                    score = difflib.SequenceMatcher(None, kw, base).ratio()
                    if score < 0.5:
                        continue
                scored.append((score, len(works or []), name, str(pid)))
            scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
            try:
                limit = max(1, min(100, int(limit)))
            except (TypeError, ValueError):
                limit = 50
            results = [{"pid": pid, "name": name, "count": cnt}
                       for _, cnt, name, pid in scored[:limit]]
            return {"success": True, "results": results}
        except Exception as e:
            return {"error": str(e)}

    def get_update_progress(self):
        try:
            state = read_state()
            progress = state.get('progress', '')
            error = state.get('error', '')
            if progress == "完成 100%" or progress == "已是最新版本 100%":
                if 'error' in state:
                    del state['error']
                    write_state(state)
            return {"progress": progress, "error": error}
        except Exception as e:
            return {"progress": "", "error": str(e)}

    def get_sync_progress(self):
        try:
            state = read_state()
            return {"progress": state.get('sync_progress', '')}
        except Exception as e:
            return {"progress": "", "error": str(e)}

    def get_broadcast_progress(self):
        try:
            state = read_state()
            return {"progress": state.get('broadcast_progress', '')}
        except Exception as e:
            return {"progress": "", "error": str(e)}

    def open_url(self, url):
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"打开链接失败: {e}")

    def update_local_data(self):
        try:
            update_local_data()
            return {"success": True}
        except Exception as e:
            traceback.print_exc()
            state = read_state()
            error_detail = state.get('error', str(e))
            return {"error": error_detail}

    def sync_user_data(self, username):
        try:
            watched_list = sync_user_collections(username)
            return {"success": True, "watched": watched_list}
        except Exception as e:
            error_msg = str(e)
            if "400" in error_msg:
                error_msg += "。请确认用户名输入正确（仅支持英文或数字，不支持特殊符号）"
            return {"error": error_msg}

    def save_watched(self, watched_list):
        try:
            save_user_watched(list(watched_list))
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def update_broadcast_data(self):
        try:
            new_broadcast = fetch_broadcast_data()
            # 防覆盖：获取结果过少说明网络异常，保留原有数据，避免排期列表被清空
            if len(new_broadcast) < 5:
                return {"error": f"排期数据获取不完整(仅获取到 {len(new_broadcast)} 条)，已保留原有数据，请稍后重试"}
            old_data = load_local_data()
            old_broadcast = old_data.get("broadcast", [])
            time_map = {}
            manual_animes = []
            for a in old_broadcast:
                raw_id = str(a.get('id'))
                if raw_id.startswith('manual_'):
                    raw_id = raw_id[len('manual_'):]
                time_map[raw_id] = {
                    'update_time': a.get('update_time', '未知'),
                    'sort_time': a.get('sort_time', '23:59')
                }
                if a.get('is_manual'):
                    manual_animes.append((raw_id, a))

            new_ids = set(str(a['id']) for a in new_broadcast)
            for a in new_broadcast:
                old = time_map.get(str(a['id']))
                if old:
                    if a.get('update_time') == '未知' and old.get('update_time') != '未知':
                        a['update_time'] = old['update_time']
                    if a.get('sort_time') == '23:59' and old.get('sort_time') != '23:59':
                        a['sort_time'] = old['sort_time']

            for raw_id, ma in manual_animes:
                if raw_id in new_ids:
                    continue
                if raw_id.isdigit():
                    total_eps, aired_eps = fetch_episode_progress(int(raw_id))
                    if total_eps:
                        ma['total'] = total_eps
                        ma['aired'] = aired_eps
                new_broadcast.append(ma)

            old_data["broadcast"] = new_broadcast
            save_local_data(old_data)

            state = read_state()
            state['broadcast_last_update'] = datetime.now().strftime("%Y-%m-%d")
            write_state(state)

            return {"success": True, "broadcast": new_broadcast}
        except Exception as e:
            traceback.print_exc()
            # 异常时清理进度残留，避免按钮进度条卡住
            try:
                st = read_state()
                st.pop('broadcast_progress', None)
                write_state(st)
            except Exception:
                pass
            return {"error": str(e)}

    def auto_update_broadcast_if_needed(self):
        today = datetime.now().strftime("%Y-%m-%d")
        state = read_state()
        if state.get('broadcast_last_update') == today:
            return {"updated": False}
        result = self.update_broadcast_data()
        if "error" in result:
            return {"updated": False, "error": result["error"]}
        else:
            data = load_local_data()
            return {"updated": True, "broadcast": data.get("broadcast", [])}

    def save_broadcast_data(self, broadcast_data):
        try:
            data = load_local_data()
            data["broadcast"] = broadcast_data
            save_local_data(data)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def save_plan_data(self, plan_data):
        try:
            data = load_local_data()
            data["plan"] = plan_data
            save_local_data(data)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    def search_and_add_anime(self, keyword):
        try:
            anime = search_anime_and_build(keyword)
            return {"success": True, "anime": anime}
        except Exception as e:
            return {"error": str(e)}

    def shutdown(self, *args):
        SHUTDOWN_EVENT.set()

    def get_theme(self):
        state = read_state()
        return state.get('theme', 'dark')

    def set_theme(self, theme):
        state = read_state()
        state['theme'] = theme
        write_state(state)
        return {"success": True}

    def get_tip_mode(self):
        state = read_state()
        return state.get('tip_mode', 'data')

    def set_tip_mode(self, mode):
        state = read_state()
        state['tip_mode'] = mode
        write_state(state)
        return {"success": True}

    def get_ui_settings(self):
        state = read_state()
        ui = state.get('ui_settings')
        return ui if isinstance(ui, dict) else {}

    def save_ui_settings(self, settings):
        state = read_state()
        ui = state.get('ui_settings')
        if not isinstance(ui, dict):
            ui = {}
        if isinstance(settings, dict):
            for k in ('timeAxis', 'sortDescending', 'tipTrigger', 'tipMode', 'tipRadar', 'tipDetail'):
                if k in settings:
                    ui[k] = settings[k]
        state['ui_settings'] = ui
        write_state(state)
        return {"success": True}

    def get_saved_username(self):
        state = read_state()
        return state.get('last_username', '')

    def save_username(self, username):
        state = read_state()
        state['last_username'] = username or ''
        write_state(state)
        return {"success": True}

    # 预热详情主体(detail_main)：首次进入作品详情页时读取解析
    def preload_detail_data(self):
        load_detail_main_cached()
        return {"success": True}

    # 空闲预读履历文件(detail_extra)：进入详情页后后台执行，供履历/声优点击秒开
    def preload_detail_extra(self):
        load_detail_extra_cached()
        return {"success": True}

# ==================== 入口 ====================

def cleanup_temp_files():
    try:
        if os.path.exists(ARCHIVE_DIR):
            for name in os.listdir(ARCHIVE_DIR):
                try:
                    os.remove(os.path.join(ARCHIVE_DIR, name))
                except OSError:
                    pass
            shutil.rmtree(ARCHIVE_DIR, ignore_errors=True)
    except OSError:
        pass
    for path in (DATA_FILE, DETAIL_MAIN_FILE, DETAIL_EXTRA_FILE, USER_FILE, STATE_FILE):
        tmp = path + ".tmp"
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

# ==================== 主窗口 ====================
# 窗口在双击后立即显示；前端在数据渲染完成时对整体内容做 0.1s 渐入。
if __name__ == '__main__':
    html_path = os.path.join(RESOURCE_DIR, 'index.html')

    print(f"加载资源路径: {html_path}")

    if not os.path.exists(html_path):
        raise FileNotFoundError(f"找不到 index.html，请检查路径: {html_path}")

    # 把上次保存的表格基础设置随 URL 传给页面：
    # 页面首帧就能选对骨架(纵/横轴)，避免启动时的视觉切换
    _ui = read_state().get('ui_settings')
    if not isinstance(_ui, dict):
        _ui = {}

    def _ui_pick(key, allowed, dflt):
        v = _ui.get(key)
        return v if v in allowed else dflt

    # 旧配置只有 tipMode 时按 panel/data 迁移到两个独立开关
    _legacy_data = _ui.get('tipMode') == 'data'
    _radar_on = _ui.get('tipRadar', not _legacy_data) is not False
    _detail_on = _ui.get('tipDetail', _legacy_data) is True
    _ui_query = 'ui=1&axis=%s&order=%s&trigger=%s&panel=%s&radar=%s&detail=%s' % (
        _ui_pick('timeAxis', ('v', 'h'), 'v'),
        '1' if _ui.get('sortDescending') is not False else '0',
        _ui_pick('tipTrigger', ('select', 'hover'), 'select'),
        _ui_pick('tipMode', ('data', 'panel'), 'panel'),
        '1' if _radar_on else '0',
        '1' if _detail_on else '0',
    )
    page_url = html_path + '?' + _ui_query

    api = Api()
    # 窗口空白底色与网页主题背景一致，避免显示瞬间出现纯白空白帧
    _theme = read_state().get('theme', 'dark')
    _bg_color = '#000000' if _theme == 'dark' else '#e6e6e6'
    window = webview.create_window(
        title='AnimeList_v4.4',
        url=page_url,
        js_api=api,
        width=1920,
        height=1080,
        min_size=(1280, 720),
        background_color=_bg_color
    )
    window.events.closing += api.shutdown

    webview.start(debug=False)

    # 窗口已关闭：短暂等待让进行中的原子保存/下载收尾，清理残留临时文件，
    # 然后强制退出，避免 pywebview 残留的非守护线程(网络请求等)拖住进程导致黑窗口不关闭
    time.sleep(1.0)
    cleanup_temp_files()
    os._exit(0)
