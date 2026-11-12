# Wi-Fi Connectivity Issues

Applies to: corporate Wi-Fi network "Corp-Secure" in all offices.

## Cannot see or connect to the Wi-Fi network
1. Make sure Wi-Fi is turned on and airplane mode is off. On Windows laptops press the Wi-Fi key or use the network icon in the taskbar.
2. Forget the "Corp-Secure" network and reconnect. Sign in with your company username and password.
3. Restart your laptop. Many connection faults clear after a restart.
4. Try moving closer to an access point. Signal is weaker in stairwells and meeting rooms with glass walls.

## Connected to Wi-Fi but no internet
- Run the Windows network troubleshooter: Settings, Network and Internet, Network troubleshooter.
- Open PowerShell and run `ipconfig /release` followed by `ipconfig /renew` to obtain a fresh IP address.
- Check whether colleagues near you have the same problem. If many people are affected, it is probably an access point or switch outage, and you should raise a high-impact incident.

## Slow Wi-Fi
Disconnect other devices from the hotspot, avoid large downloads during video calls, and switch to the 5 GHz network band "Corp-Secure-5G" if it is available.

## Guest Wi-Fi
Visitors must use "Corp-Guest". Guest Wi-Fi has no access to internal applications. Staff devices must not use the guest network.
