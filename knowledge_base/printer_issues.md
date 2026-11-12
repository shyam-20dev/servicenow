# Printer Issues

Applies to: shared office printers (for example PRN-2F-01) and the print server print.company.example.

## Printer shows offline or print jobs are stuck
1. Check that the printer is switched on, has paper and shows no error on its display.
2. On your laptop open Settings, Printers and scanners, select the printer and choose "Open print queue". Cancel any stuck documents.
3. If the queue does not clear, restart the Print Spooler service: open PowerShell as administrator and run `Restart-Service Spooler`.
4. Remove the printer and add it again using the address \\print.company.example\PRN-2F-01.

## Poor print quality
Streaks or faded text usually mean the toner is low. Run the cleaning cycle from the printer menu. Replace the toner cartridge from the supply cupboard or request one through a Facilities service request.

## Paper jam
Open the rear and front covers and gently pull the paper in the direction of the paper path. Never pull hard or use tools, because internal parts can be damaged.

## Secure print and badge release
Select "Secure Print" in the print dialog and release the job by tapping your access card on the printer. Jobs not released within 24 hours are deleted.

## Escalation
If the whole team cannot print, the printer is likely offline at the network level. Raise a Hardware incident with the printer name and floor.
