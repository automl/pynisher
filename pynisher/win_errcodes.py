# The master cheat-sheets
# https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/1bc92ddf-b79e-413c-bbaa-99a5281a6c90
#
# If you find out more codes caused by memory specific reasons for Windows to kill a
# process, please put in a PR to add them
# The cpu timeout one should be sufficient
#
# Do not import `pywin32` or other windows related libraries here as we need it to
# import on all systems

# Memory related
WIN_STATUS_PAGEFILE_QUOTA = 0xC0000007  # 3221225479
WIN_STATUS_IN_PAGE_ERROR = 0xC0000006  # 3221225478
WIN_STATUS_ACCESS_VIOLATION = 0xC0000005  # 3221225477

WIN_MEMORY_EXITCODES = [
    WIN_STATUS_PAGEFILE_QUOTA,
    WIN_STATUS_IN_PAGE_ERROR,
    WIN_STATUS_ACCESS_VIOLATION,
]

# Cputime out
WIN_STATUS_QUOTA_EXCEEDED = 0xC0000044  # 3221225540

WIN_CPUTIMEOUT_EXITCODES = [WIN_STATUS_QUOTA_EXCEEDED]

# Specific WinError codes attached ot an OSError
WIN_ERROR_COMMITMENT_LIMIT = 1455
