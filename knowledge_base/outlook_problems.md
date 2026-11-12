# Outlook Problems and Fixes

Applies to: Microsoft Outlook desktop client on Windows.

## Outlook is stuck on "Disconnected" or "Trying to connect"
1. Check the status bar at the bottom of Outlook. If it says "Working Offline", open the Send/Receive tab and turn off Work Offline.
2. Confirm you have an internet connection. Outside the office, connect to the VPN if prompted.
3. Close Outlook fully from Task Manager and open it again.

## Outlook crashes or freezes when opening attachments
Start Outlook in safe mode by pressing Windows key + R, typing `outlook.exe /safe` and pressing Enter. If it works in safe mode, a faulty add-in is the cause. Go to File, Options, Add-ins and disable add-ins one by one.

## Search does not find emails
Rebuild the search index: File, Options, Search, Indexing Options, Advanced, Rebuild. Indexing can take up to an hour.

## Mailbox is full
Archive old emails with File, Info, Cleanup Tools, Archive. Empty the Deleted Items folder. The standard mailbox limit is 50 GB.

## Repeated password prompts
This usually follows a password change. Open Windows Credential Manager, remove stored entries that start with "MicrosoftOffice", then restart Outlook and sign in again.

## Escalation
If the Outlook profile is corrupted, the Application Support team can create a new profile. Raise a Software incident and include the Outlook version (File, Office Account).
