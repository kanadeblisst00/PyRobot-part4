import platform

if "64" in platform.architecture()[0]:
    from sendmsg64 import SendMsg
else:
    from sendmsg32 import SendMsg











