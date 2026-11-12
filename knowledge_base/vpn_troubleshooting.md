# VPN Troubleshooting Guide

Applies to: GlobalConnect VPN client on company laptops (Windows and macOS).

## Symptoms
The VPN will not connect, connects but internal applications are unreachable, or the VPN disconnects repeatedly.

## Step-by-step fixes
1. Check that your home internet works: open a public website such as a news page. If it does not load, restart your router first.
2. Close the GlobalConnect VPN client completely (right-click the tray icon, choose Quit) and open it again.
3. Select the nearest gateway from the gateway list. If the automatic gateway fails, choose "vpn-eu.company.example" or "vpn-asia.company.example" manually.
4. Confirm your multi-factor authentication (MFA) prompt is approved within 60 seconds. An expired MFA prompt makes the VPN fail with "Authentication timeout".
5. Check that your laptop date and time are correct and set to automatic. A wrong clock breaks the VPN certificate check.

## Connected but cannot reach internal applications
Disconnect and reconnect to refresh your DNS settings. On Windows open PowerShell and run `ipconfig /flushdns`, then reconnect. If the portal still does not open, try the application by its IP address or contact the Network Support team.

## Frequent disconnects
Switch from Wi-Fi to a wired connection if possible, disable other VPN or proxy software, and update the GlobalConnect client from the Software Center.

## When to raise an incident
If none of the steps work, raise an incident with category Network and include the exact error message, the time it happened and the gateway you used. Network Support handles VPN incidents.
