import os
import time
import platform
import sys
import shutil 
import psutil
from winapi import *
from offset import CALL_OFFSET


def get_pid_by_name(process_name):
    is_64bit = "64" in platform.architecture()[0] 
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['name'] == process_name:
            pid = process.info['pid']
            exe_path = psutil.Process(pid).exe()
            wechat_version = GetWeChatVersion(exe_path)
            if wechat_version not in CALL_OFFSET:
                raise Exception(f"当前微信的版本({wechat_version})不在支持的列表，目前支持的版本列表: {list(CALL_OFFSET.keys())}")
            if is_64bit != IsProcess64Bit(pid):
                raise Exception("Python位数和查找进程的位数不符，请同时使用32位或64位!")
            return pid

def inject_dll(pid, dllpath=None):
    '''注入dll到给定的进程，返回http端口'''
    if not dllpath:
        raise Exception("给定的dllpath不存在")
    dllpath = os.path.abspath(dllpath)
    if not os.path.exists(dllpath):
        raise Exception('给定的dllpath不存在')
    dllname = os.path.basename(dllpath)
    dll_addr = getModuleBaseAddress(dllname, pid)
    if dll_addr:
        print("当前进程已存在相同名称的dll")
        return dll_addr
    # 通过微信进程pid获取进程句柄
    hProcess = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    # 在微信进程中申请一块内存
    lpAddress = VirtualAllocEx(hProcess, None, MAX_PATH, MEM_COMMIT, PAGE_EXECUTE_READWRITE)
    # 往内存中写入要注入的dll的绝对路径
    WriteProcessMemory(hProcess, lpAddress, c_wchar_p(dllpath), MAX_PATH, byref(c_ulong()))
    # 在微信进程内调用LoadLibraryW加载dll
    hRemote = CreateRemoteThread(hProcess, None, 0, LoadLibraryW, lpAddress, 0, None)
    time.sleep(0.01)
    # 关闭句柄
    CloseHandle(hProcess)
    CloseHandle(hRemote)
    time.sleep(0.01)
    dll_addr = getModuleBaseAddress(dllname, pid)
    return dll_addr


def uninject_dll(pid, dllname):
    dll_addr = getModuleBaseAddress(dllname, pid)
    hProcess = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    while dll_addr:
        hRemote = CreateRemoteThread(hProcess, None, 0, FreeLibrary, dll_addr, 0, None)
        CloseHandle(hRemote)
        time.sleep(0.01)
        dll_addr = getModuleBaseAddress(dllname, pid)
    CloseHandle(hProcess)


def inject_python_to_process(pid):
    if not pid:
        raise Exception("请先启动微信后再注入!")
    python_path = os.path.dirname(sys.executable)
    python_bit = platform.architecture()[0][:2]
    dllname = f"injectpy{python_bit}.dll"
    dll_python_path = os.path.join(python_path, dllname)
    dll_new_path = os.path.abspath(f"dll\\{dllname}")
    # 如果dll已经存在，则比较版本
    if os.path.exists(dll_python_path):
        dll_python_version = GetFileVersionInfo(dll_python_path)
        dll_new_version = GetFileVersionInfo(dll_new_path)
        if dll_python_version != dll_new_version:
            os.remove(dll_python_path)
    # 将injectpy.dll复制到Python所在路径
    if not os.path.exists(dll_python_path):
        shutil.copyfile(dll_new_path, dll_python_path)
    addr = inject_dll(pid, dll_python_path)
    print("注入后的dll基址: ", addr)


if __name__ == "__main__":
    pid = get_pid_by_name("WeChat.exe")
    print("查找到的微信进程pid: ", pid)
    inject_python_to_process(pid)
    