"""Sample IT knowledge base articles (written for the demo)."""
ARTICLES = [
 ("VPN: authentication timeout or cannot connect", "Network",
  "Symptoms: the VPN client shows authentication timeout, gateway not responding, or connects and drops. "
  "1) Check your internet works without the VPN. 2) Fully quit and restart the VPN client. 3) Confirm the password "
  "has not expired and the account is not locked. 4) Switch the VPN server/profile if more than one is listed. "
  "5) If many colleagues have the same error at once, report it as a possible gateway outage to Network Support instead of retrying."),
 ("Wi-Fi keeps disconnecting or is very slow", "Network",
  "1) Forget the office Wi-Fi network and reconnect. 2) Turn Wi-Fi off and on, then restart the laptop. "
  "3) Move closer to an access point; meeting rooms and kitchens often have weak coverage. 4) Update the Wi-Fi driver "
  "from the company software portal. 5) If it happens on one floor for many users, raise a ticket for Network Support with the floor and time."),
 ("Wired network port has no connection", "Network",
  "1) Check the cable is firmly plugged in at both ends. 2) Try a different cable or a different wall port. "
  "3) Look for the link light on the laptop port. 4) If you moved desks, the port may not be enabled; ask Network Support to activate it, quoting the port label."),
 ("Password reset (self-service)", "Access",
  "Use the self-service portal: choose 'Forgot password', verify with your registered phone or authenticator app, then set a new password "
  "of at least 12 characters. New passwords cannot match your last 5. If verification fails, contact the Service Desk with your employee ID "
  "to have your identity confirmed and the password reset manually."),
 ("Account locked out", "Access",
  "Accounts lock after 5 wrong password attempts and unlock automatically after 30 minutes. To unlock sooner, use the self-service portal "
  "or contact the Service Desk. Check that saved passwords on phones and old laptops are updated, because they cause repeated failed attempts."),
 ("Printer offline or not printing", "Hardware",
  "1) Check the printer shows ready and has paper and toner. 2) Clear any stuck jobs from the print queue. 3) Remove and re-add the printer "
  "from Settings > Printers using the printer name on its label. 4) For repeated paper jams, report the printer name and floor to Hardware Support."),
 ("Laptop restarts continuously or blue screen", "Hardware",
  "1) Unplug all external devices and the dock, then power on. 2) Check the charger and battery; try another charger. "
  "3) Boot into safe mode and uninstall recent updates or drivers. 4) Check for overheating: blocked vents or a loud fan. "
  "5) If it still restarts, back up your files if possible and raise a Hardware Support ticket with the model and any error code."),
 ("Laptop is slow or the disk is full", "Hardware",
  "1) Restart the laptop; do not just close the lid. 2) Check Task Manager for programs using high CPU or memory and close them. "
  "3) Free disk space: empty the recycle bin and run Disk Cleanup. 4) Keep at least 10 percent of the disk free. 5) If still slow, ask Hardware Support about a RAM or disk upgrade."),
 ("Outlook not syncing or stuck on disconnected", "Email",
  "1) Check you are online and that webmail opens. 2) In Outlook, turn off Work Offline. 3) Restart Outlook, then the laptop. "
  "4) Recreate the Outlook profile from Control Panel > Mail. 5) If webmail is also slow or down for many users, the mail server may have an outage: report it to the Service Desk."),
 ("Mailbox full or cannot send attachments", "Email",
  "The standard mailbox quota is 50 GB and the maximum attachment size is 25 MB. Archive or delete old mail and empty Deleted Items. "
  "For large files, share a link from the company file share instead of attaching. Request a quota increase from the Service Desk with a business reason."),
 ("Request software installation", "Software",
  "Approved software can be installed from the Software Center without a ticket. For other software, raise a request with the product name, "
  "version, business reason and your manager's approval. Licensed products need a licence from the software owner before installation."),
 ("Application keeps crashing or freezing", "Software",
  "1) Fully close the application and reopen it. 2) Restart the laptop. 3) Check for updates in the Software Center. "
  "4) Repair or reinstall the application from the Software Center. 5) Note the exact error message and the time, then raise a Software Support ticket."),
 ("Multi-factor authentication (MFA) code not working", "Access",
  "Check your phone's time is set to automatic, because wrong time breaks codes. Make sure you are using the correct account entry in the authenticator app. "
  "If you changed phones, ask the Service Desk to reset your MFA registration after identity verification."),
 ("Cannot access a shared drive or internal application", "Access",
  "1) Confirm you are on the office network or connected to the VPN. 2) Check that other internal sites open. 3) Request access through the "
  "access request form, quoting the drive or application name and your manager's approval. Access usually takes one business day."),
]
