# Set in an OSError for windows when a memory limit is reached
# https://docs.microsoft.com/en-us/windows/win32/debug/system-error-codes--1300-1699-
WIN_ERROR_COMMITMENT_LIMIT = 1455

# Set from PerJobUserTimeLimit in JOBOBJECT_BASIC_LIMIT_INFORMATION
# It's actual name is ERROR_NOT_ENOUGH_QUOTA but we use it for detecting a cputimeout
# https://docs.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information
# https://docs.microsoft.com/en-us/windows/win32/debug/system-error-codes--1700-3999-
WIN_EXITCODE_CPUTIMEOUT = 1816
